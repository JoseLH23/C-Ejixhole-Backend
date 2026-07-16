"""Reglas de negocio y cálculo único de reservaciones."""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.reservacion import ESTADOS_RESERVACION, Reservacion
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje
from app.repositories.reservacion_repository import ReservacionRepository
from app.services.tarifa_especial_service import TarifaEspecialService

ESTADOS_TERMINALES = ("completada", "cancelada")


def _es_violacion_de_traslape(error: IntegrityError) -> bool:
    return "ck_no_traslape_unidad_hospedaje" in str(error.orig)


class ReservacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReservacionRepository(db)
        self.tarifa_service = TarifaEspecialService(db)

    def _guardar_o_409(self, operacion):
        try:
            return operacion()
        except IntegrityError as error:
            self.db.rollback()
            if _es_violacion_de_traslape(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Esa unidad de hospedaje ya tiene una reservación activa que se traslapa con esas fechas.",
                )
            raise

    def _obtener_precio_entrada(self) -> Decimal:
        servicio_entrada = (
            self.db.query(Servicio)
            .filter(Servicio.categoria == "entrada", Servicio.reservable.is_(True))
            .first()
        )
        if not servicio_entrada or not servicio_entrada.activo:
            raise HTTPException(
                status_code=500,
                detail=(
                    "No hay un servicio de 'Acceso al parque' activo y reservable "
                    "configurado en el catálogo. Revísalo en el módulo Servicios."
                ),
            )
        return servicio_entrada.precio

    def _aplicar_tarifas_especiales(
        self,
        *,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        unidad_hospedaje_id: int | None,
        total_base: Decimal,
        desglose: list[dict],
    ) -> tuple[Decimal, list[dict]]:
        dias = 1 if tipo_reservacion == "entrada" else (fecha_salida - fecha_llegada).days
        if dias <= 0:
            return total_base, desglose
        ajuste, lineas = self.tarifa_service.calcular_ajustes(
            tipo=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            base_diaria=total_base / Decimal(dias),
        )
        return total_base + ajuste, [*desglose, *lineas]

    def _validar_y_calcular(
        self,
        servicio_id: int,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        unidad_hospedaje_id: int | None,
        num_personas: int,
        excluir_reservacion_id: int | None = None,
    ) -> tuple[Servicio, "UnidadHospedaje | None", int, Decimal, list[dict]]:
        servicio = self.db.query(Servicio).filter(Servicio.id == servicio_id).first()
        if not servicio:
            raise HTTPException(status_code=404, detail="Servicio no encontrado.")
        if not servicio.activo:
            raise HTTPException(status_code=400, detail="Este servicio ya no está disponible.")
        if servicio.capacidad_maxima and num_personas > servicio.capacidad_maxima:
            raise HTTPException(
                status_code=400,
                detail=f"Este servicio admite máximo {servicio.capacidad_maxima} personas.",
            )

        noches = (fecha_salida - fecha_llegada).days
        unidad = None
        if tipo_reservacion == "hospedaje":
            unidad = self.db.query(UnidadHospedaje).filter(UnidadHospedaje.id == unidad_hospedaje_id).first()
            if not unidad:
                raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada.")
            if not unidad.activa:
                raise HTTPException(status_code=400, detail="Esta unidad de hospedaje ya no está disponible.")
            if num_personas > unidad.capacidad_maxima:
                raise HTTPException(status_code=400, detail=f"{unidad.nombre} admite máximo {unidad.capacidad_maxima} personas.")
            if self.repo.existe_traslape_unidad_hospedaje(
                unidad.id,
                fecha_llegada,
                fecha_salida,
                excluir_reservacion_id=excluir_reservacion_id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{unidad.nombre} ya está ocupada en alguna de esas fechas.",
                )

        precio_entrada = self._obtener_precio_entrada()
        desglose: list[dict] = []
        if tipo_reservacion == "entrada":
            subtotal_entrada = precio_entrada * num_personas
            desglose.append({
                "concepto": "Entrada al parque",
                "detalle": f"${precio_entrada} x {num_personas} persona(s)",
                "subtotal": subtotal_entrada,
            })
            total = subtotal_entrada
        elif tipo_reservacion == "camping":
            subtotal_entrada = precio_entrada * num_personas * noches
            subtotal_camping = servicio.precio * num_personas * noches
            desglose.extend([
                {
                    "concepto": "Entrada al parque",
                    "detalle": f"${precio_entrada} x {num_personas} persona(s) x {noches} noche(s)",
                    "subtotal": subtotal_entrada,
                },
                {
                    "concepto": "Camping",
                    "detalle": f"${servicio.precio} x {num_personas} persona(s) x {noches} noche(s)",
                    "subtotal": subtotal_camping,
                },
            ])
            total = subtotal_entrada + subtotal_camping
        else:
            subtotal_entrada = precio_entrada * num_personas * noches
            subtotal_hospedaje = unidad.precio_por_noche * noches
            desglose.extend([
                {
                    "concepto": "Entrada al parque",
                    "detalle": f"${precio_entrada} x {num_personas} persona(s) x {noches} noche(s)",
                    "subtotal": subtotal_entrada,
                },
                {
                    "concepto": unidad.nombre,
                    "detalle": f"${unidad.precio_por_noche} x {noches} noche(s)",
                    "subtotal": subtotal_hospedaje,
                },
            ])
            total = subtotal_entrada + subtotal_hospedaje

        total, desglose = self._aplicar_tarifas_especiales(
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            total_base=total,
            desglose=desglose,
        )
        return servicio, unidad, noches, total, desglose

    def cotizar(
        self,
        servicio_id: int,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        unidad_hospedaje_id: int | None,
        num_personas: int,
    ) -> tuple[int, Decimal, list[dict]]:
        _, _, noches, total, desglose = self._validar_y_calcular(
            servicio_id,
            tipo_reservacion,
            fecha_llegada,
            fecha_salida,
            unidad_hospedaje_id,
            num_personas,
        )
        return noches, total, desglose

    def crear(
        self,
        cliente_id: int,
        servicio_id: int,
        usuario_id: int | None,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        unidad_hospedaje_id: int | None,
        num_personas: int,
        origen: str,
        notas: str | None,
    ) -> Reservacion:
        cliente = self.db.query(Cliente).filter(Cliente.id == cliente_id).first()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado.")
        if not cliente.activo:
            raise HTTPException(status_code=400, detail="No se puede reservar para un cliente desactivado.")

        _, unidad, _, total, _ = self._validar_y_calcular(
            servicio_id,
            tipo_reservacion,
            fecha_llegada,
            fecha_salida,
            unidad_hospedaje_id,
            num_personas,
        )
        reservacion = Reservacion(
            cliente_id=cliente_id,
            servicio_id=servicio_id,
            usuario_id=usuario_id,
            unidad_hospedaje_id=unidad.id if unidad else None,
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            fecha_visita=fecha_llegada,
            num_personas=num_personas,
            origen=origen,
            total=total,
            monto_pagado=0,
            notas=notas,
        )
        return self._guardar_o_409(lambda: self.repo.crear(reservacion))

    def obtener_por_id(self, reservacion_id: int) -> Reservacion:
        reservacion = self.repo.obtener_por_id(reservacion_id)
        if not reservacion:
            raise HTTPException(status_code=404, detail="Reservación no encontrada.")
        return reservacion

    def listar(self, **filtros) -> list[Reservacion]:
        return self.repo.listar(**filtros)

    def cambiar_estado(self, reservacion_id: int, nuevo_estado: str) -> Reservacion:
        if nuevo_estado not in ESTADOS_RESERVACION:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {nuevo_estado}")
        reservacion = self.obtener_por_id(reservacion_id)
        if reservacion.estado in ESTADOS_TERMINALES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Esta reservación ya está en estado terminal '{reservacion.estado}' y no puede cambiar de estado.",
            )
        if reservacion.estado == nuevo_estado:
            raise HTTPException(status_code=400, detail=f"La reservación ya está en estado '{nuevo_estado}'.")
        return self.repo.actualizar_estado(reservacion, nuevo_estado)

    def actualizar(
        self,
        reservacion_id: int,
        servicio_id: int | None = None,
        fecha_llegada: date | None = None,
        fecha_salida: date | None = None,
        num_personas: int | None = None,
        unidad_hospedaje_id: int | None = None,
        notas: str | None = None,
    ) -> Reservacion:
        reservacion = self.obtener_por_id(reservacion_id)
        if reservacion.estado in ESTADOS_TERMINALES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Esta reservación ya está en estado terminal '{reservacion.estado}' y no se puede editar.",
            )

        nuevo_servicio_id = servicio_id if servicio_id is not None else reservacion.servicio_id
        nueva_fecha_llegada = fecha_llegada if fecha_llegada is not None else reservacion.fecha_llegada
        nueva_fecha_salida = fecha_salida if fecha_salida is not None else reservacion.fecha_salida
        nuevo_num_personas = num_personas if num_personas is not None else reservacion.num_personas
        nueva_unidad_id = unidad_hospedaje_id if unidad_hospedaje_id is not None else reservacion.unidad_hospedaje_id

        if nueva_fecha_salida < nueva_fecha_llegada:
            raise HTTPException(400, "fecha_salida no puede ser anterior a fecha_llegada")
        if reservacion.tipo_reservacion == "entrada" and nueva_fecha_salida != nueva_fecha_llegada:
            raise HTTPException(400, "Para 'entrada' (visita de un día), fecha_llegada y fecha_salida deben ser el mismo día")
        if reservacion.tipo_reservacion in ("camping", "hospedaje") and nueva_fecha_salida == nueva_fecha_llegada:
            raise HTTPException(
                400,
                f"Para '{reservacion.tipo_reservacion}' se necesita al menos 1 noche (fecha_salida posterior a fecha_llegada)",
            )

        _, unidad, _, nuevo_total, _ = self._validar_y_calcular(
            nuevo_servicio_id,
            reservacion.tipo_reservacion,
            nueva_fecha_llegada,
            nueva_fecha_salida,
            nueva_unidad_id,
            nuevo_num_personas,
            excluir_reservacion_id=reservacion_id,
        )
        if nuevo_total < reservacion.monto_pagado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"El nuevo total (${nuevo_total}) sería menor a lo ya pagado "
                    f"(${reservacion.monto_pagado}). Registra un reembolso antes de reducir esta reservación."
                ),
            )

        cambios = {
            "servicio_id": nuevo_servicio_id,
            "fecha_llegada": nueva_fecha_llegada,
            "fecha_salida": nueva_fecha_salida,
            "fecha_visita": nueva_fecha_llegada,
            "num_personas": nuevo_num_personas,
            "unidad_hospedaje_id": unidad.id if unidad else None,
            "total": nuevo_total,
        }
        if notas is not None:
            cambios["notas"] = notas
        return self._guardar_o_409(lambda: self.repo.actualizar(reservacion, cambios))

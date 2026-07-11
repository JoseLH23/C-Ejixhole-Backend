"""
Service de Reservaciones. Reglas de negocio; el acceso a datos se
delega a ReservacionRepository (y a los repos/queries de Cliente y
Servicio para validar que existen).
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.reservacion import ESTADOS_RESERVACION, Reservacion
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje
from app.repositories.reservacion_repository import ReservacionRepository

ESTADOS_TERMINALES = ("completada", "cancelada")

# Nota (decisión de negocio, ver docs/portal-publico-fase-1.md): el
# costo es el mismo para adultos y niños — "num_personas" es un
# conteo simple, sin niveles de precio por edad.
#
# Los precios de entrada y camping YA NO están fijos aquí — salen del
# catálogo real (Servicio.precio), para que puedan editarse desde el
# módulo Servicios sin tocar código si algún día suben de precio. Ver
# _obtener_servicio_entrada().


class ReservacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReservacionRepository(db)

    def _obtener_precio_entrada(self) -> Decimal:
        """
        Precio real de "Acceso al parque" (categoria="entrada",
        reservable=True), tomado del catálogo — editable desde el
        módulo Servicios sin tocar código. Camping y hospedaje también
        lo necesitan porque la entrada siempre se incluye en su costo.

        Si no existe o está desactivado, es un error de configuración
        real del catálogo, no un problema del cliente que reserva —
        se reporta como 500 con un mensaje claro para que se arregle
        desde Servicios, en vez de cobrar un precio adivinado.
        """
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

    def _validar_y_calcular(
        self,
        servicio_id: int,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        unidad_hospedaje_id: int | None,
        num_personas: int,
    ) -> tuple[Servicio, "UnidadHospedaje | None", int, Decimal, list[dict]]:
        """
        Valida todo lo que no depende del cliente (servicio existe y
        activo, capacidad, unidad de hospedaje disponible) y calcula
        el total real — junto con el DESGLOSE por concepto, para que
        el visitante siempre sepa exactamente qué se le está
        cobrando, no solo el número final. Compartido por crear() y
        cotizar() — el precio que se cotiza es EXACTAMENTE el mismo
        que se cobra al crear, nunca dos fórmulas que puedan
        desincronizarse.
        """
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
            unidad = (
                self.db.query(UnidadHospedaje)
                .filter(UnidadHospedaje.id == unidad_hospedaje_id)
                .first()
            )
            if not unidad:
                raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada.")
            if not unidad.activa:
                raise HTTPException(
                    status_code=400, detail="Esta unidad de hospedaje ya no está disponible."
                )
            if num_personas > unidad.capacidad_maxima:
                raise HTTPException(
                    status_code=400,
                    detail=f"{unidad.nombre} admite máximo {unidad.capacidad_maxima} personas.",
                )
            if self.repo.existe_traslape_unidad_hospedaje(unidad.id, fecha_llegada, fecha_salida):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{unidad.nombre} ya está ocupada en alguna de esas fechas.",
                )

        precio_entrada = self._obtener_precio_entrada()
        desglose: list[dict] = []

        if tipo_reservacion == "entrada":
            subtotal_entrada = precio_entrada * num_personas
            desglose.append(
                {
                    "concepto": "Entrada al parque",
                    "detalle": f"${precio_entrada} x {num_personas} persona(s)",
                    "subtotal": subtotal_entrada,
                }
            )
            total = subtotal_entrada
        elif tipo_reservacion == "camping":
            subtotal_entrada = precio_entrada * num_personas * noches
            subtotal_camping = servicio.precio * num_personas * noches
            desglose.append(
                {
                    "concepto": "Entrada al parque",
                    "detalle": f"${precio_entrada} x {num_personas} persona(s) x {noches} noche(s)",
                    "subtotal": subtotal_entrada,
                }
            )
            desglose.append(
                {
                    "concepto": "Camping",
                    "detalle": f"${servicio.precio} x {num_personas} persona(s) x {noches} noche(s)",
                    "subtotal": subtotal_camping,
                }
            )
            total = subtotal_entrada + subtotal_camping
        else:  # hospedaje
            subtotal_entrada = precio_entrada * num_personas * noches
            subtotal_hospedaje = unidad.precio_por_noche * noches
            desglose.append(
                {
                    "concepto": "Entrada al parque",
                    "detalle": f"${precio_entrada} x {num_personas} persona(s) x {noches} noche(s)",
                    "subtotal": subtotal_entrada,
                }
            )
            desglose.append(
                {
                    "concepto": unidad.nombre,
                    "detalle": f"${unidad.precio_por_noche} x {noches} noche(s)",
                    "subtotal": subtotal_hospedaje,
                }
            )
            total = subtotal_entrada + subtotal_hospedaje

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
        """
        Calcula el total SIN crear nada — para que el sitio público
        pueda mostrar el precio real (con desglose) antes de que la
        persona envíe su solicitud. Hace las mismas validaciones que
        crear() (servicio activo, capacidad, disponibilidad de la
        unidad) para no cotizar algo que luego sería rechazado al
        confirmar.
        """
        _, _, noches, total, desglose = self._validar_y_calcular(
            servicio_id, tipo_reservacion, fecha_llegada, fecha_salida, unidad_hospedaje_id, num_personas
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
            raise HTTPException(
                status_code=400, detail="No se puede reservar para un cliente desactivado."
            )

        unidad, total = None, None
        _, unidad, _, total, _ = self._validar_y_calcular(
            servicio_id, tipo_reservacion, fecha_llegada, fecha_salida, unidad_hospedaje_id, num_personas
        )

        reservacion = Reservacion(
            cliente_id=cliente_id,
            servicio_id=servicio_id,
            usuario_id=usuario_id,
            unidad_hospedaje_id=unidad.id if unidad else None,
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            # Se mantiene igual a fecha_llegada por compatibilidad con
            # Reportes/Dashboard existentes — ver nota en el modelo.
            fecha_visita=fecha_llegada,
            num_personas=num_personas,
            origen=origen,
            total=total,
            monto_pagado=0,
            notas=notas,
        )

        return self.repo.crear(reservacion)

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
                detail=(
                    f"Esta reservación ya está en estado terminal "
                    f"'{reservacion.estado}' y no puede cambiar de estado."
                ),
            )

        if reservacion.estado == nuevo_estado:
            raise HTTPException(
                status_code=400, detail=f"La reservación ya está en estado '{nuevo_estado}'."
            )

        return self.repo.actualizar_estado(reservacion, nuevo_estado)

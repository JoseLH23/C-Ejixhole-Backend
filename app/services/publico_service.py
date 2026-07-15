"""
Service del portal público. A diferencia de ClienteService.crear()
(que SIEMPRE crea un cliente nuevo y solo avisa de duplicados, para
que recepción decida), aquí SÍ se reutiliza un cliente existente si
coincide teléfono o email — un mismo visitante que reserva varias
veces desde la web no debe generar un registro de Cliente distinto
cada vez.
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.reservacion import Reservacion
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje
from app.repositories.cliente_repository import ClienteRepository
from app.services.notificacion_service import notificar_nueva_reservacion_publica
from app.services.reservacion_service import ReservacionService


class PublicoService:
    def __init__(self, db: Session):
        self.db = db
        self.cliente_repo = ClienteRepository(db)
        self.reservacion_service = ReservacionService(db)

    def listar_servicios_informativos(self) -> list[Servicio]:
        return (
            self.db.query(Servicio)
            .filter(Servicio.reservable.is_(False), Servicio.activo.is_(True))
            .order_by(Servicio.nombre)
            .all()
        )

    def listar_unidades_hospedaje(self) -> list[UnidadHospedaje]:
        return (
            self.db.query(UnidadHospedaje)
            .filter(UnidadHospedaje.activa.is_(True))
            .order_by(UnidadHospedaje.nombre)
            .all()
        )

    def hay_disponibilidad(self, unidad_hospedaje_id: int, fecha_llegada: date, fecha_salida: date) -> bool:
        unidad = self.db.query(UnidadHospedaje).filter(UnidadHospedaje.id == unidad_hospedaje_id).first()
        if not unidad or not unidad.activa:
            raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada.")
        traslape = self.reservacion_service.repo.existe_traslape_unidad_hospedaje(
            unidad_hospedaje_id, fecha_llegada, fecha_salida
        )
        return not traslape

    def _buscar_o_crear_cliente(self, nombre_completo: str, email: str, telefono: str) -> Cliente:
        """
        AL-05 (auditoría de seguridad 13/jul/2026): antes se reutilizaba
        el PRIMER resultado que coincidiera por teléfono O correo — un
        teléfono compartido (familia, oficina) o un correo reciclado
        podía atribuir la reservación a la persona equivocada.

        Ahora solo se reutiliza un cliente existente si coinciden AMBOS
        datos. Una coincidencia parcial (solo teléfono o solo correo)
        NO se reutiliza en silencio — se crea un cliente nuevo para
        esta reservación, en vez de arriesgar mezclar el historial de
        dos personas distintas.
        """
        coincidencias = self.cliente_repo.buscar_por_telefono_o_email(telefono, email)
        coincidencia_segura = next(
            (c for c in coincidencias if c.telefono == telefono and c.email == email), None
        )
        if coincidencia_segura is not None:
            return coincidencia_segura

        cliente = Cliente(nombre=nombre_completo, email=email, telefono=telefono)
        return self.cliente_repo.crear(cliente)

    def _resolver_servicio_id(self, tipo_reservacion: str, unidad_hospedaje_id: int | None) -> int:
        """
        El visitante nunca manda un servicio_id — no le corresponde
        conocer ese detalle interno del catálogo. Se resuelve solo:
          - entrada  -> el servicio con categoria="entrada"
          - camping  -> el servicio con categoria="camping"
          - hospedaje -> el servicio con tipo_unidad_hospedaje igual al
                         tipo_unidad de la unidad elegida (ME-11:
                         campo real y estable, nunca el nombre visible
                         del servicio — ver migración
                         0009_servicio_tipo_hospedaje)
        """
        if tipo_reservacion == "entrada":
            categoria = "entrada"
        elif tipo_reservacion == "camping":
            categoria = "camping"
        else:  # hospedaje
            unidad = self.db.query(UnidadHospedaje).filter(UnidadHospedaje.id == unidad_hospedaje_id).first()
            if not unidad:
                raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada.")
            servicio = (
                self.db.query(Servicio)
                .filter(
                    Servicio.tipo_unidad_hospedaje == unidad.tipo_unidad,
                    Servicio.reservable.is_(True),
                )
                .first()
            )
            if not servicio:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"No hay un servicio configurado para tipo_unidad_hospedaje="
                        f"'{unidad.tipo_unidad}' en el catálogo."
                    ),
                )
            return servicio.id

        servicio = (
            self.db.query(Servicio)
            .filter(Servicio.categoria == categoria, Servicio.reservable.is_(True))
            .first()
        )
        if not servicio:
            raise HTTPException(
                status_code=500,
                detail=f"No hay un servicio con categoria='{categoria}' configurado en el catálogo.",
            )
        return servicio.id

    def cotizar(
        self,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        num_personas: int,
        unidad_hospedaje_id: int | None,
    ) -> tuple[int, Decimal, list[dict]]:
        servicio_id = self._resolver_servicio_id(tipo_reservacion, unidad_hospedaje_id)
        return self.reservacion_service.cotizar(
            servicio_id=servicio_id,
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            num_personas=num_personas,
        )

    def crear_solicitud_reservacion(
        self,
        nombre_completo: str,
        email: str,
        telefono: str,
        tipo_reservacion: str,
        fecha_llegada: date,
        fecha_salida: date,
        num_personas: int,
        unidad_hospedaje_id: int | None,
        notas: str | None,
    ) -> Reservacion:
        cliente = self._buscar_o_crear_cliente(nombre_completo, email, telefono)
        servicio_id = self._resolver_servicio_id(tipo_reservacion, unidad_hospedaje_id)

        reservacion = self.reservacion_service.crear(
            cliente_id=cliente.id,
            servicio_id=servicio_id,
            usuario_id=None,  # nadie del personal la creó
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            num_personas=num_personas,
            origen="portal",
            notas=notas,
        )

        # El correo nunca debe poder tumbar la creación — ver
        # notificacion_service.py, ya maneja sus propios errores.
        notificar_nueva_reservacion_publica(reservacion)

        return reservacion

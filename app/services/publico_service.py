"""Service del portal público."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.evento_calendario import EventoCalendario
from app.models.reservacion import ESTADOS_ACTIVOS, Reservacion
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje
from app.repositories.cliente_repository import ClienteRepository
from app.services.notificacion_service import notificar_nueva_reservacion_publica
from app.services.reservacion_service import ReservacionService
from app.services.tarifa_especial_service import TarifaEspecialService


class PublicoService:
    def __init__(self, db: Session):
        self.db = db
        self.cliente_repo = ClienteRepository(db)
        self.reservacion_service = ReservacionService(db)
        self.tarifa_service = TarifaEspecialService(db)

    def listar_servicios_informativos(self) -> list[Servicio]:
        return self.db.query(Servicio).filter(Servicio.reservable.is_(False), Servicio.activo.is_(True)).order_by(Servicio.nombre).all()

    def listar_unidades_hospedaje(self) -> list[UnidadHospedaje]:
        return self.db.query(UnidadHospedaje).filter(UnidadHospedaje.activa.is_(True)).order_by(UnidadHospedaje.nombre).all()

    def _obtener_unidad_activa(self, unidad_hospedaje_id: int) -> UnidadHospedaje:
        unidad = self.db.query(UnidadHospedaje).filter(UnidadHospedaje.id == unidad_hospedaje_id).first()
        if not unidad or not unidad.activa:
            raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada.")
        return unidad

    def hay_disponibilidad(self, unidad_hospedaje_id: int, fecha_llegada: date, fecha_salida: date) -> bool:
        self._obtener_unidad_activa(unidad_hospedaje_id)
        return not self.reservacion_service.repo.existe_traslape_unidad_hospedaje(unidad_hospedaje_id, fecha_llegada, fecha_salida)

    def listar_periodos_no_disponibles(self, unidad_hospedaje_id: int, desde: date, hasta: date) -> list[dict]:
        self._obtener_unidad_activa(unidad_hospedaje_id)
        periodos: list[dict] = []
        reservaciones = self.db.query(Reservacion).filter(
            Reservacion.unidad_hospedaje_id == unidad_hospedaje_id,
            Reservacion.estado.in_(ESTADOS_ACTIVOS),
            Reservacion.fecha_llegada <= hasta,
            Reservacion.fecha_salida > desde,
        ).all()
        for reservacion in reservaciones:
            inicio = max(reservacion.fecha_llegada, desde)
            fin = min(reservacion.fecha_salida - timedelta(days=1), hasta)
            if fin >= inicio:
                periodos.append({"fecha_inicio": inicio, "fecha_fin": fin, "motivo": "ocupado"})
        bloqueos = self.db.query(EventoCalendario).filter(
            EventoCalendario.tipo == "bloqueo",
            EventoCalendario.fecha_inicio <= hasta,
            EventoCalendario.fecha_fin >= desde,
            (EventoCalendario.unidad_hospedaje_id.is_(None)) | (EventoCalendario.unidad_hospedaje_id == unidad_hospedaje_id),
        ).all()
        for bloqueo in bloqueos:
            periodos.append({"fecha_inicio": max(bloqueo.fecha_inicio, desde), "fecha_fin": min(bloqueo.fecha_fin, hasta), "motivo": "bloqueado"})
        return sorted(periodos, key=lambda item: (item["fecha_inicio"], item["motivo"]))

    def _buscar_o_crear_cliente(self, nombre_completo: str, email: str, telefono: str) -> Cliente:
        coincidencias = self.cliente_repo.buscar_por_telefono_o_email(telefono, email)
        coincidencia_segura = next((c for c in coincidencias if c.telefono == telefono and c.email == email), None)
        if coincidencia_segura is not None:
            return coincidencia_segura
        return self.cliente_repo.crear(Cliente(nombre=nombre_completo, email=email, telefono=telefono))

    def _resolver_servicio_id(self, tipo_reservacion: str, unidad_hospedaje_id: int | None) -> int:
        if tipo_reservacion == "entrada":
            categoria = "entrada"
        elif tipo_reservacion == "camping":
            categoria = "camping"
        else:
            unidad = self._obtener_unidad_activa(unidad_hospedaje_id)  # type: ignore[arg-type]
            nombre = "Cabañas" if unidad.tipo_unidad == "cabana" else "Habitaciones"
            servicio = self.db.query(Servicio).filter(Servicio.nombre == nombre, Servicio.reservable.is_(True)).first()
            if not servicio:
                raise HTTPException(status_code=500, detail=f"No hay un servicio '{nombre}' configurado en el catálogo.")
            return servicio.id
        servicio = self.db.query(Servicio).filter(Servicio.categoria == categoria, Servicio.reservable.is_(True)).first()
        if not servicio:
            raise HTTPException(status_code=500, detail=f"No hay un servicio con categoria='{categoria}' configurado en el catálogo.")
        return servicio.id

    def _aplicar_tarifas(self, *, tipo: str, fecha_llegada: date, fecha_salida: date, unidad_hospedaje_id: int | None, total_base: Decimal, desglose: list[dict]) -> tuple[Decimal, list[dict]]:
        dias = 1 if tipo == "entrada" else (fecha_salida - fecha_llegada).days
        if dias <= 0:
            return total_base, desglose
        ajuste, lineas = self.tarifa_service.calcular_ajustes(
            tipo=tipo,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            base_diaria=total_base / Decimal(dias),
        )
        return total_base + ajuste, [*desglose, *lineas]

    def cotizar(self, tipo_reservacion: str, fecha_llegada: date, fecha_salida: date, num_personas: int, unidad_hospedaje_id: int | None) -> tuple[int, Decimal, list[dict]]:
        servicio_id = self._resolver_servicio_id(tipo_reservacion, unidad_hospedaje_id)
        noches, total_base, desglose = self.reservacion_service.cotizar(
            servicio_id=servicio_id,
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            num_personas=num_personas,
        )
        total, desglose_final = self._aplicar_tarifas(tipo=tipo_reservacion, fecha_llegada=fecha_llegada, fecha_salida=fecha_salida, unidad_hospedaje_id=unidad_hospedaje_id, total_base=total_base, desglose=desglose)
        return noches, total, desglose_final

    def crear_solicitud_reservacion(self, nombre_completo: str, email: str, telefono: str, tipo_reservacion: str, fecha_llegada: date, fecha_salida: date, num_personas: int, unidad_hospedaje_id: int | None, notas: str | None) -> Reservacion:
        cliente = self._buscar_o_crear_cliente(nombre_completo, email, telefono)
        servicio_id = self._resolver_servicio_id(tipo_reservacion, unidad_hospedaje_id)
        reservacion = self.reservacion_service.crear(
            cliente_id=cliente.id,
            servicio_id=servicio_id,
            usuario_id=None,
            tipo_reservacion=tipo_reservacion,
            fecha_llegada=fecha_llegada,
            fecha_salida=fecha_salida,
            unidad_hospedaje_id=unidad_hospedaje_id,
            num_personas=num_personas,
            origen="portal",
            notas=notas,
        )
        total_final, _ = self._aplicar_tarifas(tipo=tipo_reservacion, fecha_llegada=fecha_llegada, fecha_salida=fecha_salida, unidad_hospedaje_id=unidad_hospedaje_id, total_base=reservacion.total, desglose=[])
        if total_final != reservacion.total:
            reservacion.total = total_final
            self.db.commit()
            self.db.refresh(reservacion)
        notificar_nueva_reservacion_publica(reservacion)
        return reservacion

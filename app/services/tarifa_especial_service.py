from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.tarifa_especial import TarifaEspecial
from app.models.unidad_hospedaje import UnidadHospedaje


class TarifaEspecialService:
    def __init__(self, db: Session):
        self.db = db

    def listar(self):
        return self.db.query(TarifaEspecial).order_by(TarifaEspecial.fecha_inicio.desc(), TarifaEspecial.prioridad.desc()).all()

    def obtener(self, tarifa_id: int) -> TarifaEspecial:
        tarifa = self.db.query(TarifaEspecial).filter(TarifaEspecial.id == tarifa_id).first()
        if not tarifa:
            raise HTTPException(status_code=404, detail="Tarifa especial no encontrada")
        return tarifa

    def _validar_unidad(self, unidad_hospedaje_id: int | None):
        if unidad_hospedaje_id is None:
            return
        if not self.db.query(UnidadHospedaje).filter(UnidadHospedaje.id == unidad_hospedaje_id).first():
            raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada")

    def crear(self, **datos):
        self._validar_unidad(datos.get("unidad_hospedaje_id"))
        datos["nombre"] = datos["nombre"].strip()
        if datos.get("descripcion"):
            datos["descripcion"] = datos["descripcion"].strip() or None
        tarifa = TarifaEspecial(**datos)
        self.db.add(tarifa)
        self.db.commit()
        self.db.refresh(tarifa)
        return tarifa

    def actualizar(self, tarifa_id: int, **cambios):
        tarifa = self.obtener(tarifa_id)
        cambios = {k: v for k, v in cambios.items() if v is not None}
        self._validar_unidad(cambios.get("unidad_hospedaje_id"))
        inicio = cambios.get("fecha_inicio", tarifa.fecha_inicio)
        fin = cambios.get("fecha_fin", tarifa.fecha_fin)
        if fin < inicio:
            raise HTTPException(status_code=422, detail="fecha_fin no puede ser anterior a fecha_inicio")
        for campo, valor in cambios.items():
            setattr(tarifa, campo, valor.strip() if campo in ("nombre", "descripcion") and isinstance(valor, str) else valor)
        self.db.commit()
        self.db.refresh(tarifa)
        return tarifa

    def eliminar(self, tarifa_id: int):
        tarifa = self.obtener(tarifa_id)
        self.db.delete(tarifa)
        self.db.commit()

    def _regla_para_fecha(self, fecha: date, tipo: str, unidad_hospedaje_id: int | None):
        reglas = (
            self.db.query(TarifaEspecial)
            .filter(
                TarifaEspecial.activa.is_(True),
                TarifaEspecial.fecha_inicio <= fecha,
                TarifaEspecial.fecha_fin >= fecha,
                TarifaEspecial.aplica_a.in_(("todos", tipo)),
                or_(TarifaEspecial.unidad_hospedaje_id.is_(None), TarifaEspecial.unidad_hospedaje_id == unidad_hospedaje_id),
            )
            .order_by(TarifaEspecial.prioridad.desc(), TarifaEspecial.id.desc())
            .all()
        )
        return next((regla for regla in reglas if not regla.dias_semana or fecha.weekday() in regla.dias_semana), None)

    def calcular_ajustes(
        self,
        *,
        tipo: str,
        fecha_llegada: date,
        fecha_salida: date,
        unidad_hospedaje_id: int | None,
        base_diaria: Decimal,
    ) -> tuple[Decimal, list[dict]]:
        fechas = [fecha_llegada] if tipo == "entrada" else [fecha_llegada + timedelta(days=i) for i in range((fecha_salida - fecha_llegada).days)]
        acumulado: dict[int, dict] = {}
        total_ajuste = Decimal("0")
        for fecha in fechas:
            regla = self._regla_para_fecha(fecha, tipo, unidad_hospedaje_id)
            if not regla:
                continue
            ajuste = (base_diaria * regla.porcentaje_ajuste / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_ajuste += ajuste
            item = acumulado.setdefault(regla.id, {"regla": regla, "dias": 0, "subtotal": Decimal("0")})
            item["dias"] += 1
            item["subtotal"] += ajuste
        desglose = []
        for item in acumulado.values():
            regla = item["regla"]
            signo = "+" if regla.porcentaje_ajuste >= 0 else ""
            desglose.append({
                "concepto": regla.nombre,
                "detalle": f"{signo}{regla.porcentaje_ajuste}% x {item['dias']} día(s)",
                "subtotal": item["subtotal"],
            })
        return total_ajuste, desglose

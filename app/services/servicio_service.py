"""
Service de Servicios. Reglas de negocio; el acceso a datos se delega
a ServicioRepository.
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.reservacion import ESTADOS_ACTIVOS
from app.models.servicio import Servicio
from app.repositories.servicio_repository import ServicioRepository


class ServicioService:
    def __init__(self, db: Session):
        self.repo = ServicioRepository(db)

    def crear(
        self,
        nombre: str,
        descripcion: Optional[str],
        precio,
        duracion_minutos: Optional[int],
        capacidad_maxima: Optional[int],
        categoria: Optional[str],
    ) -> Servicio:
        servicio = Servicio(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            duracion_minutos=duracion_minutos,
            capacidad_maxima=capacidad_maxima,
            categoria=categoria,
        )
        return self.repo.crear(servicio)

    def obtener_por_id(self, servicio_id: int) -> Servicio:
        servicio = self.repo.obtener_por_id(servicio_id)
        if not servicio:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado.")
        return servicio

    def listar(
        self, solo_activos: bool = True, categoria: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> list[Servicio]:
        return self.repo.listar(solo_activos=solo_activos, categoria=categoria, limit=limit, offset=offset)

    def actualizar(self, servicio_id: int, datos: dict) -> Servicio:
        servicio = self.obtener_por_id(servicio_id)

        nueva_capacidad = datos.get("capacidad_maxima")
        if nueva_capacidad is not None:
            reservaciones_futuras_grandes = [
                r
                for r in servicio.reservaciones
                if r.estado in ESTADOS_ACTIVOS and r.num_personas > nueva_capacidad
            ]
            if reservaciones_futuras_grandes:
                ids = ", ".join(str(r.id) for r in reservaciones_futuras_grandes)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"No se puede reducir la capacidad a {nueva_capacidad}: hay "
                        f"reservaciones activas con más personas (id: {ids})."
                    ),
                )

        datos_filtrados = {k: v for k, v in datos.items() if v is not None}
        return self.repo.actualizar(servicio, datos_filtrados)

    def desactivar(self, servicio_id: int) -> Servicio:
        servicio = self.obtener_por_id(servicio_id)

        reservacion_activa = next(
            (r for r in servicio.reservaciones if r.estado in ESTADOS_ACTIVOS), None
        )
        if reservacion_activa:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"No se puede desactivar: el servicio tiene una reservación activa "
                    f"(id={reservacion_activa.id})."
                ),
            )

        return self.repo.desactivar(servicio)

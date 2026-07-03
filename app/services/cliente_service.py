"""
Service de Clientes. Aquí viven las reglas de negocio; el acceso a
datos se delega siempre a ClienteRepository.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.repositories.cliente_repository import ClienteRepository


class ClienteService:
    def __init__(self, db: Session):
        self.repo = ClienteRepository(db)

    def crear(
        self,
        nombre: str,
        apellido: str | None,
        telefono: str | None,
        email: str | None,
        notas: str | None,
    ) -> tuple[Cliente, list[Cliente]]:
        """
        Regla de negocio: duplicado se dispara si coincide teléfono O
        email con un cliente ya existente. No se bloquea la creación
        (dos personas pueden compartir un teléfono de casa) — solo se
        alerta para que recepción decida si es la misma persona.
        """
        duplicados = self.repo.buscar_por_telefono_o_email(telefono, email)

        cliente = Cliente(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
            email=email,
            notas=notas,
        )
        cliente = self.repo.crear(cliente)

        return cliente, duplicados

    def obtener_por_id(self, cliente_id: int) -> Cliente:
        cliente = self.repo.obtener_por_id(cliente_id)
        if not cliente:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")
        return cliente

    def listar(self, solo_activos: bool = True, limit: int = 100, offset: int = 0) -> list[Cliente]:
        return self.repo.listar(solo_activos=solo_activos, limit=limit, offset=offset)

    def actualizar(self, cliente_id: int, datos: dict) -> Cliente:
        cliente = self.obtener_por_id(cliente_id)

        # Si se está cambiando teléfono o email, revalidamos duplicados
        # contra otros clientes (excluyendo al propio).
        nuevo_telefono = datos.get("telefono", cliente.telefono)
        nuevo_email = datos.get("email", cliente.email)
        if "telefono" in datos or "email" in datos:
            duplicados = [
                c
                for c in self.repo.buscar_por_telefono_o_email(nuevo_telefono, nuevo_email)
                if c.id != cliente_id
            ]
            if duplicados:
                ids = ", ".join(str(c.id) for c in duplicados)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"El nuevo teléfono/email coincide con otro(s) cliente(s) "
                        f"existente(s) (id: {ids}). Verifica antes de guardar."
                    ),
                )

        datos_filtrados = {k: v for k, v in datos.items() if v is not None}
        return self.repo.actualizar(cliente, datos_filtrados)

    def desactivar(self, cliente_id: int) -> Cliente:
        cliente = self.obtener_por_id(cliente_id)

        reservacion_activa = next(
            (r for r in cliente.reservaciones if r.estado in ("pendiente", "confirmada")), None
        )
        if reservacion_activa:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"No se puede desactivar: el cliente tiene una reservación activa "
                    f"(id={reservacion_activa.id})."
                ),
            )

        return self.repo.desactivar(cliente)

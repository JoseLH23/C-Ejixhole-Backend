"""Carga mínima y segura para la prueba E2E del ecosistema completo.

Solo puede ejecutarse cuando ENVIRONMENT=e2e. La base debe ser desechable.
No usa credenciales reales ni envía correos.
"""
from __future__ import annotations

import os
from decimal import Decimal

from app.core.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.servicio import Servicio
from app.models.usuario import Rol, Usuario

ROLES = ("admin", "operador", "cajero")


def _obligatoria(nombre: str) -> str:
    valor = os.getenv(nombre, "").strip()
    if not valor:
        raise RuntimeError(f"Falta la variable obligatoria {nombre}.")
    return valor


def main() -> None:
    if settings.ENVIRONMENT != "e2e":
        raise RuntimeError(
            "scripts.seed_e2e solo puede ejecutarse con ENVIRONMENT=e2e "
            "y una base PostgreSQL desechable."
        )

    email = _obligatoria("E2E_ADMIN_EMAIL").lower()
    password = _obligatoria("E2E_ADMIN_PASSWORD")
    nombre = os.getenv("E2E_ADMIN_NAME", "Administración E2E").strip() or "Administración E2E"

    db = SessionLocal()
    try:
        for nombre_rol in ROLES:
            rol = db.query(Rol).filter(Rol.nombre == nombre_rol).first()
            if not rol:
                db.add(Rol(nombre=nombre_rol, descripcion=f"Rol {nombre_rol}"))
        db.flush()

        rol_admin = db.query(Rol).filter(Rol.nombre == "admin").one()
        admin = db.query(Usuario).filter(Usuario.email == email).first()
        if admin:
            admin.nombre = nombre
            admin.password_hash = hash_password(password)
            admin.rol_id = rol_admin.id
            admin.activo = True
        else:
            db.add(
                Usuario(
                    nombre=nombre,
                    email=email,
                    password_hash=hash_password(password),
                    rol_id=rol_admin.id,
                    activo=True,
                )
            )

        entrada = (
            db.query(Servicio)
            .filter(Servicio.categoria == "entrada", Servicio.reservable.is_(True))
            .first()
        )
        if entrada:
            entrada.nombre = "Acceso al parque"
            entrada.precio = Decimal("50.00")
            entrada.activo = True
            entrada.reservable = True
        else:
            db.add(
                Servicio(
                    nombre="Acceso al parque",
                    descripcion="Servicio temporal para prueba E2E.",
                    precio=Decimal("50.00"),
                    categoria="entrada",
                    reservable=True,
                    activo=True,
                )
            )

        db.commit()
        print(f"Seed E2E listo: admin={email}, entrada=$50.00")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""
Crea el primer usuario admin del sistema. Necesario una sola vez,
porque POST /auth/usuarios exige rol admin y al inicio la tabla
usuarios está vacía (nadie puede pasar esa protección todavía).

Uso (desde la raíz del proyecto, con tu venv activado y tu .env
apuntando a tu Postgres real):

    python -m scripts.create_admin
"""
from app.database import SessionLocal
from app.core.security import hash_password
from app.models.usuario import Rol, Usuario

ROLES_BASE = ("admin", "operador", "cajero")


def main():
    db = SessionLocal()
    try:
        for nombre_rol in ROLES_BASE:
            existente = db.query(Rol).filter(Rol.nombre == nombre_rol).first()
            if not existente:
                db.add(Rol(nombre=nombre_rol, descripcion=f"Rol {nombre_rol}"))
        db.commit()

        rol_admin = db.query(Rol).filter(Rol.nombre == "admin").first()

        email = input("Email del admin: ").strip()
        if db.query(Usuario).filter(Usuario.email == email).first():
            print(f"Ya existe un usuario con el email {email}. Nada que hacer.")
            return

        nombre = input("Nombre: ").strip()
        password = input("Password: ").strip()

        usuario = Usuario(
            nombre=nombre,
            email=email,
            password_hash=hash_password(password),
            rol_id=rol_admin.id,
        )
        db.add(usuario)
        db.commit()
        print(f"Usuario admin '{email}' creado correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

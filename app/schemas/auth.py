from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    rol_id: int


class UsuarioRolUpdate(BaseModel):
    rol_id: int


class UsuarioPasswordReset(BaseModel):
    """Contraseña temporal/nueva definida por un administrador."""

    nueva_password: str = Field(min_length=8, max_length=128)

    @field_validator("nueva_password")
    @classmethod
    def validar_password_util(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La contraseña no puede contener solo espacios.")
        return value


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    activo: bool
    # Se agrega para GET /auth/me (Fase 1: nombre y rol reales en el
    # frontend, sin depender solo del JWT). Reutiliza este mismo schema
    # en vez de crear uno nuevo — también lo devuelve POST /auth/usuarios.
    rol: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("rol", mode="before")
    @classmethod
    def _rol_a_nombre(cls, v):
        """`usuario.rol` es la relación SQLAlchemy hacia Rol, no un string
        — aquí se extrae `.nombre`. Si ya llega como string (ej. en un
        test que construye el schema directo), se deja igual."""
        return v.nombre if hasattr(v, "nombre") else v


class RolOut(BaseModel):
    """Para GET /usuarios/roles — poblar el selector de rol real al
    crear un usuario, sin hardcodear la lista en el frontend."""
    id: int
    nombre: str
    descripcion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

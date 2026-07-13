from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


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

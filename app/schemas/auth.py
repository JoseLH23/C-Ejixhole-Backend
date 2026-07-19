from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    session_managed: bool = True


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
    rol: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("rol", mode="before")
    @classmethod
    def _rol_a_nombre(cls, v):
        return v.nombre if hasattr(v, "nombre") else v


class RolOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

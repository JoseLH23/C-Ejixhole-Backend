from pydantic import BaseModel, EmailStr, field_validator


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

    class Config:
        from_attributes = True

    @field_validator("rol", mode="before")
    @classmethod
    def _rol_a_nombre(cls, v):
        """`usuario.rol` es la relación SQLAlchemy hacia Rol, no un string
        — aquí se extrae `.nombre`. Si ya llega como string (ej. en un
        test que construye el schema directo), se deja igual."""
        return v.nombre if hasattr(v, "nombre") else v

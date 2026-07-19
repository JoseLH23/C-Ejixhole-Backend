import os


JWT_ISSUER = os.getenv("JWT_ISSUER", "ejixhole-backend").strip()
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "ejixhole-admin").strip()
AUTH_SESSION_MAX_PER_USER = max(1, int(os.getenv("AUTH_SESSION_MAX_PER_USER", "5")))
AUTH_SESSION_TOUCH_MINUTES = max(1, int(os.getenv("AUTH_SESSION_TOUCH_MINUTES", "5")))

if not JWT_ISSUER:
    raise RuntimeError("JWT_ISSUER no puede estar vacío")
if not JWT_AUDIENCE:
    raise RuntimeError("JWT_AUDIENCE no puede estar vacío")

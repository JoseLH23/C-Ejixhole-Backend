from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.session_config import AUTH_SESSION_MAX_PER_USER, AUTH_SESSION_TOUCH_MINUTES
from app.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear(
        self,
        *,
        jti: str,
        usuario_id: int,
        issued_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        session = AuthSession(
            jti=jti,
            usuario_id=usuario_id,
            issued_at=issued_at,
            expires_at=expires_at,
            last_seen_at=issued_at,
        )
        self.db.add(session)
        self.db.flush()

        activas = (
            self.db.query(AuthSession)
            .filter(
                AuthSession.usuario_id == usuario_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > issued_at,
            )
            .order_by(AuthSession.issued_at.desc(), AuthSession.id.desc())
            .all()
        )
        for anterior in activas[AUTH_SESSION_MAX_PER_USER:]:
            anterior.revoked_at = issued_at
            anterior.revoke_reason = "session_limit"

        self.db.commit()
        self.db.refresh(session)
        return session

    def obtener_vigente(self, jti: str, *, ahora: datetime | None = None) -> AuthSession | None:
        ahora = ahora or datetime.now(timezone.utc)
        return (
            self.db.query(AuthSession)
            .filter(
                AuthSession.jti == jti,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > ahora,
            )
            .first()
        )

    def tocar(self, session: AuthSession, *, ahora: datetime | None = None) -> None:
        ahora = ahora or datetime.now(timezone.utc)
        ultima = session.last_seen_at
        if ultima is not None and ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)
        if ultima is not None and ahora - ultima < timedelta(minutes=AUTH_SESSION_TOUCH_MINUTES):
            return
        session.last_seen_at = ahora
        self.db.commit()

    def revocar(self, session_id: int, *, reason: str, commit: bool = True) -> AuthSession | None:
        session = self.db.query(AuthSession).filter(AuthSession.id == session_id).first()
        if session is None:
            return None
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            session.revoke_reason = reason[:120]
            if commit:
                self.db.commit()
                self.db.refresh(session)
            else:
                self.db.flush()
        return session

    def revocar_usuario(self, usuario_id: int, *, reason: str, commit: bool = True) -> int:
        ahora = datetime.now(timezone.utc)
        sessions = (
            self.db.query(AuthSession)
            .filter(AuthSession.usuario_id == usuario_id, AuthSession.revoked_at.is_(None))
            .all()
        )
        for session in sessions:
            session.revoked_at = ahora
            session.revoke_reason = reason[:120]
        if sessions:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
        return len(sessions)

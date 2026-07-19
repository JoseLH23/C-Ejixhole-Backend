from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, func

from app.database import Base


class PublicSubmissionAttempt(Base):
    __tablename__ = "public_submission_attempts"
    __table_args__ = (
        Index("ix_public_attempt_ip_created", "ip_hash", "created_at"),
        Index("ix_public_attempt_contact_created", "contact_hash", "created_at"),
        Index("ix_public_attempt_client_created", "client_hash", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    ip_hash = Column(String(64), nullable=False, index=True)
    contact_hash = Column(String(64), nullable=True, index=True)
    client_hash = Column(String(64), nullable=True, index=True)
    nonce_hash = Column(String(64), nullable=True)
    allowed = Column(Boolean, nullable=False, default=False)
    mode = Column(String(20), nullable=False)
    reason = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

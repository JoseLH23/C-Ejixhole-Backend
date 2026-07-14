"""
AL-04 (auditoría de seguridad 13/jul/2026): idempotencia real contra
doble clic / doble envío.

Diseño (patrón "reservar primero", el mismo que usa Stripe): antes de
ejecutar la operación real, se intenta INSERTAR la clave con un
constraint UNIQUE(clave, endpoint) real en la base de datos. Esto es
lo que de verdad cierra la condición de carrera de dos clics
CASI SIMULTÁNEOS (no solo dos clics uno después del otro) — un
`SELECT` primero y un `INSERT` después, sin la reserva atómica, deja
una ventana real donde ambos requests pasan la validación antes de que
ninguno termine.

Completamente opt-in: si el cliente no manda el header
`Idempotency-Key`, esta función simplemente ejecuta la operación tal
cual, sin ningún cambio de comportamiento — así los flujos actuales
(y cualquier integración vieja) siguen funcionando exactamente igual.
"""
import hashlib
import json
from typing import Type

from fastapi import HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency_key import IdempotencyKey


def _hash_del_cuerpo(cuerpo: BaseModel) -> str:
    return hashlib.sha256(cuerpo.model_dump_json().encode("utf-8")).hexdigest()


def ejecutar_con_idempotencia(
    db: Session, request: Request, endpoint: str, cuerpo: BaseModel, operacion, schema_salida: Type[BaseModel]
):
    """
    `operacion`: callable sin argumentos que ejecuta la acción real
    (ej. `lambda: service.crear(...)`) y devuelve el resultado (un
    modelo de SQLAlchemy, tal como ya devuelven los services reales).

    `schema_salida`: el mismo Pydantic response_model que ya declara
    la ruta (ej. ReservacionOut). Es necesario para serializar el
    resultado guardado — usar jsonable_encoder() directo sobre el
    objeto de SQLAlchemy pierde propiedades calculadas (ej.
    `saldo_actual`, `saldo_pendiente`) que no son columnas reales; el
    schema real, vía from_attributes, sí las captura igual que hace
    FastAPI normalmente al serializar la respuesta.
    """
    clave = request.headers.get("idempotency-key")  # los headers HTTP no distinguen mayúsculas
    if not clave:
        return operacion()

    hash_actual = _hash_del_cuerpo(cuerpo)

    # Paso 1: reservar la clave ANTES de tocar nada real. Si esto
    # falla por el UNIQUE constraint, alguien más (una request
    # anterior, o una gemela que llegó casi al mismo tiempo) ya la
    # reservó — no se ejecuta la operación real una segunda vez.
    reserva = IdempotencyKey(clave=clave, endpoint=endpoint, request_hash=hash_actual, response_body=None)
    db.add(reserva)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existente = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.clave == clave, IdempotencyKey.endpoint == endpoint)
            .first()
        )
        if existente.request_hash != hash_actual:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta Idempotency-Key ya se usó con datos distintos — usa una clave nueva para una solicitud distinta.",
            )
        if existente.response_body is None:
            # La otra request (secuencial o concurrente) todavía no
            # termina — nunca se arriesga una segunda ejecución real.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta solicitud ya se está procesando. Espera unos segundos antes de reintentar.",
            )
        return json.loads(existente.response_body)

    # Paso 2: se ganó la reserva sin competencia — ahora sí se ejecuta
    # la operación real.
    try:
        resultado = operacion()
    except Exception:
        # Si la operación real falla (validación de negocio, etc.), se
        # libera la clave — un reintento legítimo con la MISMA clave
        # debe poder funcionar después, no quedarse atascado para
        # siempre en "en curso".
        db.query(IdempotencyKey).filter(
            IdempotencyKey.clave == clave, IdempotencyKey.endpoint == endpoint
        ).delete()
        db.commit()
        raise

    cuerpo_serializado = schema_salida.model_validate(resultado).model_dump_json()
    db.query(IdempotencyKey).filter(IdempotencyKey.clave == clave, IdempotencyKey.endpoint == endpoint).update(
        {"response_body": cuerpo_serializado}
    )
    db.commit()

    return resultado

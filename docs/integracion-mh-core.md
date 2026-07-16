# Integración inicial EjiXhole → MH-Core

## Alcance

EjiXhole publica una única vista agregada y de solo lectura:

```text
GET /api/v1/integrations/mh-core/operational-summary
X-MH-Service-Key: <credencial exclusiva>
```

La respuesta incluye ingresos agregados, reservaciones activas, próximas visitas,
saldo pendiente, cancelación, ocupación y diferencia de caja. No incluye nombres,
correos, teléfonos, observaciones, folios individuales ni registros de clientes.

## Seguridad

- La credencial es `MH_CORE_SERVICE_KEY` y debe tener al menos 32 caracteres.
- Debe ser distinta de `JWT_SECRET_KEY` y de la clave que protege al propio MH-Core.
- Sin credencial configurada, el endpoint responde `503` y permanece cerrado.
- Una credencial incorrecta responde `401`.
- El alcance fijo es `ejixhole:read:operations`.
- No existen métodos POST, PUT, PATCH o DELETE para esta integración.
- La ruta solo existe bajo `/api/v1`; no se creó una versión legacy.

Generación recomendada:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

La misma clave se configura en EjiXhole como `MH_CORE_SERVICE_KEY` y en MH-Core
como `EJIXHOLE_SERVICE_KEY`. Nunca debe guardarse en Git.

## Arquitectura

MH-Core consume la API HTTP versionada. No recibe acceso a PostgreSQL, no comparte
la sesión administrativa y no puede modificar reservaciones, pagos o caja.

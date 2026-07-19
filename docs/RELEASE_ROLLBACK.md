# Release y rollback del Backend

## Gate previo

1. El manifiesto debe validar y la etiqueta `vX.Y.Z` debe coincidir con su versión.
2. CI, E2E, seguridad y suite completa deben estar verdes.
3. `alembic heads` debe mostrar el head esperado y sin ramas accidentales.
4. La compatibilidad central del ecosistema debe aprobar los contratos.
5. Debe existir un respaldo verificable antes de migraciones con datos.

## Orden de despliegue

1. Aplicar solo migraciones compatibles hacia atrás.
2. Desplegar backend.
3. Ejecutar smoke tests de health, readiness y versión.
4. Desplegar panel y portal compatibles.
5. Observar errores, latencia, eventos y auditoría.

## Rollback

- Revertir aplicación únicamente cuando la versión anterior sea compatible con el esquema actual.
- No ejecutar downgrade destructivo sin respaldo probado y revisión humana.
- Si el esquema no es compatible, desplegar una corrección hacia adelante.
- Conservar commit, etiqueta, evidencia, head de Alembic y resultados del smoke test.

## Cierre

El release se considera estable cuando readiness está operativo, la versión publicada coincide con el manifiesto, no aumentan errores 5xx, no hay duplicados y el canal de eventos continúa procesando.

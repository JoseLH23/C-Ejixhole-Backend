# Contribuir a C-Ejixhole-Backend

## Flujo obligatorio

1. Crear una rama desde `main`.
2. Mantener un objetivo principal por cambio.
3. Implementar reglas de negocio en servicios y consistencia crítica en PostgreSQL.
4. Añadir o actualizar pruebas.
5. Abrir un pull request usando la plantilla.
6. Esperar a que todos los checks estén verdes.
7. Verificar migraciones, despliegue y rollback cuando aplique.

## Nombres de ramas

- `feat/...` para funciones.
- `fix/...` para correcciones.
- `security/...` para endurecimiento.
- `docs/...` para documentación.
- `cto/...` para bloques coordinados del roadmap.

## Reglas técnicas

- No subir `.env`, credenciales, respaldos ni datos personales.
- No confiar en validaciones exclusivas del frontend.
- Toda operación crítica reintentable debe considerar idempotencia.
- Las migraciones deben soportar `upgrade`, `downgrade` y reaplicación en PostgreSQL.
- Las APIs nuevas deben vivir bajo el contrato versionado.
- Los cambios incompatibles requieren estrategia de transición.

## Comandos mínimos

```powershell
$env:PYTHONPATH = "."
pytest -q
alembic upgrade head
```

La definición completa de terminado incluye pruebas, CI verde, manejo de errores, documentación, verificación del ambiente y una forma de rollback cuando corresponda.

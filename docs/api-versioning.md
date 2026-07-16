# Versionado de la API

## Contrato actual

La versión estable de negocio es:

```text
/api/v1
```

Ejemplos:

```text
POST /api/v1/auth/login
GET  /api/v1/reservaciones
POST /api/v1/pagos
GET  /api/v1/publico/servicios
```

Los endpoints de infraestructura permanecen sin versión:

```text
GET /health/live
GET /health/ready
GET /status
```

## Compatibilidad temporal

Las rutas históricas sin `/api/v1` continúan funcionando para evitar una
interrupción durante la migración del panel, portal, scripts y futuras
integraciones.

Una respuesta de ruta histórica incluye:

```text
X-API-Version: legacy
Deprecation: true
Link: </api/v1/...>; rel="successor-version"
```

La misma operación bajo `/api/v1` devuelve:

```text
X-API-Version: v1
```

No se ha fijado todavía una fecha de retiro de las rutas históricas. Primero se
debe verificar que todos los clientes usan v1 y que el piloto de producción ha
terminado correctamente.

## Reglas para cambios futuros

- Los cambios compatibles se incorporan dentro de `/api/v1`.
- Un cambio que rompa contratos requiere una nueva versión mayor, por ejemplo
  `/api/v2`.
- No se elimina ni cambia el significado de un campo publicado sin una etapa de
  migración documentada.
- MH-Core y nuevas aplicaciones deben comenzar directamente con `/api/v1`.
- Health checks no dependen de una versión de negocio.

## Migración de clientes

1. Cambiar la URL base al prefijo `/api/v1`.
2. Ejecutar pruebas unitarias y E2E.
3. Confirmar que no aparecen respuestas con `X-API-Version: legacy`.
4. Ejecutar el checklist y piloto de producción.
5. Mantener las rutas históricas hasta completar el inventario de consumidores.

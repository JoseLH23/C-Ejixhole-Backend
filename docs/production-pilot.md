# Checklist de producción y piloto operativo controlado

## Objetivo

Comprobar que EjiXhole puede operar de extremo a extremo en producción sin improvisar y con un plan claro de reversión.

## Estado previo obligatorio

Antes de ejecutar el piloto real deben cumplirse todos estos puntos:

- Backend CI, migraciones PostgreSQL y restauración de respaldo en verde.
- Prueba E2E temporal completa en verde.
- Backend `/health/ready` con base de datos disponible y correo configurado.
- Portal público y panel administrativo respondiendo.
- Última versión del panel desplegada en Vercel.
- Cuenta exclusiva o autorizada para el piloto con rol `admin`.
- Ninguna caja abierta para esa cuenta.
- Monitoreo de GitHub Actions e Issues activo.
- Momento sin atención activa a visitantes.

## Verificación no destructiva

```powershell
python -m scripts.production_pilot
```

Este modo es el predeterminado. Solo consulta:

- backend y PostgreSQL;
- configuración de notificaciones;
- portal público;
- panel administrativo;
- catálogo público.

No inicia sesión ni crea datos.

## Piloto real

El workflow `Checklist y piloto de producción` permite elegir `full-pilot`.
La ejecución exige:

1. escribir exactamente `EJECUTAR_PILOTO_REAL`;
2. tener los secrets `PILOT_ADMIN_EMAIL` y `PILOT_ADMIN_PASSWORD`;
3. aprobar el environment `production-pilot`, cuando tenga protección configurada.

El recorrido crea datos claramente marcados como prueba:

```text
Solicitud pública de 1 entrada
→ login por cookie HttpOnly
→ apertura de caja en $0
→ aceptación
→ pago completo en efectivo
→ movimiento automático de caja
→ check-in
→ check-out
→ visita completada
→ cierre de caja sin diferencia
→ logout
```

La persona ficticia se llama `PILOTO CONTROLADO <run-id>`, usa un correo de `example.com` y las notas indican que no debe contactarse ni atenderse como cliente real.

## Guardas de seguridad

- El modo real permanece apagado por defecto.
- La confirmación debe coincidir exactamente.
- Las credenciales solo llegan mediante secrets y nunca se imprimen.
- Si la cuenta ya tiene una caja abierta, el piloto se aborta.
- Cada operación idempotente usa una clave estable por ejecución.
- No se eliminan registros ni se realizan compensaciones destructivas automáticas.
- El reporte guarda únicamente IDs técnicos y resultado.

## Criterios de aprobación

El piloto se considera aprobado únicamente si:

- las tres aplicaciones responden;
- PostgreSQL y correo están configurados;
- el login genera cookie `HttpOnly` y cookie CSRF;
- la reservación queda `completada`;
- el saldo pendiente queda en cero;
- el pago aparece como ingreso de caja;
- la caja del piloto queda cerrada;
- no aparece una alerta nueva de producción.

## Plan de reversión

### Antes de crear datos

Si falla disponibilidad, despliegue, login o credenciales, no se modifica producción. Se corrige el despliegue y se repite primero el modo `readiness`.

### Después de crear la reservación y antes del pago

- No eliminar la reservación.
- Mantenerla identificada con sus notas de piloto.
- Un administrador puede cancelarla desde el panel si todavía no inició la visita.
- Registrar el ID exacto en el acta del piloto.

### Después del pago

- No editar montos directamente en PostgreSQL.
- Usar el flujo de reembolso del sistema si se requiere reversión contable.
- Confirmar que el reembolso produzca el egreso correspondiente en una caja abierta.

### Después del check-in

- No cambiar el estado manualmente en base de datos.
- Corregir la causa y continuar con check-out cuando el saldo sea cero.
- Si existe un defecto que impide continuar, conservar los IDs y abrir un incidente técnico.

### Despliegue defectuoso

1. detener nuevas operaciones administrativas;
2. conservar el backend y la base sin migraciones manuales;
3. revertir el commit del frontend o backend mediante un PR;
4. confirmar CI y E2E temporal;
5. volver a desplegar;
6. ejecutar `readiness` antes de reabrir el panel.

Las migraciones solo se revierten con el procedimiento documentado y después de un respaldo verificado. Nunca se ejecuta un `downgrade` directamente por intuición en producción.

## Acta mínima

Cada piloto debe registrar:

- fecha y hora;
- commit de backend, panel y portal;
- resultado de readiness;
- ID de reservación;
- ID de caja;
- total cobrado;
- resultado de correo y monitoreo;
- incidentes encontrados;
- decisión: aprobar, corregir o revertir.

## Estado del 16 de julio de 2026

- Backend, migraciones, respaldo/restauración y E2E temporal: verificados en CI.
- Sesión HttpOnly: verificada en navegador con PostgreSQL temporal.
- Despliegue del panel con la sesión nueva: pendiente porque Vercel alcanzó el límite diario gratuito de despliegues.
- Piloto real sobre producción: bloqueado deliberadamente hasta que el panel nuevo esté desplegado y el modo `readiness` confirme las tres piezas.

No se considera una falla funcional del producto; es un bloqueo de publicación. Ejecutar un piloto con la versión anterior del panel no validaría la migración de seguridad recién realizada.

# Prueba E2E del sistema completo

La prueba levanta un entorno desechable con PostgreSQL 17, el backend FastAPI, el portal público, el panel administrativo y Chromium mediante Playwright.

## Recorrido comprobado

```text
Solicitud pública
→ backend
→ inicio de sesión administrativo
→ apertura de caja
→ aceptación de solicitud
→ pago en efectivo
→ movimiento automático de caja
→ check-in
→ check-out
→ visita completada
```

No usa Render, Neon, Vercel, Resend ni información real.

## Ejecución

El workflow `.github/workflows/e2e-system.yml` se ejecuta manualmente, una vez al día y ante cambios relevantes del backend o de la propia prueba. Los frontends se descargan desde sus ramas `main` para comprobar la compatibilidad real entre los tres repositorios.

## Evidencias

Ante un fallo se conservan durante 14 días el reporte HTML, la traza, capturas o video y los logs de los tres servicios.

## Protección del seed

`scripts/seed_e2e.py` se niega a ejecutarse salvo que `ENVIRONMENT=e2e`. Debe utilizarse exclusivamente con una base desechable.

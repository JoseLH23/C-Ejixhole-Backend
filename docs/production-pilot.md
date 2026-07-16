# Preparación para piloto de producción

## Verificación automática

Ejecuta:

```powershell
python -m scripts.production_pilot
```

El comando valida sin modificar datos:

- backend y PostgreSQL;
- configuración de notificaciones;
- portal público;
- panel administrativo;
- catálogo y disponibilidad pública.

El workflow `Preparación para piloto de producción` ejecuta la misma revisión con reintentos y conserva un reporte.

## Requisitos antes del piloto manual

- CI, migraciones, restauración de respaldo y E2E en verde.
- Últimas versiones realmente desplegadas.
- Monitoreo activo.
- Una persona autorizada presente.
- Un horario sin operación activa.

## Recorrido manual controlado

La persona autorizada debe comprobar desde las interfaces:

1. solicitud pública claramente marcada como prueba;
2. recepción del aviso;
3. inicio y restauración de sesión administrativa;
4. reservación, caja y pago;
5. check-in y check-out;
6. saldo final en cero;
7. cierre de sesión;
8. ausencia de alertas nuevas.

No deben usarse datos de clientes reales. El registro debe identificarse como `PILOTO CONTROLADO — NO CONTACTAR`.

## Plan de reversión

- Antes de guardar datos: detener el piloto y corregir el despliegue.
- Reservación sin pago: cancelarla desde el flujo normal y conservar el folio en el acta.
- Pago registrado: usar el procedimiento de reembolso; nunca editar montos en la base.
- Visita iniciada: no cambiar estados manualmente en PostgreSQL; corregir la causa y continuar por las acciones normales.
- Despliegue defectuoso: revertir mediante PR, validar CI y repetir la verificación automática.
- Migraciones: solo después de respaldo verificado y usando el procedimiento documentado.

## Acta mínima

Registrar fecha, commits desplegados, folio de prueba, sesión de caja, total, resultado del aviso, monitoreo, incidentes y decisión final.

## Estado del 16 de julio de 2026

La base técnica y la sesión HttpOnly están verificadas en CI y E2E temporal. El despliegue nuevo del panel permanece pendiente por el límite diario gratuito de Vercel. Por esa razón, el piloto manual de producción queda en espera: realizarlo sobre la versión anterior no validaría la mejora recién terminada.

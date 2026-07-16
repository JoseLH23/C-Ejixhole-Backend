import { expect, test } from "@playwright/test";

const PORTAL_URL = process.env.PORTAL_URL ?? "http://127.0.0.1:5174";
const ADMIN_URL = process.env.ADMIN_URL ?? "http://127.0.0.1:5173";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin.e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2E-Password-2026!";

function escaparRegex(texto) {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function fechaLocalMasDias(dias) {
  const fecha = new Date();
  fecha.setHours(12, 0, 0, 0);
  fecha.setDate(fecha.getDate() + dias);
  return fecha;
}

function etiquetaFecha(fecha) {
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(fecha);
}

test("portal → backend → panel → caja → pago → check-in → check-out", async ({ browser }) => {
  const marca = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const nombreCliente = `Cliente E2E ${marca}`;
  const emailCliente = `e2e.${marca}@example.com`;
  const fechaVisita = fechaLocalMasDias(1);

  const contexto = await browser.newContext({ locale: "es-MX", timezoneId: "America/Mexico_City" });
  const portal = await contexto.newPage();

  await test.step("el visitante crea una solicitud pública real", async () => {
    await portal.goto(`${PORTAL_URL}/reservar`);
    await expect(portal.getByRole("button", { name: /Entrada/i })).toBeVisible();

    await portal.getByRole("button", { name: /Entrada/i }).click();
    await portal.getByRole("button", { name: /^Fecha de visita$/i }).click();

    const dialogoCalendario = portal.getByRole("dialog", { name: /^Fecha de visita$/i });
    await expect(dialogoCalendario).toBeVisible();
    await dialogoCalendario
      .getByRole("button", { name: new RegExp(`^${escaparRegex(etiquetaFecha(fechaVisita))}$`, "i") })
      .click();

    await portal.getByRole("spinbutton").fill("2");
    await expect(portal.getByText("$100.00", { exact: true }).last()).toBeVisible();
    await portal.getByRole("button", { name: /Continuar/i }).click();

    const formulario = portal.locator("form");
    const entradas = formulario.locator("input");
    await entradas.nth(0).fill(nombreCliente);
    await formulario.locator('input[type="email"]').fill(emailCliente);
    await entradas.nth(2).fill("4441234567");
    await formulario.locator("textarea").fill("Flujo automático controlado; no es una reservación real.");

    const solicitud = portal.waitForResponse(
      (respuesta) =>
        respuesta.url().endsWith("/publico/reservaciones") &&
        respuesta.request().method() === "POST"
    );
    await portal.getByRole("button", { name: /Enviar solicitud/i }).click();
    const respuestaSolicitud = await solicitud;
    expect(respuestaSolicitud.status()).toBe(201);

    await expect(portal.getByRole("heading", { name: /Solicitud recibida/i })).toBeVisible();
    await expect(portal.getByText("$100.00", { exact: true }).last()).toBeVisible();
  });

  const textoFolio = await portal.getByText(/Folio:\s*#\d+/i).textContent();
  const coincidenciaFolio = textoFolio?.match(/#(\d+)/);
  expect(coincidenciaFolio, "La confirmación debe mostrar un folio numérico").not.toBeNull();
  const folio = coincidenciaFolio[1];

  const admin = await contexto.newPage();
  await test.step("el administrador inicia sesión y abre caja", async () => {
    await admin.goto(`${ADMIN_URL}/login`);
    await admin.getByLabel("Email").fill(ADMIN_EMAIL);
    await admin.getByLabel("Contraseña").fill(ADMIN_PASSWORD);
    await admin.getByRole("button", { name: /Iniciar sesión/i }).click();
    await expect(admin).toHaveURL(new RegExp(`${escaparRegex(ADMIN_URL)}/?$`));

    await admin.goto(`${ADMIN_URL}/caja`);
    await expect(admin.getByRole("heading", { name: "Caja", exact: true })).toBeVisible();
    await expect(admin.getByText("No tienes una caja abierta", { exact: true })).toBeVisible();

    await admin.getByRole("button", { name: "Abrir caja", exact: true }).click();
    const dialogo = admin.getByRole("dialog");
    await dialogo.getByLabel(/Monto de apertura/i).fill("500.00");
    await dialogo.getByRole("button", { name: "Abrir caja", exact: true }).click();
    await expect(admin.getByText("Caja abierta", { exact: true })).toBeVisible();
    await expect(admin.getByText(/Sesión #\d+/)).toBeVisible();
  });

  await test.step("acepta, cobra, registra llegada y completa la visita", async () => {
    await admin.goto(`${ADMIN_URL}/reservaciones`);
    await expect(admin.getByRole("heading", { name: "Reservaciones", exact: true })).toBeVisible();

    await admin.getByPlaceholder(/Buscar por folio, cliente/i).fill(nombreCliente);
    const fila = admin.getByRole("row").filter({ hasText: nombreCliente });
    await expect(fila).toBeVisible();
    await expect(fila).toContainText(`#${folio}`);

    await fila.getByRole("button", { name: "Aceptar", exact: true }).click();
    await expect(admin.getByText("Solicitud aceptada", { exact: true })).toBeVisible();
    await expect(fila).toContainText("Confirmada");

    await fila.getByRole("button", { name: "Pagos", exact: true }).click();
    const pagos = admin.getByRole("dialog");
    await expect(pagos.getByText(new RegExp(`Pagos — Reservación #${folio}`))).toBeVisible();

    await pagos.getByRole("combobox").first().click();
    await admin.getByRole("option", { name: "Pago completo", exact: true }).click();
    await pagos.getByLabel(/Monto \(MXN\)/i).fill("100.00");
    await pagos.getByRole("button", { name: "Registrar pago", exact: true }).click();
    await expect(admin.getByText("Pago registrado", { exact: true })).toBeVisible();
    await expect(pagos.getByText("$100.00", { exact: true }).first()).toBeVisible();
    await pagos.getByRole("button", { name: "Cerrar", exact: true }).click();

    await expect(fila).toContainText("$0.00");
    await fila.getByRole("button", { name: "Check-in", exact: true }).click();
    await expect(admin.getByText("Check-in registrado", { exact: true })).toBeVisible();
    await expect(fila).toContainText("En curso");

    await fila.getByRole("button", { name: "Check-out", exact: true }).click();
    const confirmacion = admin.getByRole("dialog");
    await expect(confirmacion.getByText(/Registrar check-out/i)).toBeVisible();
    await confirmacion.getByRole("button", { name: "Completar visita", exact: true }).click();
    await expect(admin.getByText("Check-out registrado", { exact: true })).toBeVisible();
    await expect(fila).toContainText("Completada");
  });

  await test.step("el pago quedó reflejado en la caja", async () => {
    await admin.goto(`${ADMIN_URL}/caja`);
    await expect(admin.getByText(`Pago reservación #${folio}`, { exact: true })).toBeVisible();
    await expect(admin.getByText("Ingreso", { exact: true }).first()).toBeVisible();
    await expect(admin.getByText("$100.00", { exact: true }).first()).toBeVisible();
  });

  await contexto.close();
});

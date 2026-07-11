# Configurar el correo real de notificaciones (chepo23larios@gmail.com)

Gmail no permite usar tu contraseña normal para enviar correos desde
código — necesitas generar una "contraseña de aplicación" (16
caracteres, solo para esto).

## Pasos (5 minutos, una sola vez)

1. Entra a https://myaccount.google.com/security
2. Activa "Verificación en 2 pasos" si no la tienes activada (Gmail lo exige para poder crear contraseñas de aplicación).
3. Ve a https://myaccount.google.com/apppasswords
4. Crea una nueva, ponle de nombre "EjiXhole Backend" (o cualquier nombre), y copia el código de 16 caracteres que te da (con espacios, ej. `abcd efgh ijkl mnop`).
5. Abre tu archivo `.env` en `Ejixhole-Backend` y agrega/edita estas 4 líneas:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=chepo23larios@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
NOTIFICACIONES_EMAIL_DESTINO=chepo23larios@gmail.com
```

(Pega el código de 16 caracteres SIN espacios en `SMTP_PASSWORD`.)

6. Reinicia el backend (`uvicorn app.main:app --reload` o como lo corras normalmente) para que tome los nuevos valores de `.env`.

## Cómo confirmar que ya funciona

Haz una reservación de prueba desde el sitio público
(`localhost:5174/reservar`) y revisa tu bandeja de entrada — deberías
recibir un correo con el asunto "Nueva solicitud de reservación #...".

Si no llega, revisa la terminal donde corre el backend — cualquier
error de envío se registra ahí con el detalle exacto (credenciales
incorrectas, etc.), sin que la reservación deje de crearse.

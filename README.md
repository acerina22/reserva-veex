# Reserva VeEX

Web de reservas de los equipos VeEX 10G y 1G (Node + Neon Postgres), con bot de Slack y alertas.

## Web (Render)
- `server.js` + `public/index.html`. Variable: `DATABASE_URL` (cadena de conexión de Neon).
- Build: `npm install` · Start: `node server.js`.
- La base impide por restricción (`sin_solapes`) que dos reservas activas del mismo equipo se superpongan.
- API: `GET /api/reservas`, `GET /api/estadisticas?dias=14`, `GET /api/reservas.csv`.

## Consulta en Slack (necesita la app de Slack, la crea un admin)
- `bot_veex.py`: responde `/veex`, `/veex 10g`, `/veex 1g` y las menciones `@BotVeEX veex`.
- Variables: `SLACK_BOT_TOKEN` (xoxb-), `SLACK_APP_TOKEN` (xapp-). Socket Mode activado.
- Permisos del bot: `commands`, `app_mentions:read`, `chat:write`. Crear el comando `/veex` en la app.
- Instalar: `pip install -r requirements.txt` · Ejecutar: `python bot_veex.py`.

## Alertas de devolución vencida
- `alerta_veex.py` lee la web y avisa por webhook. Variable: `SLACK_WEBHOOK_URL` (y `SLACK_WEBHOOK_VAR` si el webhook es de Workflow Builder).
- GitHub Actions (`.github/workflows/alerta.yml`) lo corre cada 30 min en horario laboral; cargar los secretos `SLACK_WEBHOOK_URL` y `SLACK_WEBHOOK_VAR` en el repo.

## En la PC (Windows)
- `instalar_veex.bat` instala `chequear_veex.py` con una tarea cada 30 min y accesos en el escritorio.

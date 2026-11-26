# Reserva VeEX (Fase 2)

Archivos
- `veex_sheet.py`: lee la planilla CSV y calcula estados.
- `alerta_veex.py`: avisa por webhook cuando un equipo `Retirado` pasó su hora `Hasta`.
- `bot_veex.py`: `@BotVeEX veex` (o `veex 10g` / `veex 1g`) responde el estado actual y próximas reservas.

Planilla (fila 1 = encabezados exactos)
`Equipo | Desde | Hasta | Sector | Cliente / Caso | Ubicación | Responsable | Observación | Estado`
Fechas `DD/MM/YYYY HH:MM`. Estado: Reservado, Retirado, Devuelto, Cancelado.

Setup
    pip install slack-bolt requests
    export SHEET_CSV_URL="https://docs.google.com/spreadsheets/d/ID/pub?output=csv"
    export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
    export SLACK_BOT_TOKEN="xoxb-..."   # scopes: app_mentions:read, chat:write, users:read
    export SLACK_APP_TOKEN="xapp-..."   # scope: connections:write (Socket Mode activado)
    python bot_veex.py

Alertas con cron (lun-vie, cada 30 min, 8 a 19 h):
    */30 8-19 * * 1-5 cd /ruta/veex && python alerta_veex.py

Nota: la alerta se repite en cada corrida mientras el equipo siga vencido (sirve de recordatorio).

Render
- Tipo: Web Service (Python), Build: `pip install -r requirements.txt`, Start: `python bot_veex.py`.
- Plan Starter o superior: el plan gratis se duerme y corta la conexión del bot.
- Variables: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SHEET_CSV_URL (cargarlas en el dashboard, no en el repo).
- Alertas: un Cron Job de Render con `python alerta_veex.py` y SLACK_WEBHOOK_URL, SHEET_CSV_URL.

Web de reservas (Node + Neon Postgres)
- `server.js` + `public/index.html`. Variable: `DATABASE_URL` (cadena de conexión de Neon).
- Build: `npm install` · Start: `node server.js`.
- La base impide por restricción (`sin_solapes`) que dos reservas activas del mismo equipo se superpongan.

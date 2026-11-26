"""Bot de Slack para consultar el estado de los VeEX.

Uso en Slack:  /veex   /veex 10g   /veex 1g   o mencionar al bot:  @BotVeEX veex
Variables: SLACK_BOT_TOKEN (xoxb-), SLACK_APP_TOKEN (xapp-), opcional VEEX_URL, PORT (Render)
Permisos del bot: commands, app_mentions:read, chat:write. Socket Mode activado.
"""
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from veex_sheet import leer_reservas, texto_estado

app = App(token=os.environ["SLACK_BOT_TOKEN"])


def respuesta(pedido):
    try:
        return texto_estado(leer_reservas(), pedido)
    except Exception as e:  # noqa: BLE001
        return f"No pude consultar las reservas: {e}"


@app.command("/veex")
def comando(ack, command, respond):
    ack()  # Slack exige responder en 3 s; la consulta puede tardar si el servidor dormía
    respond(response_type="ephemeral", text=respuesta(command.get("text", "")))


@app.event("app_mention")
def mencion(event, say):
    texto = event.get("text", "")
    if "veex" not in texto.lower():
        return
    say(text=respuesta(texto), thread_ts=event.get("thread_ts") or event["ts"])


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def _health_server():
    # Render (web service) exige un puerto abierto; Socket Mode no lo necesita.
    port = os.environ.get("PORT")
    if port:
        threading.Thread(target=HTTPServer(("0.0.0.0", int(port)), _Health).serve_forever, daemon=True).start()


if __name__ == "__main__":
    _health_server()
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()

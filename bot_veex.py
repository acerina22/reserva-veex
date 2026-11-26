"""@BotVeEX: responde el estado de los equipos cuando lo mencionan con la palabra 'veex'.

Variables de entorno: SLACK_BOT_TOKEN (xoxb-), SLACK_APP_TOKEN (xapp-), SHEET_CSV_URL
"""
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from veex_sheet import EQUIPOS, leer_reservas, resumen_equipo

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.event("app_mention")
def responder(event, say):
    texto = event.get("text", "").lower()
    if "veex" not in texto:
        return
    hilo = event.get("thread_ts") or event["ts"]
    try:
        reservas = leer_reservas()
    except Exception as e:  # noqa: BLE001
        say(text=f"No pude leer la planilla de reservas: {e}", thread_ts=hilo)
        return
    pedidos = [e for e in EQUIPOS if e.split()[-1].lower() in texto] or list(EQUIPOS)
    say(text="\n\n".join(resumen_equipo(reservas, e) for e in pedidos), thread_ts=hilo)


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
        threading.Thread(
            target=HTTPServer(("0.0.0.0", int(port)), _Health).serve_forever, daemon=True
        ).start()


if __name__ == "__main__":
    _health_server()
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()

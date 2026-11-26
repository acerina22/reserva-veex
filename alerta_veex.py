"""Alerta de devoluciones vencidas. Correr con cron cada 30-60 min en horario laboral.

Variables de entorno: SLACK_WEBHOOK_URL (y opcional SLACK_WEBHOOK_VAR, VEEX_URL)
"""
import os

import requests

from veex_sheet import leer_reservas, vencidas, _f


def enviar_alerta_slack(r):
    # Webhook clásico: variable "text". Webhook de Workflow Builder: poner en
    # SLACK_WEBHOOK_VAR el nombre de la variable que definiste (ej. "mensaje").
    var = os.environ.get("SLACK_WEBHOOK_VAR") or "text"
    mensaje = {
        var: (
            f"⚠️ *Aviso de devolución pendiente — {r['equipo']}*\n"
            f"• *Responsable:* {r['responsable']}\n"
            f"• *Cliente / Caso:* {r['cliente_caso']}\n"
            f"• *Ubicación:* {r['ubicacion']}\n"
            f"• *Vencimiento del turno:* {_f(r['hasta'])}\n"
            "_Por favor, confirmá la devolución con ✅ o actualizá el mensaje fijado si necesitás extenderlo._"
        )
    }
    requests.post(os.environ["SLACK_WEBHOOK_URL"], json=mensaje, timeout=10).raise_for_status()


def main():
    for r in vencidas(leer_reservas()):
        enviar_alerta_slack(r)


if __name__ == "__main__":
    main()

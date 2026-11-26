"""Chequeo local de reservas VeEX (solo librería estándar de Python 3).

Consulta la web de reservas y avisa si hay equipos retirados con devolución vencida.
    python chequear_veex.py            -> muestra el estado y avisa en pantalla si hay vencidos
    python chequear_veex.py --silencio -> solo imprime (para usar en consola)
Opcional: SLACK_WEBHOOK_URL (+ SLACK_WEBHOOK_VAR) para además avisar en Slack.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

URL = os.environ.get("VEEX_URL", "https://reserva-veex.onrender.com/api/reservas")


def pedir(url, datos=None):
    req = urllib.request.Request(url, data=datos, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:  # la 1.ª vez puede tardar si el server dormía
        return r.read()


def f(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")


def aviso_pantalla(titulo, texto):
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, texto, titulo, 0x40 | 0x1000)
        elif sys.platform == "darwin":
            os.system(f"osascript -e 'display notification \"{texto}\" with title \"{titulo}\"'")
        else:
            os.system(f'notify-send "{titulo}" "{texto}"')
    except Exception:
        pass


def main():
    datos = json.loads(pedir(URL))
    ahora = datetime.fromisoformat(datos["ahora"].replace("Z", "+00:00"))
    activas = [r for r in datos["reservas"] if r["estado"] in ("reservado", "retirado")]
    vencidas = [
        r for r in activas
        if r["estado"] == "retirado" and datetime.fromisoformat(r["hasta"].replace("Z", "+00:00")) < ahora
    ]
    for eq in ("VeEX 10G", "VeEX 1G"):
        ret = next((r for r in activas if r["equipo"] == eq and r["estado"] == "retirado"), None)
        print(f"{eq}: " + (f"RETIRADO por {ret['responsable']} hasta {f(ret['hasta'])}" if ret else "disponible"))
    if not vencidas:
        return
    lineas = [f"{r['equipo']}: {r['responsable']} ({r['cliente_caso'] or '-'}), vencía {f(r['hasta'])}" for r in vencidas]
    texto = "Devolución pendiente:\n" + "\n".join(lineas)
    print("\n" + texto)
    if "--silencio" not in sys.argv:
        aviso_pantalla("VeEX: devolución vencida", texto)
    hook = os.environ.get("SLACK_WEBHOOK_URL")
    if hook:
        var = os.environ.get("SLACK_WEBHOOK_VAR") or "text"
        pedir(hook, json.dumps({var: "⚠️ " + texto}).encode())


if __name__ == "__main__":
    main()

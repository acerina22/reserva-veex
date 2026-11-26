"""Lectura de las reservas VeEX desde la web (API JSON) y cálculo de estados.

Variable opcional: VEEX_URL (por defecto https://reserva-veex.onrender.com/api/reservas)
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
URL = os.environ.get("VEEX_URL") or "https://reserva-veex.onrender.com/api/reservas"
EQUIPOS = ("VeEX 10G", "VeEX 1G")


def _fecha(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00")) if valor else None


def leer_reservas(url=None):
    # La primera consulta puede tardar si el servidor gratuito estaba dormido.
    with urllib.request.urlopen(url or URL, timeout=90) as r:
        datos = json.loads(r.read().decode("utf-8"))
    return [
        {
            "id": f["id"],
            "equipo": f["equipo"],
            "desde": _fecha(f["desde"]),
            "hasta": _fecha(f["hasta"]),
            "sector": f.get("sector") or "",
            "cliente_caso": f.get("cliente_caso") or "-",
            "cliente": f.get("cliente") or "",
            "servicio": f.get("servicio") or "",
            "ubicacion": f.get("ubicacion") or "-",
            "responsable": f.get("responsable") or "Sin asignar",
            "observacion": f.get("observacion") or "",
            "estado": (f.get("estado") or "").lower(),
        }
        for f in datos["reservas"]
    ]


def vencidas(reservas, ahora=None):
    """Reservas en estado retirado cuyo horario 'hasta' ya pasó."""
    ahora = ahora or datetime.now(timezone.utc)
    return [r for r in reservas if r["estado"] == "retirado" and r["hasta"] and ahora > r["hasta"]]


def estado_equipo(reservas, equipo):
    """Devuelve (retirada_actual, [reservas_futuras]) para un equipo."""
    propias = [r for r in reservas if r["equipo"].lower() == equipo.lower()]
    retirada = next((r for r in propias if r["estado"] == "retirado"), None)
    futuras = sorted((r for r in propias if r["estado"] == "reservado"), key=lambda r: r["desde"])
    return retirada, futuras


def _f(d):
    return d.astimezone(TZ).strftime("%d/%m %H:%M") if d else "?"


def resumen_equipo(reservas, equipo):
    retirada, futuras = estado_equipo(reservas, equipo)
    if retirada:
        ahora = datetime.now(timezone.utc)
        marca = "Devolución vencida 🔴" if ahora > retirada["hasta"] else "Retirado 🔄"
        txt = (
            f"📌 *{equipo}*\nEstado: {marca}\nLo tiene: {retirada['responsable']}"
            + (f" ({retirada['sector']})" if retirada["sector"] else "")
            + f"\nCaso: {retirada['cliente_caso']}"
        )
        if retirada["cliente"]:
            txt += f"\nCliente: {retirada['cliente']}"
        if retirada["servicio"]:
            txt += f"\nServicio: {retirada['servicio']}"
        txt += f"\nUbicación: {retirada['ubicacion']}\nDevolución prevista: {_f(retirada['hasta'])}"
        if retirada["observacion"]:
            txt += f"\nObservación: {retirada['observacion']}"
    else:
        txt = f"📌 *{equipo}*\nEstado: Disponible ✅"
    if futuras:
        txt += "\nPróximas reservas 📅:"
        for r in futuras[:5]:
            txt += f"\n• {_f(r['desde'])} – {_f(r['hasta'])} · {r['responsable']} · {r['cliente_caso']}"
    return txt


def texto_estado(reservas, pedido=""):
    """Texto de respuesta para el bot. 'pedido' puede incluir 10g o 1g."""
    pedido = pedido.lower()
    elegidos = [e for e in EQUIPOS if e.split()[-1].lower() in pedido] or list(EQUIPOS)
    return "\n\n".join(resumen_equipo(reservas, e) for e in elegidos)

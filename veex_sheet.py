"""Lectura de la planilla de reservas VeEX (Google Sheet publicada como CSV).

Columnas esperadas: Equipo, Desde, Hasta, Sector, Cliente / Caso, Ubicación,
Responsable, Observación, Estado (Reservado | Retirado | Devuelto | Cancelado).
Formato de fechas: DD/MM/YYYY HH:MM
"""
import csv
import io
import os
from datetime import datetime

import requests

FMT = "%d/%m/%Y %H:%M"
EQUIPOS = ("VeEX 10G", "VeEX 1G")


def _fecha(valor):
    valor = (valor or "").strip()
    try:
        return datetime.strptime(valor, FMT) if valor else None
    except ValueError:
        return None


def leer_reservas(url=None):
    url = url or os.environ["SHEET_CSV_URL"]
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    r.encoding = "utf-8"
    filas = []
    for f in csv.DictReader(io.StringIO(r.text)):
        filas.append(
            {
                "equipo": (f.get("Equipo") or "").strip(),
                "desde": _fecha(f.get("Desde")),
                "hasta": _fecha(f.get("Hasta")),
                "sector": (f.get("Sector") or "").strip(),
                "cliente_caso": (f.get("Cliente / Caso") or "-").strip(),
                "ubicacion": (f.get("Ubicación") or "-").strip(),
                "responsable": (f.get("Responsable") or "Sin asignar").strip(),
                "observacion": (f.get("Observación") or "").strip(),
                "estado": (f.get("Estado") or "").strip().lower(),
            }
        )
    return filas


def vencidas(reservas, ahora=None):
    """Reservas en estado Retirado cuyo horario 'Hasta' ya pasó."""
    ahora = ahora or datetime.now()
    return [r for r in reservas if r["estado"] == "retirado" and r["hasta"] and ahora > r["hasta"]]


def estado_equipo(reservas, equipo):
    """Devuelve (retirada_actual, [reservas_futuras]) para un equipo."""
    propias = [r for r in reservas if r["equipo"].lower() == equipo.lower()]
    retirada = next((r for r in propias if r["estado"] == "retirado"), None)
    futuras = sorted(
        (r for r in propias if r["estado"] == "reservado" and r["desde"]),
        key=lambda r: r["desde"],
    )
    return retirada, futuras


def _f(d):
    return d.strftime("%d/%m %H:%M") if d else "?"


def resumen_equipo(reservas, equipo):
    retirada, futuras = estado_equipo(reservas, equipo)
    if retirada:
        txt = (
            f"📌 *{equipo}*\nEstado: Retirado 🔄\nSector: {retirada['sector']}\n"
            f"Cliente / caso: {retirada['cliente_caso']}\nUbicación: {retirada['ubicacion']}\n"
            f"Responsable: {retirada['responsable']}\nDisponible desde: {_f(retirada['hasta'])}"
        )
        if retirada["observacion"]:
            txt += f"\nObservación: {retirada['observacion']}"
    else:
        txt = f"📌 *{equipo}*\nEstado: Devuelto ✅ (disponible)"
    if futuras:
        txt += "\nPróximas reservas 📅:"
        for r in futuras[:5]:
            txt += f"\n• {_f(r['desde'])} – {_f(r['hasta'])} · {r['responsable']} · {r['cliente_caso']}"
    return txt

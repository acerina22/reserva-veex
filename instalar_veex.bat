@echo off
title Instalador VeEX
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t = Get-Content -Raw -Encoding UTF8 -LiteralPath '%~f0'; $m = '#--'+'PS--'; $c = ($t -split [regex]::Escape($m))[-1]; & ([scriptblock]::Create($c))"
exit /b
#--PS--
$ErrorActionPreference = 'Stop'
$dir   = Join-Path $env:LOCALAPPDATA 'VeEX'
$web   = 'https://reserva-veex.onrender.com'
$utf8  = New-Object System.Text.UTF8Encoding($false)

Write-Host ''
Write-Host '=== Instalador VeEX ===' -ForegroundColor Cyan

# 1) Buscar Python (descarta el atajo vacio de la Microsoft Store)
$pyExe = $null
foreach ($c in @('python', 'py')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $r = & $cmd.Source -c "import sys;print(sys.executable)" 2>$null
            if ($r -and (Test-Path $r)) { $pyExe = $r.Trim(); break }
        } catch {}
    }
}
if (-not $pyExe) {
    Write-Host 'No encontre Python 3 instalado.' -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $ok = Read-Host 'Lo instalo ahora con winget? (s/n)'
        if ($ok -eq 's') {
            winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            Write-Host 'Listo. Cerra esta ventana y ejecuta de nuevo el instalador.' -ForegroundColor Green
        }
    } else {
        Write-Host 'Instalalo desde https://www.python.org/downloads/ (marca "Add python.exe to PATH") y ejecuta de nuevo este instalador.'
    }
    Read-Host 'Enter para salir'
    return
}
$pyw = Join-Path (Split-Path $pyExe) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $pyExe }
Write-Host "Python: $pyExe"

# 2) Carpeta y script
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$script = Join-Path $dir 'chequear_veex.py'
$code = @'
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
'@
[System.IO.File]::WriteAllText($script, $code, $utf8)
Write-Host "Script instalado en: $dir"

# 3) Acceso para chequear a mano
$bat = Join-Path $dir 'Chequear VeEX ahora.bat'
[System.IO.File]::WriteAllText($bat, "@echo off`r`n`"$pyExe`" `"$script`"`r`necho.`r`npause`r`n", [System.Text.Encoding]::ASCII)

# 4) Accesos directos en el escritorio
$desk = [Environment]::GetFolderPath('Desktop')
[System.IO.File]::WriteAllText((Join-Path $desk 'Reserva VeEX.url'), "[InternetShortcut]`r`nURL=$web`r`n", [System.Text.Encoding]::ASCII)
Copy-Item $bat (Join-Path $desk 'Chequear VeEX ahora.bat') -Force

# 5) Tarea programada cada 30 minutos (aviso en pantalla si hay devolucion vencida)
$accion  = New-ScheduledTaskAction -Execute $pyw -Argument ('"' + $script + '"')
$disp    = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName 'VeEX chequeo' -Action $accion -Trigger $disp -Force | Out-Null
Write-Host 'Tarea programada creada: chequea cada 30 minutos.' -ForegroundColor Green

# 6) Primera ejecucion
Write-Host ''
Write-Host 'Primer chequeo (puede tardar hasta un minuto si el servidor estaba dormido)...'
try { & $pyExe $script } catch { Write-Host "No se pudo consultar ahora: $_" -ForegroundColor Yellow }

Write-Host ''
Write-Host 'Todo listo.' -ForegroundColor Green
Write-Host "  - Carpeta: $dir"
Write-Host '  - Escritorio: "Reserva VeEX" (abre la web) y "Chequear VeEX ahora"'
Write-Host '  - Para desinstalar: Unregister-ScheduledTask "VeEX chequeo" -Confirm:$false  y borrar la carpeta'
Read-Host 'Enter para cerrar'

"""Ejecuta la suite dos veces en estado limpio (clon nuevo del repositorio cada vez).

Uso (desde la raiz del proyecto):  python tools/ejecucion_limpia.py

Cada ejecucion hace `git clone` del ultimo commit, corre `python -m unittest discover -s tests -v`
dentro del clon y guarda evidencias/ejecucion_limpia_N.txt con comando, versiones, commit y resultado
(rutas y usuario saneados).
"""
import datetime
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registrar_evidencia import RAIZ, sanear  # noqa: E402

ENTORNO = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
COMANDO = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]


def una_ejecucion(numero):
    with tempfile.TemporaryDirectory(prefix="clon_limpio_") as base:
        clon = Path(base) / "laboratorio_seguridad"
        subprocess.run(["git", "clone", "--quiet", str(RAIZ), str(clon)], check=True, capture_output=True)
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=clon, capture_output=True, text=True).stdout.strip()
        limpio = subprocess.run(["git", "status", "--porcelain"], cwd=clon, capture_output=True, text=True).stdout.strip() == ""
        resultado = subprocess.run(COMANDO, cwd=clon, capture_output=True, text=True, encoding="utf-8", env=ENTORNO)
    encabezado = [
        f"# Ejecucion en estado limpio {numero} de 2",
        f"fecha: {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}",
        "preparacion: git clone del repositorio en un directorio temporal nuevo (sin __pycache__ ni datos previos)",
        f"arbol de trabajo del clon: {'limpio' if limpio else 'con cambios'}",
        "comando: python -m unittest discover -s tests -v",
        f"python: {platform.python_version()} ({platform.system()} {platform.release()})",
        f"commit del codigo: {commit}",
        f"codigo de salida: {resultado.returncode}",
        "-" * 72,
    ]
    texto = sanear("\n".join(encabezado) + "\n" + resultado.stdout + resultado.stderr)
    destino = RAIZ / "evidencias" / f"ejecucion_limpia_{numero}.txt"
    destino.write_text(texto, encoding="utf-8", newline="\n")
    return resultado.returncode, commit


def main():
    codigos = []
    for numero in (1, 2):
        codigo, commit = una_ejecucion(numero)
        print(f"ejecucion limpia {numero}: commit {commit}, codigo de salida {codigo}")
        codigos.append(codigo)
    return max(codigos)


if __name__ == "__main__":
    sys.exit(main())

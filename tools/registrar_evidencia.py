"""Ejecuta la suite y guarda una evidencia saneada y reproducible.

Uso (desde la raiz del proyecto):
    python tools/registrar_evidencia.py evidencias/archivo.txt "Titulo de la evidencia"

La evidencia incluye fecha, comando, versiones, commit y estado del arbol de
trabajo. Se reemplazan rutas absolutas y el nombre de usuario del sistema para
no exponer datos personales. Devuelve el codigo de salida de la suite.
"""
import datetime
import getpass
import os
import platform
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COMANDO = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]


def _git(*argumentos):
    resultado = subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True)
    return resultado.stdout.strip()


def sanear(texto):
    """Quita rutas absolutas y el usuario del sistema."""
    for original, reemplazo in (
        (str(RAIZ), "<repo>"),
        (str(RAIZ).replace("\\", "/"), "<repo>"),
        (str(Path.home()), "<home>"),
        (getpass.getuser(), "<usuario>"),
    ):
        texto = texto.replace(original, reemplazo)
    return texto


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    destino = RAIZ / sys.argv[1]
    titulo = sys.argv[2] if len(sys.argv) > 2 else "Ejecucion de la suite"
    ejecucion = subprocess.run(COMANDO, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    salida = ejecucion.stdout + ejecucion.stderr
    sucio = "con cambios sin confirmar" if _git("status", "--porcelain", "--", "src", "tests", "servidor.py") else "limpio"
    encabezado = [
        f"# {titulo}",
        f"fecha: {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"comando: python -m unittest discover -s tests -v",
        f"python: {platform.python_version()} ({platform.system()} {platform.release()})",
        f"commit base: {_git('rev-parse', '--short', 'HEAD')} ({_git('log', '-1', '--format=%s')})",
        f"arbol de codigo: {sucio}",
        f"codigo de salida: {ejecucion.returncode}",
        "-" * 72,
    ]
    texto = sanear("\n".join(encabezado) + "\n" + salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8", newline="\n")
    print(texto)
    return ejecucion.returncode


if __name__ == "__main__":
    sys.exit(main())

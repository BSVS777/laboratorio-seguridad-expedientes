"""Prueba de mutacion manual: rompe un control a la vez y verifica que alguna prueba falle.

Uso (desde la raiz del proyecto):  python tools/mutaciones.py

Cada mutacion se aplica a una COPIA temporal del proyecto (el codigo real no se toca).
Si ninguna prueba falla, la mutacion "sobrevive": indica que la suite no detectaria esa regresion
(o que el control es redundante). Escribe evidencias/mutaciones.md y evidencias/mutaciones.json.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTORNO = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

# (id, requisito, descripcion, archivo, texto original (unico), reemplazo, casos que deberian detectarla)
MUTACIONES = [
    ("M-01", "SEC-01", "El docente puede leer expedientes de cualquier sede", "src/lab.py",
     '        return expediente["sede"] == usuario["sede"]', "        return True", ["TC-10"]),
    ("M-02", "SEC-02", "El docente puede modificar notas de otra sede", "src/lab.py",
     ' or expediente["sede"] != usuario["sede"]', "", ["TC-03"]),
    ("M-03", "SEC-02", "Se elimina la comprobacion de rol docente al modificar", "src/lab.py",
     'usuario["rol"] != "docente" or ', "", ["TC-09"]),
    ("M-04", "SEC-04", "Se elimina la validacion de rango de la nota", "src/lab.py",
     "return NOTA_MIN <= nota <= NOTA_MAX", "return True", ["TC-05"]),
    ("M-05", "SEC-04", "Un booleano se acepta como nota", "src/lab.py",
     "isinstance(nota, bool) or ", "", ["TC-14"]),
    ("M-06", "SEC-03", "Una sesion revocada sigue autenticando", "src/lab.py",
     'sesion["revocada"] or ', "", ["TC-04"]),
    ("M-07", "SEC-03", "Se ignora la bandera 'expirada' (antes la tapaba el reloj)", "src/lab.py",
     ' or sesion["expirada"]', "", ["TC-04"]),
    ("M-08", "SEC-03", "La sesion no caduca por reloj", "src/lab.py",
     'if estado["ahora"]() >= sesion["expira_en"]:', "if False:", ["TC-19"]),
    ("M-09", "SEC-05", "Un ID inexistente responde 404 a cualquier rol (enumeracion)", "src/lab.py",
     'if usuario["rol"] == "administrador":\n            return 404', "if True:\n            return 404", ["TC-12"]),
    ("M-10", "SEC-05", "Escribir sobre un ID inexistente deja de ser 403", "src/lab.py",
     'if expediente is None or usuario["rol"] != "docente"', 'if usuario["rol"] != "docente"', ["TC-20"]),
    ("M-11", "SEC-06", "Las denegaciones dejan de auditarse", "src/lab.py",
     '    _auditar(estado, accion, usuario, expediente_id, "denegada")\n    return 403',
     "    return 403", ["TC-15"]),
    ("M-12", "SEC-06", "La bitacora guarda un valor con forma de token", "src/lab.py",
     '"usuario": usuario["id"]', '"usuario": "lab-" + usuario["id"]', ["TC-15"]),
    ("M-13", "SEC-03", "El servidor procesa el cuerpo antes de autenticar", "servidor.py",
     "if autenticar(self.estado, self._token()) is None:", "if False:", ["TC-22"]),
    ("M-14", "SEC-05", "Se elimina Cache-Control: no-store", "servidor.py",
     'self.send_header("Cache-Control", "no-store")', "pass", ["TC-21"]),
    ("M-15", "SEC-07", "Se acepta Content-Length negativo", "servidor.py",
     "if cantidad < 0:", "if False:", ["TC-18"]),
]


def ejecutar(copia):
    resultado = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=copia, capture_output=True, text=True, encoding="utf-8", env=ENTORNO, timeout=240,
    )
    salida = resultado.stdout + resultado.stderr
    fallidas = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\w+)", salida, re.M)))
    total = re.search(r"Ran (\d+) tests?", salida)
    return resultado.returncode, int(total.group(1)) if total else 0, fallidas


def casos_de(nombres):
    return sorted({f"TC-{m.group(1)}" for n in nombres if (m := re.search(r"TC(\d\d)", n))})


def main():
    filas = []
    with tempfile.TemporaryDirectory(prefix="mutacion_") as base:
        for indice, (mid, req, desc, archivo, original, nuevo, esperados) in enumerate(MUTACIONES):
            copia = Path(base) / f"m{indice}"
            for elemento in ("src", "tests", "servidor.py"):
                origen = RAIZ / elemento
                if origen.is_dir():
                    shutil.copytree(origen, copia / elemento, ignore=shutil.ignore_patterns("__pycache__"))
                else:
                    copia.mkdir(parents=True, exist_ok=True)
                    shutil.copy(origen, copia / elemento)
            if indice == 0:  # linea base: sin mutar, la suite debe pasar
                codigo, total, fallidas = ejecutar(copia)
                assert codigo == 0, f"la linea base falla: {fallidas}"
                linea_base = total
            ruta = copia / archivo
            texto = ruta.read_text(encoding="utf-8")
            assert texto.count(original) == 1, f"{mid}: el texto a mutar no es unico ({texto.count(original)})"
            ruta.write_text(texto.replace(original, nuevo), encoding="utf-8", newline="")
            try:
                codigo, total, fallidas = ejecutar(copia)
            except subprocess.TimeoutExpired:
                codigo, total, fallidas = 1, 0, ["(tiempo agotado: la suite se bloqueo)"]
            matados = casos_de(fallidas)
            filas.append({
                "id": mid, "requisito": req, "mutacion": desc, "archivo": archivo,
                "detectada": codigo != 0, "casos_que_fallan": matados,
                "esperados": esperados,
                "esperados_detectan": all(e in matados for e in esperados),
            })
            print(f"{mid} {'DETECTADA ' if codigo else 'SOBREVIVE '} {matados}")
    detectadas = sum(f["detectada"] for f in filas)
    (RAIZ / "evidencias").mkdir(exist_ok=True)
    (RAIZ / "evidencias" / "mutaciones.json").write_text(
        json.dumps({"pruebas_linea_base": linea_base, "mutaciones": filas}, ensure_ascii=False, indent=2),
        encoding="utf-8", newline="\n")
    lineas = [
        "# Prueba de mutacion manual (¿las pruebas fallan cuando el control falla?)",
        "",
        f"Linea base sin mutar: {linea_base} pruebas, todas aprobadas. Cada fila rompe **un** control en una copia temporal.",
        f"Resultado: **{detectadas} de {len(filas)} mutaciones detectadas** ({detectadas / len(filas):.0%}).",
        "",
        "| Mutacion | Requisito | Control roto | ¿Detectada? | Casos que fallan |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in filas:
        lineas.append(
            f"| {f['id']} | {f['requisito']} | {f['mutacion']} | {'Si' if f['detectada'] else 'No (sobrevive)'} "
            f"| {', '.join(f['casos_que_fallan']) or '-'} |")
    sobrevivientes = [f for f in filas if not f["detectada"]]
    lineas += ["", "## Sobrevivientes"]
    if sobrevivientes:
        for f in sobrevivientes:
            lineas.append(f"- {f['id']}: {f['mutacion']}. Ver el analisis en el informe.")
    else:
        lineas.append("- Ninguno.")
    (RAIZ / "evidencias" / "mutaciones.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

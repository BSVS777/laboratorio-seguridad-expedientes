"""Genera los entregables documentales a partir de datos reales.

Uso (desde la raiz del proyecto):  python informe/generar.py

1. Ejecuta la suite y asigna un estado (Aprobado / Fallido / No ejecutado) a cada caso TC-xx.
2. Calcula las metricas (tasa de aprobacion, avance, cobertura de requisitos).
3. Escribe casos_prueba.csv, matriz_trazabilidad.csv y hallazgos.csv.
4. Construye informe/_build/informe_seguridad.html y lo convierte en informe_seguridad.pdf con Edge (modo sin ventana).

Los datos del equipo (portada, integrantes, revisor, companero) salen de informe/equipo.json.
"""
import contextlib
import csv
import datetime
import html
import io
import json
import platform
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "informe"))
import datos  # noqa: E402

EDGE = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]
MANUALES_POR_CASO = {
    "TC-02": "PM-01", "TC-03": "PM-02", "TC-05": "PM-03", "TC-17": "PM-04",
    "TC-04": "PM-05, PM-06", "TC-12": "PM-07, PM-08",
}
CICLOS = [
    (1, "Acceso indebido: enumeración de expedientes", "SEC-05 (amenaza R-07, relacionado con SEC-01)", "H-01",
     [("ROJO", "a501914", "ciclo1_1_ROJO.txt"), ("VERDE", "d7fe59d", "ciclo1_2_VERDE.txt"), ("REFACTOR", "e29e531", "ciclo1_3_REFACTOR.txt")],
     "TC-12 y TC-20 fallan con `403 != 404`: un ID inexistente respondía 404 y uno ajeno 403, lo que permite descubrir qué expedientes existen.",
     "Cambio mínimo: cuando el expediente no existe y el rol no es administrador, se responde el mismo 403 auditado.",
     "`_denegar()` centraliza el 403 y su auditoría; los caminos de lectura y escritura ya no pueden divergir."),
    (2, "Validez de la sesión: caducidad por reloj", "SEC-03 (amenaza R-04)", "H-02",
     [("ROJO", "335dfc4", "ciclo2_1_ROJO.txt"), ("VERDE", "7f7fd23", "ciclo2_2_VERDE.txt"), ("REFACTOR", "a3719fd", "ciclo2_3_REFACTOR.txt")],
     "TC-19a/b/c fallan con `401 != 200` y TC-19d con `expira_en` ausente: una sesión con vigencia vencida seguía autenticando.",
     "Cambio mínimo: `expira_en` por sesión y reloj inyectable `estado[\"ahora\"]`; se rechaza si `ahora >= expira_en`.",
     "`_sesion_vigente()` unifica la regla entre `autenticar` y `revocar_sesion`."),
    (3, "Sesión: autenticar antes de interpretar el cuerpo (adicional)", "SEC-03 (amenaza R-08)", "H-03",
     [("ROJO", "ec13a34", "ciclo3_1_ROJO.txt"), ("VERDE", "724193d", "ciclo3_2_VERDE.txt"), ("REFACTOR", "7eff45f", "ciclo3_3_REFACTOR.txt")],
     "TC-22 falla con `401 != 400`: sin sesión y con JSON inválido el servidor describía el error de validación.",
     "Cambio mínimo: `do_POST` autentica antes de leer el cuerpo.",
     "`no_autenticado()` define la respuesta 401 una sola vez."),
    (4, "El 401 podía perderse con un cuerpo sin consumir (adicional)", "SEC-03 / SEC-07 (amenaza R-08)", "H-04",
     [("ROJO", "9f73de3", "ciclo4_1_ROJO.txt"), ("VERDE", "fff5be1", "ciclo4_2_VERDE.txt"), ("REFACTOR", "dafa7ba", "ciclo4_3_REFACTOR.txt")],
     "TC-23 falla con `ConnectionAbortedError`: el servidor cerraba con datos pendientes y el cliente perdía la respuesta.",
     "Cambio mínimo: `_descartar_cuerpo()` consume hasta 1024 bytes antes de responder el 401.",
     "`_leer_nota()` aísla la lectura del cuerpo y deja `do_POST` más corto."),
]


# ------------------------------------------------------------------ utilidades
def e(texto):
    return html.escape(str(texto), quote=False)


ETIQUETAS_SEGURAS = re.compile(r"&lt;(/?(?:code|em|strong|br|span)(?: class=['\"]\w+['\"])?)/?&gt;")


def md(texto):
    texto = ETIQUETAS_SEGURAS.sub(lambda m: "<" + m.group(1) + ">", e(texto))
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    return re.sub(r"(\[(?:COMPLETAR|PENDIENTE)[^\]]*\])", r"<mark>\1</mark>", texto)


def tabla(cabeceras, filas, clase=""):
    if filas and all(re.match(r"^(\*\*)?(TC|SEC|CA|PM|H|R|A|C|NC|OBS|M)-\d+", str(f[0])) for f in filas):
        clase = f"{clase} idcol".strip()
    cab = "".join(f"<th>{md(c)}</th>" for c in cabeceras)
    cuerpo = "".join("<tr>" + "".join(f"<td>{md(c)}</td>" for c in fila) + "</tr>" for fila in filas)
    return f'<table class="{clase}"><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>'


def git(*argumentos):
    return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def leer(ruta):
    archivo = RAIZ / ruta
    return archivo.read_text(encoding="utf-8") if archivo.exists() else ""


# ------------------------------------------------------------------ resultados reales
class Registro(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.estados = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.estados[test._testMethodName] = "ok"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.estados[test._testMethodName] = "fallo"

    def addError(self, test, err):
        super().addError(test, err)
        self.estados[test._testMethodName] = "fallo"


def ejecutar_suite():
    suite = unittest.TestLoader().discover(str(RAIZ / "tests"))
    registro = Registro()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        suite.run(registro)
    return registro.estados


def estados_por_caso(estados_pruebas):
    resultado = {}
    for caso in datos.CASOS:
        numero = caso["id"].split("-")[1]
        pruebas = sorted(n for n in estados_pruebas if re.search(rf"TC{numero}(?!\d)", n))
        if not pruebas:
            estado = "No ejecutado"
        elif all(estados_pruebas[n] == "ok" for n in pruebas):
            estado = "Aprobado"
        else:
            estado = "Fallido"
        resultado[caso["id"]] = (estado, pruebas)
    return resultado


def metricas(casos_estado):
    conteo = {k: sum(1 for estado, _ in casos_estado.values() if estado == k)
              for k in ("Aprobado", "Fallido", "Bloqueado", "No ejecutado")}
    planificados = len(casos_estado)
    ejecutados = conteo["Aprobado"] + conteo["Fallido"]
    tasa = 100 * conteo["Aprobado"] / ejecutados if ejecutados else 0
    avance = 100 * ejecutados / planificados if planificados else 0
    cubiertos = {r.strip() for c in datos.CASOS if casos_estado[c["id"]][0] in ("Aprobado", "Fallido") for r in c["req"].split(",")}
    requisitos = [r[0] for r in datos.REQUISITOS]
    cobertura = 100 * len([r for r in requisitos if r in cubiertos]) / len(requisitos)
    return conteo, planificados, ejecutados, tasa, avance, cobertura, [r for r in requisitos if r not in cubiertos]


# ------------------------------------------------------------------ CSV
def escribir_csv(ruta, cabeceras, filas):
    with open(RAIZ / ruta, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(cabeceras)
        escritor.writerows(filas)


def generar_csv(casos_estado):
    responsable = "Equipo (ver equipo.json)"
    escribir_csv("casos_prueba.csv",
                 ["ID", "Tipo", "Titulo", "Requisito", "Amenaza", "Prioridad", "Objetivo", "Precondiciones", "Entradas", "Pasos",
                  "Resultado esperado", "Nivel", "Pruebas automatizadas", "Pruebas manuales", "Estado", "Responsable"],
                 [[c["id"], c["tipo"], c["titulo"], c["req"], c["amenaza"], c["prioridad"], c["objetivo"], c["pre"], c["entradas"],
                   c["pasos"], c["esperado"], c["nivel"], "; ".join(casos_estado[c["id"]][1]), MANUALES_POR_CASO.get(c["id"], "-"),
                   casos_estado[c["id"]][0], responsable] for c in datos.CASOS])
    categoria = {r[0]: r[1] for r in datos.REQUISITOS}
    filas = []
    for c in datos.CASOS:
        for req in [r.strip() for r in c["req"].split(",")]:
            estado, pruebas = casos_estado[c["id"]]
            filas.append([req, categoria[req], c["amenaza"], c["id"], c["tipo"], c["prioridad"], c["esperado"],
                          "; ".join(pruebas), MANUALES_POR_CASO.get(c["id"], "-"), "evidencias/ejecucion_limpia_1.txt; evidencias/ejecucion_limpia_2.txt", estado])
    filas.sort(key=lambda f: (f[0], f[3]))
    escribir_csv("matriz_trazabilidad.csv",
                 ["Requisito", "Categoria", "Amenaza", "Caso de prueba", "Tipo", "Prioridad", "Evidencia esperada",
                  "Pruebas automatizadas", "Pruebas manuales", "Evidencia obtenida", "Estado"], filas)
    escribir_csv("hallazgos.csv", [nombre for _, nombre in datos.HALLAZGO_CAMPOS],
                 [[h[k] for k, _ in datos.HALLAZGO_CAMPOS] for h in datos.HALLAZGOS])


# ------------------------------------------------------------------ lectura de evidencias
def parsear_corrida(texto):
    ran = re.search(r"Ran (\d+) tests?", texto)
    fallos = re.search(r"failures=(\d+)", texto)
    errores = re.search(r"errors=(\d+)", texto)
    total = int(ran.group(1)) if ran else 0
    malos = (int(fallos.group(1)) if fallos else 0) + (int(errores.group(1)) if errores else 0)
    return total, total - malos, malos


def tabla_ciclo(ciclo):
    filas = []
    for paso, commit, archivo in ciclo[4]:
        total, buenas, malas = parsear_corrida(leer(f"evidencias/tdd/{archivo}"))
        existe = bool(git("cat-file", "-t", commit))
        filas.append([paso, f"`{commit}`" + ("" if existe else " (¡no existe!)"), f"`evidencias/tdd/{archivo}`", total, buenas, malas,
                      f"{100 * buenas / total:.1f} %" if total else "-"])
    return tabla(["Paso", "Commit", "Evidencia", "Pruebas", "Aprobadas", "Fallidas", "Tasa"], filas, "compacta")


def pruebas_manuales():
    filas = []
    for seccion in leer("evidencias/pruebas_manuales_api.md").split("\n## ")[1:]:
        encabezado = seccion.splitlines()[0]
        identificador, _, descripcion = encabezado.partition(" - ")
        caso = re.search(r"Caso relacionado: (.+)", seccion)
        http = re.search(r"HTTP/1\.\d (\d+)", seccion)
        cuerpo = re.search(r"\n(\{.*\})\n```", seccion)
        resultado = f"HTTP {http.group(1)}" if http else (cuerpo.group(1) if cuerpo else "-")
        filas.append([identificador, descripcion, caso.group(1) if caso else "-", resultado])
    return filas


def corrida_limpia(numero):
    texto = leer(f"evidencias/ejecucion_limpia_{numero}.txt")
    if not texto:
        return [f"Ejecución limpia {numero}", "[PENDIENTE: ejecutar tools/ejecucion_limpia.py]", "-", "-", "-"]
    commit = re.search(r"commit del codigo: (\S+)", texto)
    python = re.search(r"python: (.+)", texto)
    ran = re.search(r"Ran (\d+) tests? in ([\d.]+)s", texto)
    ok = "OK" in texto.split("-" * 72)[-1]
    return [f"Ejecución limpia {numero}", f"`{commit.group(1) if commit else '-'}`", python.group(1) if python else "-",
            f"{ran.group(1)} pruebas en {ran.group(2)} s" if ran else "-", "Aprobada" if ok else "CON FALLOS"]


def contribuciones(equipo):
    lineas = git("log", "--format=%an\t%ad\t%s", "--date=short").splitlines()
    por_autor = {}
    for linea in lineas:
        autor, fecha, _ = linea.split("\t", 2)
        por_autor.setdefault(autor, []).append(fecha)
    filas = []
    for integrante in equipo["integrantes"]:
        fechas = por_autor.get(integrante["git_autor"], [])
        dias = len(set(fechas))
        cumple = len(fechas) >= 2 and dias >= 2
        filas.append([integrante["nombre"], integrante["git_autor"], integrante["aporte"], len(fechas), dias,
                      "Cumple" if cumple else "**No cumple aún** (se requieren ≥ 2 commits en ≥ 2 días distintos)"])
    sin_asignar = [(a, len(f), len(set(f))) for a, f in por_autor.items() if a not in {i["git_autor"] for i in equipo["integrantes"]}]
    return filas, sin_asignar


# ------------------------------------------------------------------ HTML
CSS = """
@page { size: A4; margin: 18mm 15mm 18mm 15mm; @bottom-center { content: "Página " counter(page); font-size: 8pt; color: #555; } }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Calibri, Arial, sans-serif; font-size: 9.6pt; line-height: 1.38; color: #1c2430; }
h1 { font-size: 21pt; color: #17375e; margin: 0 0 4pt; }
h2 { font-size: 14pt; color: #17375e; border-bottom: 2px solid #17375e; padding-bottom: 2pt; margin: 18pt 0 7pt; break-after: avoid; }
h3 { font-size: 11pt; color: #1f4e79; margin: 12pt 0 4pt; break-after: avoid; }
h4 { font-size: 9.8pt; color: #2b2b2b; margin: 8pt 0 3pt; break-after: avoid; }
p { margin: 3pt 0 5pt; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.4pt; background: #eef1f5; padding: 0 2pt; border-radius: 2pt; }
pre { font-family: Consolas, "Courier New", monospace; font-size: 7.6pt; background: #f4f6f9; border: 1px solid #d7dde6; padding: 5pt 7pt; white-space: pre-wrap; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 8.2pt; }
th { background: #17375e; color: #fff; text-align: left; padding: 3pt 4pt; border: 1px solid #17375e; }
td { padding: 3pt 4pt; border: 1px solid #c9d1dc; vertical-align: top; }
tr { break-inside: avoid; }
table.idcol td:first-child { white-space: nowrap; }
tbody tr:nth-child(even) td { background: #f6f8fb; }
table.compacta { width: auto; min-width: 70%; }
mark { background: #fff3a8; color: #6b4e00; padding: 0 2pt; border-radius: 2pt; }
.portada { text-align: center; padding-top: 40mm; break-after: page; }
.portada .sub { font-size: 12pt; color: #444; margin-bottom: 14pt; }
.portada table { width: 80%; margin: 14pt auto; font-size: 10pt; text-align: left; }
.aviso { border-left: 4px solid #c58b00; background: #fff8e1; padding: 5pt 8pt; margin: 6pt 0; break-inside: avoid; }
.pendiente { border-left: 4px solid #b00020; background: #fdecee; padding: 5pt 8pt; margin: 6pt 0; break-inside: avoid; }
.decision { border: 2px solid #17375e; padding: 7pt 10pt; margin: 8pt 0; background: #eef3fa; break-inside: avoid; }
.kpi { display: flex; gap: 8pt; margin: 6pt 0; }
.kpi div { flex: 1; border: 1px solid #c9d1dc; padding: 5pt; text-align: center; border-radius: 3pt; }
.kpi b { display: block; font-size: 16pt; color: #17375e; }
.ok { color: #0a6b2d; font-weight: 600; } .mal { color: #b00020; font-weight: 600; }
ul { margin: 2pt 0 5pt 14pt; padding: 0; }
"""


def construir_html(equipo, casos_estado, estados_pruebas):
    conteo, planificados, ejecutados, tasa, avance, cobertura, sin_cobertura = metricas(casos_estado)
    nucleo = [c for c in datos.CASOS if int(c["id"].split("-")[1]) <= 12]
    cnt_nucleo = {k: sum(1 for c in nucleo if casos_estado[c["id"]][0] == k) for k in ("Aprobado", "Fallido")}
    pruebas_unidad = [n for n in estados_pruebas if not n.startswith("test_api_")]
    pruebas_api = [n for n in estados_pruebas if n.startswith("test_api_")]
    mutaciones = json.loads(leer("evidencias/mutaciones.json") or '{"mutaciones": []}')["mutaciones"]
    detectadas = sum(1 for m in mutaciones if m["detectada"])
    hoy = datetime.date.today().isoformat()
    commit_codigo = git("log", "-1", "--format=%h", "--", "src", "servidor.py", "tests")
    filas_contrib, sin_asignar = contribuciones(equipo)
    rc, pr = equipo["revision_cruzada"], equipo["prueba_reproducibilidad"]
    abiertos = [h for h in datos.HALLAZGOS if h["estado_final"] == "Abierto"]
    aceptados = [h for h in datos.HALLAZGOS if h["estado_final"].startswith("Aceptado")]
    corregidos = [h for h in datos.HALLAZGOS if h["estado_final"].startswith("Corregido")]
    secciones = []

    # ---- portada
    integrantes = "<br>".join(md(f"{i['nombre']} ({i['git_autor']})") for i in equipo["integrantes"])
    secciones.append(f"""
<div class="portada">
  <div class="sub">{md(equipo['institucion'])}</div>
  <h1>Informe técnico de pruebas de seguridad</h1>
  <div class="sub">{md(datos.PROYECTO)}</div>
  <table>
    <tr><th>Curso</th><td>{md(equipo['curso'])}</td></tr>
    <tr><th>Código de curso</th><td>{md(equipo['codigo_curso'])}</td></tr>
    <tr><th>Grupo</th><td>{md(equipo['grupo'])}</td></tr>
    <tr><th>Docente</th><td>{md(equipo['docente'])}</td></tr>
    <tr><th>Integrantes</th><td>{integrantes}</td></tr>
    <tr><th>Proyecto y versión</th><td>{md(datos.PROYECTO)} · versión {datos.VERSION_PROYECTO}</td></tr>
    <tr><th>Fecha de entrega</th><td>{md(equipo['fecha_entrega'])}</td></tr>
    <tr><th>Fecha de generación</th><td>{hoy} · commit del código <code>{commit_codigo}</code></td></tr>
  </table>
  <p class="aviso">Material didáctico. Todos los datos, usuarios y tokens son sintéticos; las pruebas se ejecutaron solo en 127.0.0.1.</p>
</div>""")

    # ---- resumen
    secciones.append(f"""
<h2>Resumen ejecutivo</h2>
<p>Se diseñó y ejecutó una campaña de pruebas de seguridad sobre el laboratorio local de expedientes académicos (UTN Central y UTN Pacífico).
Se definieron <strong>{len(datos.ACTIVOS)} activos</strong>, <strong>{len(datos.AMENAZAS)} amenazas</strong> y <strong>{len(datos.REQUISITOS)} requisitos verificables</strong>
(SEC-01 a SEC-07), se diseñaron <strong>{planificados} casos</strong> (los 12 obligatorios más {planificados - 12} adicionales) y se automatizaron
<strong>{len(estados_pruebas)} pruebas</strong> ({len(pruebas_unidad)} de unidad y {len(pruebas_api)} de integración con la API). Se aplicaron
<strong>4 ciclos rojo-verde-refactor</strong> con commits verificables (2 obligatorios y 2 adicionales), se corrigieron {len(corregidos)} hallazgos y quedan
{len(aceptados)} aceptados como riesgo residual y {len(abiertos)} abierto.</p>
<div class="kpi">
  <div><b>{tasa:.1f} %</b>Tasa de aprobación</div>
  <div><b>{avance:.1f} %</b>Avance de ejecución</div>
  <div><b>{cobertura:.1f} %</b>Cobertura de requisitos</div>
  <div><b>{detectadas}/{len(mutaciones)}</b>Mutaciones detectadas</div>
</div>
<div class="decision"><strong>Decisión: LIBERAR CON CONDICIONES</strong> para el uso didáctico local; <strong>NO LIBERAR</strong> para cualquier uso real.
Una tasa de aprobación alta no autoriza por sí sola la liberación (ver sección 6).</div>
""")

    # ---- 1. alcance
    secciones.append(f"""
<h2>1. Alcance, activos, flujo de datos y amenazas</h2>
<h3>1.1 Alcance</h3>
<p>Se evalúa el servicio local compuesto por <code>servidor.py</code> (API HTTP en 127.0.0.1:8765) y <code>src/lab.py</code> (modelo de negocio), con dos sedes
(UTN Central en Alajuela y UTN Pacífico) y los roles estudiante, docente y administrador. La política de acceso es:</p>
{tabla(["Rol", "Lectura", "Cambio de nota"], [
    ["Estudiante", "Solo su expediente", "Prohibido"], ["Docente", "Expedientes de su sede", "Solo de su sede"],
    ["Administrador", "Expedientes de ambas sedes", "Prohibido"], ["Sin sesión / sesión inválida", "Prohibido", "Prohibido"]], "compacta")}
<p>Fuera de alcance: autenticación real, HTTPS, persistencia en base de datos y cualquier sistema distinto del laboratorio. Usuarios sintéticos:
Ana (estudiante, Central), Luis (estudiante, Pacífico), María (docente, Central), Pedro (docente, Pacífico), Admin y una sesión vencida.</p>
<h3>1.2 Activos</h3>
{tabla(["ID", "Activo", "Descripción", "Propiedad de seguridad"], datos.ACTIVOS)}
<h3>1.3 Flujo de datos</h3>
<pre>{e(datos.FLUJO_DATOS)}</pre>
<p>La frontera de confianza está entre el cliente y <code>servidor.py</code>: todo lo que cruza (cabecera <code>Authorization</code>, ruta, cuerpo JSON) es entrada no confiable.</p>
<h3>1.4 Amenazas priorizadas</h3>
{tabla(["ID", "Actor", "Acción de abuso", "Activo", "Impacto", "Prioridad", "Razonamiento de la prioridad"], datos.AMENAZAS)}
""")

    # ---- 2. requisitos
    matriz = []
    for rid, categoria, texto in datos.REQUISITOS:
        casos = [c for c in datos.CASOS if rid in [r.strip() for r in c["req"].split(",")]]
        matriz.append([rid, categoria, ", ".join(sorted({c["amenaza"] for c in casos})),
                       ", ".join(c["id"] for c in casos), f"{sum(casos_estado[c['id']][0] == 'Aprobado' for c in casos)}/{len(casos)} aprobados"])
    secciones.append(f"""
<h2>2. Requisitos, criterios de aceptación y trazabilidad</h2>
<h3>2.1 Requisitos de seguridad verificables</h3>
{tabla(["ID", "Categoría", "Requisito observable"], datos.REQUISITOS)}
<h3>2.2 Criterios de aceptación (Dado-Cuando-Entonces)</h3>
{tabla(["ID", "Requisito", "Dado", "Cuando", "Entonces"], datos.CRITERIOS)}
<h3>2.3 Matriz de trazabilidad requisito - riesgo - caso de prueba</h3>
{tabla(["Requisito", "Categoría", "Amenazas", "Casos de prueba", "Estado"], matriz)}
<p>La matriz completa (un renglón por requisito y caso, con evidencia esperada y obtenida) está en <code>matriz_trazabilidad.csv</code>.</p>
""")

    # ---- 3. casos
    def ficha(c):
        estado, pruebas = casos_estado[c["id"]]
        clase = "ok" if estado == "Aprobado" else "mal"
        manual = MANUALES_POR_CASO.get(c["id"])
        evidencia = "<br>".join(f"`{p}`" for p in pruebas) + (f"<br>Manual: {manual}" if manual else "")
        return [f"**{c['id']}**<br>{c['tipo']}<br>{c['prioridad']}", f"**{c['titulo']}**<br>{c['req']} · {c['amenaza']}<br>{c['objetivo']}",
                c["pre"], f"{c['entradas']}<br>**Pasos:** {c['pasos']}", c["esperado"],
                f"<span class='{clase}'>{estado}</span><br>{c['nivel']}<br>{evidencia}"]

    def tabla_html(casos):
        filas = [ficha(c) for c in casos]
        cab = "".join(f"<th>{t}</th>" for t in ["ID", "Caso y objetivo", "Precondiciones", "Entradas y pasos", "Resultado esperado", "Estado y evidencia"])
        cuerpo = "".join("<tr>" + "".join(f"<td>{md(v)}</td>" for v in f) + "</tr>" for f in filas)
        return f'<table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>'

    html_nucleo = tabla_html(nucleo)
    html_extras = tabla_html([c for c in datos.CASOS if int(c["id"].split("-")[1]) > 12])
    conteo_tipos = {t: sum(1 for c in nucleo if c["tipo"] == t) for t in ("Positivo", "Negativo", "Frontera")}
    secciones.append(f"""
<h2>3. Diseño de casos, TDD y ejecución</h2>
<h3>3.1 Los 12 casos de diseño ({conteo_tipos['Positivo']} positivos, {conteo_tipos['Negativo']} negativos, {conteo_tipos['Frontera']} de frontera)</h3>
<p>Cada caso registra identificador, requisito, amenaza, precondiciones, entradas, pasos, resultado esperado (oráculo) y evidencia (plantilla A.1). Los resultados
se obtienen de la ejecución real de la suite; <code>casos_prueba.csv</code> contiene la misma información.</p>
{html_nucleo}
<h3>3.2 Casos adicionales (no cuentan para el mínimo de 12)</h3>
{html_extras}
<h3>3.3 Automatización y diversidad</h3>
<p>Se automatizaron <strong>{len(estados_pruebas)} pruebas</strong> en <code>tests/</code>: {len(pruebas_unidad)} de unidad sobre la lógica de negocio
(<code>test_laboratorio.py</code>) y {len(pruebas_api)} de integración contra el servidor HTTP real en un puerto efímero de 127.0.0.1 (<code>test_api.py</code>).
Los {planificados} casos tienen al menos una prueba automatizada; además hay {len(pruebas_manuales())} pruebas manuales y 21 comprobaciones de API con
<code>ejecutar_todo.ps1</code>. No se duplicaron pruebas para alcanzar el mínimo: cada caso cubre una combinación distinta de rol, sede, sesión o entrada.</p>
""")

    # ---- TDD
    bloques_tdd = []
    for ciclo in CICLOS:
        bloques_tdd.append(f"""
<h4>Ciclo {ciclo[0]}: {e(ciclo[1])}</h4>
<p><strong>Requisito:</strong> {md(ciclo[2])} · <strong>Hallazgo:</strong> {ciclo[3]}</p>
<ul><li><strong>Rojo:</strong> {md(ciclo[5])}</li><li><strong>Verde:</strong> {md(ciclo[6])}</li><li><strong>Refactor:</strong> {md(ciclo[7])}</li></ul>
{tabla_ciclo(ciclo)}""")
    secciones.append(f"""
<h3>3.4 Ciclos rojo-verde-refactor</h3>
<div class="aviso"><strong>Nota de transparencia.</strong> El código base disponible en el repositorio ya contenía las correcciones de autorización,
sesiones revocadas y validación de nota; no se conserva una versión vulnerable ni su historial. Por eso los ciclos se ejecutaron sobre debilidades que
seguían abiertas y cada paso es un commit real que se puede verificar con <code>git show &lt;hash&gt;</code> y reproducir con <code>git checkout &lt;hash&gt;</code>.</div>
<p>El enunciado exige dos ciclos: el <strong>ciclo 1</strong> está vinculado con acceso indebido y el <strong>ciclo 2</strong> con la validez de la sesión. Los ciclos 3 y 4 son adicionales
y surgieron de la inspección estática y de una prueba intermitente. Por cada ciclo se guardan tres evidencias (plantilla A.3): rojo fallando por el motivo correcto,
verde con el cambio mínimo y refactor con la suite otra vez aprobada. Las salidas completas y saneadas están en <code>evidencias/tdd/</code> y el mapa de hashes en
<code>evidencias/tdd/REGISTRO_TDD.md</code>.</p>
{''.join(bloques_tdd)}
""")

    # ---- ejecucion, manuales, estatica, mutacion
    filas_manual = pruebas_manuales()
    estatica = leer("evidencias/inspeccion_estatica.md")
    filas_chk = re.findall(r"^\| (C-\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", estatica, re.M)
    cumplen = sum(1 for f in filas_chk if f[3].startswith("Cumple"))
    secciones.append(f"""
<h3>3.5 Ejecución en estado limpio y regresión</h3>
<p>La suite se ejecutó dos veces desde clones nuevos del repositorio (<code>tools/ejecucion_limpia.py</code>, comando <code>python -m unittest discover -s tests -v</code>).
Cada ejecución registra comando, versiones, commit y resultado en <code>evidencias/ejecucion_limpia_N.txt</code>. La regresión es la propia suite completa:
tras cada commit de verde y de refactor se repitió la suite entera (<code>evidencias/tdd/</code>), no solo la prueba que fallaba.</p>
{tabla(["Ejecución", "Commit del código", "Python y sistema", "Resultado", "Estado"], [corrida_limpia(1), corrida_limpia(2)])}
<h3>3.6 Pruebas manuales por la API (análisis dinámico)</h3>
<p>Se ejecutaron {len(filas_manual)} solicitudes con <code>curl.exe</code> contra el servidor local (incluye acceso entre sedes y entrada inválida). Comandos y respuestas literales en
<code>evidencias/pruebas_manuales_api.md</code>.</p>
{tabla(["ID", "Prueba", "Caso / requisito", "Resultado observado"], filas_manual)}
<h3>3.7 Inspección estática (SAST) con lista de comprobación</h3>
<p>El código se revisó <strong>sin ejecutarlo</strong> con una lista de {len(filas_chk)} comprobaciones sobre permisos, sesiones, validación, manejo de errores, exposición de datos, auditoría,
configuración y secretos ({cumplen} cumplen). La herramienta bandit 1.9.4 no reportó alertas (<code>evidencias/sast_bandit.txt</code>), resultado que se considera no concluyente para la
lógica de autorización. Se distingue del análisis dinámico de la sección 3.6, donde sí se envían solicitudes al sistema en ejecución.</p>
{tabla(["#", "Comprobación", "Resultado", "Área"], [[f[0], f[2], f[3], f[1]] for f in filas_chk])}
<h3>3.8 Prueba de mutación (¿las pruebas pueden fallar cuando el control falla?)</h3>
<p><code>tools/mutaciones.py</code> rompe un control a la vez en una copia temporal y comprueba que alguna prueba falle. Resultado final: <strong>{detectadas} de {len(mutaciones)} mutaciones detectadas</strong>.
La primera ejecución dejó un mutante vivo (M-07, la bandera <code>expirada</code> estaba tapada por el reloj); se agregó TC-04c y quedó detectado
(<code>evidencias/mutaciones_primera_ejecucion.txt</code> frente a <code>evidencias/mutaciones.md</code>).</p>
{tabla(["Mutación", "Requisito", "Control roto", "Detectada", "Casos que fallan"], [[m['id'], m['requisito'], m['mutacion'], 'Sí' if m['detectada'] else 'No', ', '.join(m['casos_que_fallan'])] for m in mutaciones], "compacta")}
""")

    # ---- 4. revisiones
    ajustes = tabla(["Antes", "Después", "Motivo"], datos.AJUSTES_PRUEBAS)
    secciones.append(f"""
<h2>4. Revisiones, usabilidad, hallazgos y conclusiones</h2>
<h3>4.1 Acta de inspección cruzada</h3>
<div class="pendiente"><strong>Pendiente de completar por el equipo.</strong> El enunciado exige que una persona distinta del autor revise una política de acceso y dos casos.
Las observaciones de abajo las identificó el autor durante la preparación y deben ser confirmadas, corregidas o ampliadas por el revisor antes de entregar.</div>
{tabla(["Campo", "Contenido"], [
    ["Revisor", rc['revisor']], ["Autor revisado", rc['autor_revisado']], ["Fecha", rc['fecha']],
    ["Objetos inspeccionados", "1) Política de acceso (tabla rol - operación, <code>_puede_leer</code> y la condición de escritura en <code>lab.py:122</code>). 2) Caso TC-03 (docente cambia nota de otra sede). 3) Caso TC-12 (enumeración de IDs)."],
    ["Observaciones del revisor", rc['observaciones_del_revisor']]])}
{tabla(["ID", "Observación verificable", "Severidad", "Acción tomada", "Hallazgo"], [
    ["OBS-01", "La política original no define qué responder ante un ID inexistente; 404 frente a 403 permitía enumerar expedientes.", "Media", "Requisito SEC-05 y ciclo TDD 1; corregido.", "H-01"],
    ["OBS-02", "Los oráculos de TC-02/TC-10 solo buscaban la clave <code>nota</code>, no <code>sede</code> ni el estado de los datos tras la denegación.", "Baja", "Nuevos <code>assertSinDatosProtegidos</code> y <code>assertExpedientesIntactos</code>; corregido.", "H-05"],
    ["OBS-03", "La caducidad de sesión era solo una bandera y la bandera <code>expirada</code> no tenía prueba propia (mutante M-07 vivo).", "Alta / Baja", "Ciclo TDD 2 y prueba TC-04c; corregido.", "H-02, H-05"],
    ["OBS-04", "Los intentos sin sesión válida y las revocaciones no quedan en la bitácora.", "Baja", "Aceptado como riesgo residual: requiere política adicional.", "H-06"]])}
<h4>Revisión de las pruebas inspeccionadas</h4>
{tabla(["Pregunta", "TC-03", "TC-12"], [
    ["¿Comprueba el efecto sobre los datos?", "Sí: <code>assertExpedientesIntactos</code> compara los expedientes completos antes y después.", "Sí: compara la respuesta completa (código y cuerpo) de IDs ajenos frente a inexistentes."],
    ["¿Es independiente?", "Sí: <code>setUp</code> crea un estado nuevo y una copia profunda por prueba; no depende de otras pruebas.", "Sí: mismo mecanismo; la prueba de API usa un servidor y un estado nuevos."],
    ["¿Puede fallar cuando el control falla?", "Sí: la mutación M-02 (quitar la comprobación de sede) la hace fallar.", "Sí: la mutación M-09 (404 para todos los roles) la hace fallar."]])}
<h3>4.2 Usabilidad y reproducibilidad</h3>
<h4>Reproducibilidad con un compañero</h4>
<div class="pendiente"><strong>Pendiente de completar por el equipo.</strong> Un compañero debe ejecutar la suite usando únicamente el <code>README.md</code> y registrar el resultado.
Mientras tanto, el autor verificó el procedimiento en clones nuevos (sección 3.5), lo cual <em>no sustituye</em> la prueba con otra persona.</div>
{tabla(["Campo", "Registro"], [["Compañero", pr['companero']], ["Fecha", pr['fecha']], ["Sistema y Python", pr['sistema']],
    ["¿Los pasos del README fueron suficientes?", pr['pasos_suficientes']], ["Dificultades encontradas", pr['dificultades']]])}
<h4>Mensajes de seguridad: sesión inválida y acceso denegado</h4>
{tabla(["Situación", "Mensaje actual", "Claridad", "Divulgación", "Valoración y mejora"], [
    ["Sesión inválida (ausente, desconocida, revocada o vencida)", "401 · <code>{\"error\": \"No autenticado\"}</code>",
     "Indica que falta autenticación válida, pero no distingue si debe iniciar sesión de nuevo o corregir el token.",
     "Ninguna: no revela si el token existió ni cuándo venció; evita sondeo de tokens.",
     "Seguro y suficientemente claro. Mejora propuesta (H-09): enviar <code>WWW-Authenticate: Bearer</code> y aceptar el esquema sin distinguir mayúsculas."],
    ["Acceso denegado (rol, sede o propiedad)", "403 · <code>{\"error\": \"Operación denegada\"}</code>",
     "Dice que la operación no se permitió, sin explicar el motivo (rol, sede o ID).",
     "Ninguna: sin nota, estudiante ni sede, y es idéntico para IDs ajenos e inexistentes (SEC-05).",
     "Aceptable para datos académicos: prioriza la confidencialidad; el diagnóstico queda en la bitácora (usuario, acción, ID y resultado)."]])}
<h4>Ajustes de nombres, datos y mensajes en las pruebas</h4>
{ajustes}
<h3>4.3 Registro de hallazgos</h3>
<p>Plantilla A.2 completa en <code>hallazgos.csv</code> (19 campos por hallazgo). Resumen:</p>
{tabla(["ID", "Título", "Sev.", "Requisito", "Casos", "Estado final", "Commits"], [[h['id'], h['titulo'], h['severidad'], h['req'], h['casos'], h['estado_final'], h['commits']] for h in datos.HALLAZGOS])}
{''.join(f"<h4>{h['id']} — {e(h['titulo'])}</h4>" + tabla(["Campo", "Contenido"], [[nombre, h[clave]] for clave, nombre in datos.HALLAZGO_CAMPOS if clave not in ('id', 'titulo')], "compacta") for h in datos.HALLAZGOS[:4])}
<p>Los detalles de H-05 a H-09 están en <code>hallazgos.csv</code>.</p>
<h3>4.4 Resultados no concluyentes y fallos de la propia prueba</h3>
{tabla(["ID", "Situación", "Clasificación", "Explicación técnica"], datos.NO_CONCLUYENTES)}
<h3>4.5 Conclusiones</h3>
<ul>
<li>Los controles de autorización, sesión, validación y confidencialidad se comportan según los requisitos en los {planificados} casos, tanto en la lógica como a través de la API.</li>
<li>Los defectos reales más valiosos aparecieron al <em>cuestionar</em> el diseño (enumeración, caducidad por reloj) y al <em>cuestionar las pruebas</em> (mutación y repetición), no al ver que todo pasaba.</li>
<li>La inspección estática encontró un defecto que la suite no cubría (H-03), lo que muestra que SAST y pruebas dinámicas se complementan.</li>
<li>Persisten limitaciones propias de un laboratorio (auditoría de intentos sin sesión, concurrencia, sin manejador general de excepciones).</li>
</ul>
""")

    # ---- 5. indicadores y decisión
    secciones.append(f"""
<h2>5. Indicadores calculados</h2>
<p>Estados separados por categoría (todos los casos planificados: {planificados}):</p>
{tabla(["Aprobado", "Fallido", "Bloqueado", "No ejecutado", "Planificados"], [[conteo['Aprobado'], conteo['Fallido'], conteo['Bloqueado'], conteo['No ejecutado'], planificados]], "compacta")}
{tabla(["Indicador", "Fórmula", "Cálculo", "Resultado"], [
    ["Tasa de aprobación", "aprobados / (aprobados + fallidos) × 100", f"{conteo['Aprobado']} / ({conteo['Aprobado']} + {conteo['Fallido']}) × 100", f"**{tasa:.1f} %**"],
    ["Avance", "(aprobados + fallidos) / planificados × 100", f"({conteo['Aprobado']} + {conteo['Fallido']}) / {planificados} × 100", f"**{avance:.1f} %**"],
    ["Cobertura de requisitos", "requisitos con al menos una prueba válida / requisitos definidos × 100",
     f"{len(datos.REQUISITOS) - len(sin_cobertura)} / {len(datos.REQUISITOS)} × 100", f"**{cobertura:.1f} %**"],
    ["Tasa de aprobación (12 casos de diseño)", "igual, solo TC-01 a TC-12", f"{cnt_nucleo['Aprobado']} / ({cnt_nucleo['Aprobado']} + {cnt_nucleo['Fallido']}) × 100",
     f"**{100 * cnt_nucleo['Aprobado'] / (cnt_nucleo['Aprobado'] + cnt_nucleo['Fallido']):.1f} %**"]])}
<p>Una prueba se considera válida si está automatizada, se ejecutó y su oráculo comprueba la respuesta, la ausencia de filtración y, cuando aplica, el estado de los datos; la validez se respalda con la prueba de mutación ({detectadas}/{len(mutaciones)}).
Las cifras salen de la ejecución real de la suite al generar este informe.</p>
<h3>Indicadores por paso TDD</h3>
{tabla(["Ciclo", "Paso", "Commit", "Pruebas", "Aprobadas", "Fallidas", "Tasa"],
       [[c[0], paso, f"`{h}`", *(lambda t: (t[0], t[1], t[2], f"{100 * t[1] / t[0]:.1f} %" if t[0] else "-"))(parsear_corrida(leer(f'evidencias/tdd/{arch}')))] for c in CICLOS for paso, h, arch in c[4]], "compacta")}
<p>La tasa en los pasos rojos es baja a propósito: demuestra que las pruebas nuevas detectan el defecto antes de corregirlo.</p>

<h2>6. Decisión de liberación</h2>
<div class="decision"><strong>Liberar con condiciones</strong> para el alcance del laboratorio (uso didáctico local en 127.0.0.1 con datos sintéticos). <strong>No liberar</strong> para cualquier uso real o publicación.</div>
<p><strong>Justificación.</strong> No hay defectos críticos de autorización abiertos: los {len(corregidos)} hallazgos confirmados relevantes están corregidos y verificados con rojo-verde-refactor y regresión completa, y las pruebas demostraron poder fallar
(mutación {detectadas}/{len(mutaciones)}). Aun así, <strong>una tasa de aprobación de {tasa:.0f} % no autoriza por sí sola la liberación</strong>: la cobertura se limita a los casos diseñados.</p>
<h4>Defectos y riesgos abiertos</h4>
{tabla(["ID", "Hallazgo", "Severidad", "Tratamiento"], [[h['id'], h['titulo'], h['severidad'], h['estado_final']] for h in aceptados + abiertos])}
<h4>Condiciones para la liberación didáctica</h4>
<ul>
<li>Completar el acta de inspección cruzada con un revisor distinto del autor (sección 4.1).</li>
<li>Registrar la prueba de reproducibilidad con un compañero usando solo el README (sección 4.2).</li>
<li>Cumplir el requisito de commits por integrante (≥ 2 commits en ≥ 2 días distintos; sección 7).</li>
<li>Aceptar formalmente H-06, H-07 y H-08 como riesgo residual o corregirlos; decidir sobre H-09.</li>
</ul>
<h4>Riesgo residual (para cualquier uso real)</h4>
<ul>
<li>La autenticación es sintética: tokens de texto fijo sin firma, contraseña ni rotación; la caducidad usa un reloj local y un TTL fijo.</li>
<li>No hay HTTPS, límite de intentos ni protección contra fuerza bruta; los intentos fallidos no se auditan (H-06).</li>
<li>El almacenamiento es memoria del proceso, sin cerrojo ante concurrencia (H-07) y sin aislamiento por sede a nivel de datos.</li>
<li>La bitácora vive en memoria y no es inmutable.</li>
<li>Un administrador distingue 404 de 403, por lo que puede enumerar IDs (es coherente con su rol de lectura global).</li>
</ul>
<p><strong>Responsable de la decisión (hipotético):</strong> {md(equipo['responsable_decision'])}</p>
<h3>Limitaciones del estudio</h3>
<ul>
<li>No se conserva la versión vulnerable original del laboratorio; el rojo documentado corresponde a debilidades que seguían abiertas (sección 3.4).</li>
<li>No se ejecutó un escaneo DAST automatizado (es optativo); el análisis dinámico fue manual (sección 3.6) y mediante pruebas de integración.</li>
<li>No se probó concurrencia, rendimiento ni resistencia a denegación de servicio.</li>
<li>La prueba de mutación usa {len(mutaciones)} mutaciones elegidas por el autor; no prueba todas las regresiones posibles.</li>
<li>El resultado de bandit es no concluyente para la lógica de negocio.</li>
</ul>
""")

    # ---- 8. contribuciones, IA, reglas
    pendientes_git = ""
    if sin_asignar:
        pendientes_git = "<p>Autores Git sin integrante asignado en <code>informe/equipo.json</code>: " + ", ".join(f"{a} ({n} commits, {d} días)" for a, n, d in sin_asignar) + ".</p>"
    secciones.append(f"""
<h2>7. Contribución del equipo y trazabilidad de commits</h2>
<p>Requisito del enunciado: al menos 2 commits significativos por integrante, en al menos 2 días distintos. Los números se calculan con <code>git log</code> y los nombres de autor de <code>informe/equipo.json</code>.</p>
{tabla(["Integrante", "Autor Git", "Aporte", "Commits", "Días distintos", "Estado del requisito"], filas_contrib)}
{pendientes_git}
<div class="pendiente"><strong>Atención.</strong> Hasta el momento de generar este informe los commits provienen de una sola cuenta y de un solo día. Cada integrante debe aportar sus propios commits en días diferentes
(por ejemplo, mejorar pruebas, completar el acta o corregir H-09) para cumplir el requisito; este informe no inventa autorías.</div>

<h2>8. Uso de asistentes de IA</h2>
<p>Se utilizó el asistente de IA <strong>Claude Code</strong> (Anthropic) para: proponer y redactar casos de prueba, ejecutar los ciclos TDD, escribir las herramientas de evidencia y de mutación,
realizar la inspección estática, generar los CSV y este informe. Todas las pruebas y comandos citados fueron ejecutados en el laboratorio local y sus salidas se conservan en <code>evidencias/</code>.
Las partes que requieren personas (inspección cruzada, prueba de reproducibilidad, autoría de commits, datos de portada) no se completaron con IA y están marcadas como pendientes.
El equipo debe comprender, ejecutar y verificar las pruebas por su cuenta antes de entregar.</p>

<h2>9. Cumplimiento de las reglas de ejecución y seguridad</h2>
<ul>
<li>Todas las pruebas se ejecutaron en el laboratorio local (127.0.0.1) y no se evaluó ningún sistema real.</li>
<li>Solo se usaron cuentas, tokens y datos ficticios; el repositorio no contiene credenciales ni información personal reales.</li>
<li>No se alteró ninguna aserción para ocultar un fallo confirmado. El único cambio de expectativa (TC-12, de 404 a 403 para no administradores) responde a un nuevo requisito (SEC-05) y se documentó en el commit rojo del ciclo 1.</li>
<li>El proyecto usa solo Python y su biblioteca estándar; bandit se usó únicamente como herramienta SAST opcional.</li>
</ul>

<h2>Anexo: archivos entregados</h2>
{tabla(["Archivo", "Contenido"], [
    ["informe_seguridad.pdf", "Este informe."], ["README.md", "Entorno, instalación, comandos exactos y restablecimiento de datos."],
    ["src/, servidor.py, tests/", "Código fuente y pruebas (unidad e integración)."],
    ["matriz_trazabilidad.csv, casos_prueba.csv, hallazgos.csv", "Matriz requisito-riesgo-caso, registro de casos (A.1) y bitácora de hallazgos (A.2)."],
    ["evidencias/", "TDD (rojo-verde-refactor con hashes), ejecuciones limpias, pruebas manuales, inspección estática, bandit y mutación."],
    ["tools/, informe/", "Herramientas reproducibles: registrar evidencia, ejecución limpia, mutación y generador de este informe."]])}
""")

    cuerpo = "".join(secciones)
    return f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Informe de seguridad</title><style>{CSS}</style></head><body>{cuerpo}</body></html>'


def generar_pdf(ruta_html, ruta_pdf):
    edge = next((p for p in EDGE if p.exists()), None)
    if not edge:
        print("AVISO: Microsoft Edge no encontrado; se omite el PDF (abra el HTML y use Imprimir > Guardar como PDF).")
        return False
    with tempfile.TemporaryDirectory(prefix="edge_perfil_") as perfil:
        subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={perfil}",
                        f"--print-to-pdf={ruta_pdf}", ruta_html.as_uri()], capture_output=True, timeout=120)
    return ruta_pdf.exists()


def main():
    equipo = json.loads((RAIZ / "informe" / "equipo.json").read_text(encoding="utf-8"))
    estados_pruebas = ejecutar_suite()
    casos_estado = estados_por_caso(estados_pruebas)
    conteo, planificados, ejecutados, tasa, avance, cobertura, sin_cobertura = metricas(casos_estado)
    sin_prueba = [c for c, (estado, _) in casos_estado.items() if estado == "No ejecutado"]
    if sin_prueba:
        print("AVISO: casos sin prueba automatizada:", ", ".join(sin_prueba))
    generar_csv(casos_estado)
    destino = RAIZ / "informe" / "_build"
    destino.mkdir(exist_ok=True)
    ruta_html = destino / "informe_seguridad.html"
    texto = construir_html(equipo, casos_estado, estados_pruebas)
    ruta_html.write_text(texto, encoding="utf-8")
    ruta_pdf = RAIZ / "informe_seguridad.pdf"
    hecho = generar_pdf(ruta_html, ruta_pdf)
    pendientes = len(re.findall(r"\[(?:COMPLETAR|PENDIENTE)", texto))
    print(f"Pruebas: {len(estados_pruebas)} · casos: {planificados} · {conteo}")
    print(f"Tasa de aprobacion {tasa:.1f}% · avance {avance:.1f}% · cobertura {cobertura:.1f}% · sin cobertura: {sin_cobertura or 'ninguno'}")
    print(f"PDF: {'generado' if hecho else 'NO generado'} ({ruta_pdf.name}) · marcadores pendientes en el informe: {pendientes}")


if __name__ == "__main__":
    main()

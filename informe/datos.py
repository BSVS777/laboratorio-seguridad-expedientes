"""Datos estructurados del informe: fuente unica para los CSV y el PDF.

Mantener aqui los identificadores (A-xx, R-xx, SEC-xx, CA-xx, TC-xx, H-xx) garantiza que
`matriz_trazabilidad.csv`, `casos_prueba.csv`, `hallazgos.csv` y el informe coincidan.
"""

PROYECTO = "Laboratorio de seguridad de expedientes académicos"
VERSION_PROYECTO = "1.1.0"

# ---------------------------------------------------------------- activos
ACTIVOS = [
    ("A-01", "Expedientes académicos", "Registros con identificador, estudiante, sede y nota (`estado[\"expedientes\"]`).", "Confidencialidad, integridad"),
    ("A-02", "Notas", "Dato crítico y modificable; su alteración equivale a fraude académico.", "Integridad"),
    ("A-03", "Sesiones y tokens sintéticos", "Tokens `lab-*` con banderas de revocación/expiración y `expira_en` (`estado[\"sesiones\"]`).", "Autenticidad, disponibilidad"),
    ("A-04", "Bitácora de auditoría", "Lista en memoria con usuario, acción, ID y resultado (`estado[\"auditoria\"]`).", "Trazabilidad, confidencialidad"),
    ("A-05", "Política de permisos", "Roles (estudiante, docente, administrador) y sedes (Central, Pacífico): `USUARIOS`, `_puede_leer`, regla de escritura.", "Autorización"),
    ("A-06", "API HTTP local", "`servidor.py` en 127.0.0.1:8765: parseo de cabeceras, JSON y tamaño del cuerpo.", "Disponibilidad, integridad de entrada"),
]

FLUJO_DATOS = """\
 [Cliente: curl / PowerShell / Postman / pruebas]
        |  (1) HTTP + "Authorization: Bearer <token sintético>"      <== frontera de confianza
        v
 [servidor.py]  _token() -> autenticar() (POST) -> _leer_nota() (Content-Length, JSON, 1024 bytes)
        |  (2) llamada Python con (estado, token, id, nota)
        v
 [src/lab.py]   autenticar -> autorizar (rol / sede / propiedad) -> validar nota -> persistir -> auditar
        |  (3) lee/escribe  A-01 expedientes, A-02 notas, A-03 sesiones, A-04 bitácora (memoria del proceso)
        v
 [servidor.py]  _salida(): JSON + "Cache-Control: no-store"
        |  (4) HTTP 200 / 400 / 401 / 403 / 404 / 413
        v
 [Cliente]\
"""

# ---------------------------------------------------------------- amenazas
# (id, actor, accion de abuso, activos, impacto, prioridad, razon de la prioridad)
AMENAZAS = [
    ("R-01", "Estudiante autenticado (Ana)", "Cambia el ID en la URL para leer el expediente de otra persona (IDOR).", "A-01, A-02",
     "Divulgación de notas y datos de terceros; pérdida de confidencialidad.", "Alta",
     "Probabilidad alta (basta cambiar un número) e impacto alto (datos académicos protegidos)."),
    ("R-02", "Docente de una sede", "Lee o modifica expedientes de la otra sede.", "A-01, A-02",
     "Notas alteradas o divulgadas fuera de su ámbito; fraude académico.", "Alta",
     "Impacto alto sobre la integridad; probabilidad media (usuario legítimo con acceso parcial)."),
    ("R-03", "Estudiante o administrador", "Invoca el cambio de nota (escalada vertical de privilegios).", "A-02",
     "Nota alterada sin autoridad; el administrador debería ser solo lectura.", "Alta",
     "Impacto alto (fraude) y endpoint conocido: probabilidad media-alta."),
    ("R-04", "Persona con un token revocado o vencido", "Reutiliza la sesión después de cerrarla o de su caducidad.", "A-03, A-01",
     "Acceso a información protegida tras terminar la sesión.", "Alta",
     "Impacto alto; probabilidad media (tokens guardados en historiales o scripts)."),
    ("R-05", "Docente descuidado o atacante con sesión docente", "Envía notas fuera de rango o de tipo inesperado (-1, 1000, true, NaN, texto).", "A-02",
     "Corrupción de datos y cálculos de promedios inválidos.", "Media",
     "Impacto medio (acotado a su sede); probabilidad media."),
    ("R-06", "Quien lea la bitácora o los logs", "Extrae tokens vigentes de los registros de auditoría.", "A-04, A-03",
     "Suplantación de sesiones.", "Media",
     "Impacto alto, pero requiere acceso a los registros: probabilidad baja-media."),
    ("R-07", "Usuario autenticado sin privilegios", "Prueba IDs y compara 404 contra 403 para descubrir qué expedientes existen.", "A-01",
     "Enumeración de expedientes; prepara ataques dirigidos.", "Media",
     "Impacto bajo-medio, probabilidad alta (automatizable)."),
    ("R-08", "Cliente malicioso o defectuoso", "Envía JSON inválido, Content-Length negativo o excesivo, o cuerpo sin sesión.", "A-06",
     "Errores internos, solicitudes colgadas o filtración de reglas de validación.", "Baja",
     "Impacto bajo (laboratorio local de un solo usuario); probabilidad media."),
]

# ---------------------------------------------------------------- requisitos
# (id, categoria, requisito observable)
REQUISITOS = [
    ("SEC-01", "Autorización / confidencialidad",
     "Si un estudiante solicita el expediente de otra persona, el servicio debe denegar la lectura (403), no incluir la nota "
     "en la respuesta y no modificar los registros. Un docente solo lee expedientes de su sede y el administrador lee los de ambas sedes."),
    ("SEC-02", "Autorización / integridad",
     "Solo un docente puede cambiar la nota de un expediente y solo si es de su sede; estudiantes, administradores y docentes de "
     "otra sede reciben 403 y la nota original permanece intacta."),
    ("SEC-03", "Sesiones",
     "Una solicitud sin sesión, con sesión desconocida, revocada o vencida (por bandera o por reloj) recibe 401 antes de cualquier "
     "otro procesamiento, sin acceso a datos y sin revelar la causa."),
    ("SEC-04", "Validación",
     "La nota debe ser un número finito en [0,100]; texto, null, booleanos, NaN, infinito, listas y valores fuera de rango "
     "reciben 400 y no se persisten."),
    ("SEC-05", "Confidencialidad en errores",
     "Las respuestas 401/403/400/404 no incluyen notas ni otros datos protegidos; el permiso se evalúa antes que el dato; y un "
     "ID inexistente es indistinguible de uno ajeno para quien no es administrador."),
    ("SEC-06", "Trazabilidad",
     "Cada lectura o actualización autenticada (permitida, denegada o rechazada) se registra con usuario, acción, ID de "
     "expediente y resultado, y la bitácora nunca contiene tokens."),
    ("SEC-07", "Robustez de entrada",
     "Un cuerpo JSON mal formado, que no sea un objeto, o con Content-Length negativo o no numérico se responde 400; un cuerpo "
     "mayor a 1024 bytes se responde 413; en ningún caso se alteran datos."),
]

# (id, requisito, dado, cuando, entonces)
CRITERIOS = [
    ("CA-01", "SEC-01",
     "Ana (estudiante, Central) tiene una sesión vigente y existe el expediente 202 de Luis (Pacífico)",
     "Ana solicita GET /expedientes/202",
     "recibe 403 con {\"error\": \"Operación denegada\"}, sin nota, estudiante ni sede, y los expedientes no cambian"),
    ("CA-02", "SEC-02",
     "María (docente, Central) tiene sesión vigente y el expediente 202 (Pacífico) tiene nota 91",
     "María envía POST /expedientes/202/nota con {\"nota\": 10}",
     "recibe 403 y la nota del expediente 202 sigue siendo 91"),
    ("CA-03", "SEC-03",
     "Ana revocó su sesión (o su sesión superó `expira_en`)",
     "Ana solicita GET /expedientes/101 con ese token",
     "recibe 401 sin datos del expediente"),
    ("CA-04", "SEC-04",
     "María tiene sesión vigente y el expediente 101 tiene nota 82",
     "María envía POST /expedientes/101/nota con {\"nota\": 101}",
     "recibe 400 y la nota del expediente 101 continúa en 82"),
    ("CA-05", "SEC-05",
     "Luis (estudiante) tiene sesión vigente y el ID 999 no existe",
     "Luis solicita GET /expedientes/999 y GET /expedientes/101 (de Ana)",
     "ambas respuestas son idénticas (403 y mismo cuerpo), de modo que no puede saber qué IDs existen"),
]

# ---------------------------------------------------------------- casos de prueba
# claves: id, tipo, titulo, req, amenaza, prioridad, objetivo, pre, entradas, pasos, esperado, nivel
CASOS = [
    dict(id="TC-01", tipo="Positivo", titulo="Estudiante lee su propio expediente", req="SEC-01", amenaza="R-01", prioridad="Alta",
         objetivo="Confirmar que el control no bloquea la lectura legítima.",
         pre="Sesión `lab-ana` vigente (Ana, estudiante, Central); expediente 101 de Ana con nota 82.",
         entradas="GET /expedientes/101 con `Authorization: Bearer lab-ana`.",
         pasos="1) Enviar la solicitud. 2) Revisar código y cuerpo.",
         esperado="200; cuerpo con estudiante `ana` y nota 82.", nivel="Unidad + API"),
    dict(id="TC-02", tipo="Negativo", titulo="Estudiante A intenta leer el expediente de B", req="SEC-01", amenaza="R-01", prioridad="Alta",
         objetivo="Verificar denegación sin filtrar datos (acceso horizontal).",
         pre="Sesión `lab-ana` vigente; expediente 202 pertenece a Luis (Pacífico), nota 91.",
         entradas="GET /expedientes/202 con `Bearer lab-ana`.",
         pasos="1) Enviar. 2) Comprobar código. 3) Buscar nota, estudiante, sede o `91` en el cuerpo. 4) Comparar los expedientes antes/después.",
         esperado="403; el cuerpo no contiene nota, estudiante ni sede; expedientes sin cambios.", nivel="Unidad + API"),
    dict(id="TC-03", tipo="Negativo", titulo="Docente de una sede cambia la nota de otra sede", req="SEC-02", amenaza="R-02", prioridad="Alta",
         objetivo="Verificar integridad entre sedes (acceso horizontal de escritura).",
         pre="Sesión `lab-maria` (docente, Central); expediente 202 (Pacífico) con nota 91.",
         entradas="POST /expedientes/202/nota con {\"nota\": 10}.",
         pasos="1) Enviar. 2) Comprobar código. 3) Releer el expediente 202 como administrador.",
         esperado="403; la nota de 202 permanece en 91; expedientes sin cambios.", nivel="Unidad + API"),
    dict(id="TC-04", tipo="Negativo", titulo="Sesión revocada o vencida", req="SEC-03", amenaza="R-04", prioridad="Alta",
         objetivo="Verificar que una sesión no vigente no accede a nada.",
         pre="a) `lab-ana` revocada con POST /sesiones/revocar. b) `lab-vencida` (marcada vencida). c) sesión marcada `expirada` con `expira_en` futuro.",
         entradas="GET /expedientes/101 y POST /expedientes/101/nota con cada token.",
         pasos="1) Revocar (caso a). 2) Solicitar lectura y escritura. 3) Repetir con b y c.",
         esperado="401 en todos; cuerpo sin datos; nota intacta.", nivel="Unidad + API"),
    dict(id="TC-05", tipo="Frontera", titulo="Nota fuera de [0,100]", req="SEC-04", amenaza="R-05", prioridad="Media",
         objetivo="Rechazar valores justo fuera del rango y no persistirlos.",
         pre="Sesión `lab-maria` vigente; expediente 101 con nota 82.",
         entradas="Notas -1, -0.01, 100.01, 101 y 1000.",
         pasos="1) Enviar cada valor. 2) Comprobar 400. 3) Releer la nota.",
         esperado="400 en cada caso; la nota sigue en 82.", nivel="Unidad + API"),
    dict(id="TC-06", tipo="Positivo", titulo="Docente cambia una nota de su sede", req="SEC-02", amenaza="R-02", prioridad="Alta",
         objetivo="Confirmar que el cambio legítimo funciona y persiste.",
         pre="Sesión `lab-maria` (Central); expediente 101 (Central) con nota 82.",
         entradas="POST /expedientes/101/nota con {\"nota\": 85}.",
         pasos="1) Enviar. 2) Releer el expediente.",
         esperado="200; la nota persistida es 85.", nivel="Unidad + API"),
    dict(id="TC-07", tipo="Positivo", titulo="Administrador lee expedientes de ambas sedes", req="SEC-01", amenaza="R-01", prioridad="Media",
         objetivo="Confirmar que el administrador conserva la lectura global.",
         pre="Sesión `lab-admin`; expedientes 101 (Central) y 202 (Pacífico).",
         entradas="GET /expedientes/101 y GET /expedientes/202.",
         pasos="1) Enviar ambas solicitudes.",
         esperado="200 en ambas.", nivel="Unidad"),
    dict(id="TC-08", tipo="Negativo", titulo="Administrador intenta cambiar una nota", req="SEC-02", amenaza="R-03", prioridad="Alta",
         objetivo="Verificar escalada vertical: el administrador es solo lectura.",
         pre="Sesión `lab-admin`; expediente 101 con nota 82.",
         entradas="POST /expedientes/101/nota con {\"nota\": 100}.",
         pasos="1) Enviar. 2) Releer el expediente.",
         esperado="403; nota intacta.", nivel="Unidad + API (ps1)"),
    dict(id="TC-09", tipo="Negativo", titulo="Estudiante intenta cambiar su propia nota", req="SEC-02", amenaza="R-03", prioridad="Alta",
         objetivo="Verificar escalada vertical del estudiante.",
         pre="Sesión `lab-ana`; expediente 101 con nota 82.",
         entradas="POST /expedientes/101/nota con {\"nota\": 100}.",
         pasos="1) Enviar. 2) Releer el expediente.",
         esperado="403; nota intacta.", nivel="Unidad + API (ps1)"),
    dict(id="TC-10", tipo="Negativo", titulo="Docente intenta leer un expediente de otra sede", req="SEC-01", amenaza="R-02", prioridad="Alta",
         objetivo="Verificar la lectura restringida a la sede propia.",
         pre="Sesión `lab-maria` (Central); expediente 202 (Pacífico).",
         entradas="GET /expedientes/202 con `Bearer lab-maria`.",
         pasos="1) Enviar. 2) Revisar código y cuerpo.",
         esperado="403; el cuerpo no contiene nota, estudiante ni sede.", nivel="Unidad"),
    dict(id="TC-11", tipo="Frontera", titulo="Notas límite 0 y 100", req="SEC-04", amenaza="R-05", prioridad="Media",
         objetivo="Confirmar que los extremos inclusivos se aceptan.",
         pre="Sesión `lab-maria`; expediente 101.",
         entradas="Notas 0 y 100.",
         pasos="1) Enviar 0. 2) Enviar 100. 3) Releer tras cada envío.",
         esperado="200 en ambos; la nota persistida coincide.", nivel="Unidad + API (ps1)"),
    dict(id="TC-12", tipo="Frontera", titulo="Expediente inexistente no permite enumerar IDs", req="SEC-05", amenaza="R-07", prioridad="Media",
         objetivo="Verificar que 999 (inexistente) y 202 (ajeno) son indistinguibles para no administradores.",
         pre="Sesiones `lab-ana`, `lab-maria`, `lab-admin`; el ID 999 no existe.",
         entradas="GET /expedientes/999 y GET /expedientes/202 con cada token.",
         pasos="1) Solicitar ambos IDs por rol. 2) Comparar código y cuerpo.",
         esperado="Estudiante y docente: respuestas idénticas (403). Administrador: 404 sin datos.", nivel="Unidad + API (ps1)"),
    # ---- casos adicionales (no cuentan para el mínimo de 12)
    dict(id="TC-13", tipo="Negativo", titulo="Token ausente o desconocido", req="SEC-03", amenaza="R-04", prioridad="Alta",
         objetivo="Sin sesión no hay acceso.",
         pre="Ninguna.", entradas="GET /expedientes/101 sin cabecera y con `Bearer lab-inexistente`.",
         pasos="1) Enviar ambas.", esperado="401; cuerpo sin datos.", nivel="Unidad + API (ps1)"),
    dict(id="TC-14", tipo="Negativo", titulo="Tipos inválidos de nota", req="SEC-04", amenaza="R-05", prioridad="Media",
         objetivo="Rechazar valores que no son números reales.",
         pre="Sesión `lab-maria`.", entradas="\"85\", null, true, NaN, inf, [85].",
         pasos="1) Enviar cada valor.", esperado="400; nota intacta.", nivel="Unidad + API (ps1)"),
    dict(id="TC-15", tipo="Adicional", titulo="Auditoría registra denegados y nunca tokens", req="SEC-06", amenaza="R-06", prioridad="Media",
         objetivo="Verificar usuario/acción/resultado y ausencia de tokens.",
         pre="Estado nuevo.", entradas="Lectura propia, cambio legítimo y lectura ajena.",
         pasos="1) Ejecutar las tres operaciones. 2) Inspeccionar `estado[\"auditoria\"]`.",
         esperado="Resultados [permitida, permitida, denegada]; ningún campo `token`; ningún valor con `lab-`.", nivel="Unidad"),
    dict(id="TC-16", tipo="Negativo", titulo="El permiso se evalúa antes que la validación del dato", req="SEC-05", amenaza="R-05", prioridad="Media",
         objetivo="No revelar reglas de validación a quien no tiene permiso.",
         pre="Sesión `lab-ana`.", entradas="Nota 5000 por un estudiante.",
         pasos="1) Enviar.", esperado="403 (no 400).", nivel="Unidad"),
    dict(id="TC-17", tipo="Negativo", titulo="JSON mal formado o que no es objeto", req="SEC-07", amenaza="R-08", prioridad="Baja",
         objetivo="Rechazar cuerpos inválidos sin alterar datos.",
         pre="Sesión `lab-maria`.", entradas="`{nota:`, `[85]` y cuerpo vacío.",
         pasos="1) Enviar cada cuerpo.", esperado="400; nota intacta.", nivel="API"),
    dict(id="TC-18", tipo="Negativo", titulo="Content-Length negativo o excesivo", req="SEC-07", amenaza="R-08", prioridad="Baja",
         objetivo="Evitar solicitudes colgadas y cuerpos grandes.",
         pre="Sesión `lab-maria`.", entradas="Content-Length: -1 y Content-Length: 2048.",
         pasos="1) Enviar cada cabecera.", esperado="400 y 413 respectivamente.", nivel="API"),
    dict(id="TC-19", tipo="Frontera", titulo="Caducidad de la sesión por reloj", req="SEC-03", amenaza="R-04", prioridad="Alta",
         objetivo="La sesión caduca en `expira_en` (ciclo TDD 2).",
         pre="Reloj inyectado; `expira_en` = 1000.", entradas="Reloj en 999.999, 1000 y 1500; revocar tras vencer.",
         pasos="1) Fijar el reloj. 2) Leer y modificar.", esperado="200 antes del instante; 401 en y después del instante; toda sesión nueva tiene `expira_en`.", nivel="Unidad"),
    dict(id="TC-20", tipo="Negativo", titulo="Escribir sobre un ID inexistente no permite enumerar", req="SEC-05", amenaza="R-07", prioridad="Media",
         objetivo="El 403 de escritura es idéntico para IDs ajenos e inexistentes (ciclo TDD 1).",
         pre="Sesiones `lab-ana`, `lab-maria`, `lab-admin`.", entradas="POST nota sobre 202 y sobre 999.",
         pasos="1) Enviar a ambos IDs por rol.", esperado="Respuestas idénticas (403); datos intactos.", nivel="Unidad"),
    dict(id="TC-21", tipo="Adicional", titulo="Respuestas sin caché", req="SEC-05", amenaza="R-01", prioridad="Baja",
         objetivo="Evitar que proxies o navegadores guarden notas.",
         pre="Sesión `lab-ana`.", entradas="GET /expedientes/101.", pasos="1) Revisar cabeceras.",
         esperado="`Cache-Control: no-store`.", nivel="API"),
    dict(id="TC-22", tipo="Negativo", titulo="Sin sesión válida el 401 precede a la validación del cuerpo", req="SEC-03", amenaza="R-08", prioridad="Media",
         objetivo="Autenticar antes de interpretar el cuerpo (ciclo TDD 3).",
         pre="Ninguna.", entradas="POST con token ausente, desconocido o vencido y cuerpos inválidos.",
         pasos="1) Enviar 9 combinaciones.", esperado="401 en todas; el cuerpo no describe errores de validación.", nivel="API"),
    dict(id="TC-23", tipo="Negativo", titulo="El 401 llega completo aunque el cliente envíe cuerpo", req="SEC-07", amenaza="R-08", prioridad="Media",
         objetivo="El servidor consume el cuerpo antes de cerrar (ciclo TDD 4).",
         pre="Ninguna.", entradas="200 solicitudes sin sesión con cuerpo de ~900 bytes.",
         pasos="1) Repetir la solicitud 200 veces.", esperado="401 en todas; ninguna conexión abortada.", nivel="API"),
]

# ---------------------------------------------------------------- hallazgos
# Plantilla A.2. Campos: ver HALLAZGO_CAMPOS.
HALLAZGOS = [
    dict(id="H-01", titulo="Enumeración de expedientes por diferencia 404/403", severidad="Media",
         justificacion="Divulgación limitada (existencia de IDs), explotable por cualquier usuario autenticado y automatizable.",
         activo="A-01", req="SEC-05", casos="TC-12, TC-20", amenaza="R-07",
         pasos="1) Autenticarse como Ana. 2) GET /expedientes/999 → 404. 3) GET /expedientes/202 → 403. 4) Comparar.",
         esperado="Misma respuesta (403) para un ID inexistente y uno ajeno.", observado="404 `No existe` frente a 403 `Operación denegada`.",
         impacto="Permite descubrir qué expedientes existen.", estado_hallazgo="Confirmado",
         correccion="`leer_expediente` y `actualizar_nota` responden 403 por la misma función `_denegar`; solo el administrador recibe 404.",
         commits="a501914 (rojo), d7fe59d (verde), e29e531 (refactor)", evidencia="evidencias/tdd/ciclo1_*.txt; PM-07 y PM-08 en pruebas_manuales_api.md",
         fecha="2026-10-30", estado_final="Corregido y verificado", cierre="TC-12 y TC-20 en verde; mutantes M-09 y M-10 detectados."),
    dict(id="H-02", titulo="La caducidad de la sesión dependía solo de una bandera manual", severidad="Alta",
         justificacion="Una sesión nunca caducaba por tiempo: un token filtrado seguía válido indefinidamente.",
         activo="A-03", req="SEC-03", casos="TC-19", amenaza="R-04",
         pasos="1) Fijar `expira_en` en el pasado en una sesión sin bandera `expirada`. 2) Solicitar una lectura.",
         esperado="401.", observado="200 con los datos del expediente.",
         impacto="Reutilización de sesiones vencidas (R-04).", estado_hallazgo="Confirmado",
         correccion="`expira_en` + reloj inyectable `estado[\"ahora\"]`; `_sesion_vigente` unifica la regla.",
         commits="335dfc4 (rojo), 7f7fd23 (verde), a3719fd (refactor)", evidencia="evidencias/tdd/ciclo2_*.txt",
         fecha="2026-10-30", estado_final="Corregido y verificado", cierre="TC-19a/b/c/d en verde; mutante M-08 detectado."),
    dict(id="H-03", titulo="El servidor interpretaba el cuerpo antes de autenticar", severidad="Baja",
         justificacion="Revela reglas de validación a un cliente sin sesión; sin acceso a datos.",
         activo="A-06", req="SEC-03", casos="TC-22", amenaza="R-08",
         pasos="1) POST /expedientes/101/nota sin token con cuerpo `{nota:`.",
         esperado="401.", observado="400 `JSON inválido`.",
         impacto="Divulgación de comportamiento interno a no autenticados.", estado_hallazgo="Confirmado",
         correccion="Se autentica en `do_POST` antes de `_leer_nota`.",
         commits="ec13a34 (rojo), 724193d (verde), 7eff45f (refactor)", evidencia="evidencias/tdd/ciclo3_*.txt",
         fecha="2026-10-30", estado_final="Corregido y verificado", cierre="TC-22 en verde; mutante M-13 detectado."),
    dict(id="H-04", titulo="El 401 podía perderse si el cliente enviaba cuerpo", severidad="Baja",
         justificacion="Afecta disponibilidad/diagnóstico del control de sesiones; intermitente; sin fuga de datos.",
         activo="A-06", req="SEC-03, SEC-07", casos="TC-23", amenaza="R-08",
         pasos="1) Repetir 200 veces POST sin token con ~900 bytes de cuerpo.",
         esperado="401 siempre.", observado="`ConnectionAbortedError` (RST) en parte de las solicitudes.",
         impacto="El cliente no recibe la denegación; comportamiento no determinista.", estado_hallazgo="Confirmado",
         correccion="`_descartar_cuerpo` consume (sin interpretar) hasta 1024 bytes antes de responder el 401.",
         commits="9f73de3 (rojo), fff5be1 (verde), dafa7ba (refactor)", evidencia="evidencias/tdd/ciclo4_*.txt",
         fecha="2026-10-30", estado_final="Corregido y verificado", cierre="TC-23 en verde (200 repeticiones) y 5 corridas completas sin intermitencia."),
    dict(id="H-05", titulo="Debilidades de la propia suite (fallo de la prueba, no del producto)", severidad="Baja",
         justificacion="Una prueba que no puede fallar da falsa confianza, aunque no expone datos por sí sola.",
         activo="Suite de pruebas", req="SEC-01, SEC-03", casos="TC-02, TC-10, TC-04",
         amenaza="-",
         pasos="1) Revisar oráculos de TC-02/TC-10. 2) Ejecutar `tools/mutaciones.py` y revisar sobrevivientes.",
         esperado="Los oráculos verifican respuesta, ausencia de filtración y estado; cada control tiene una prueba que falla si se rompe.",
         observado="TC-10 solo buscaba la clave `nota`; varias denegaciones no comprobaban el estado; la mutación M-07 sobrevivía (la bandera `expirada` quedaba tapada por el reloj).",
         impacto="Regresiones no detectadas en lectura entre sedes y en la bandera de expiración.", estado_hallazgo="Confirmado",
         correccion="`assertSinDatosProtegidos` (nota, estudiante, sede), `assertExpedientesIntactos` y la prueba TC-04c.",
         commits="8ca9385, b6fc0a5", evidencia="evidencias/mutaciones_primera_ejecucion.txt y evidencias/mutaciones.md",
         fecha="2026-10-30", estado_final="Corregido y verificado", cierre="15 de 15 mutaciones detectadas."),
    dict(id="H-06", titulo="Los intentos sin sesión válida y las revocaciones no se auditan", severidad="Baja",
         justificacion="Sin usuario identificable no hay a quién atribuir el intento; no expone datos.",
         activo="A-04", req="SEC-06", casos="TC-15", amenaza="R-06",
         pasos="1) Enviar una solicitud con token desconocido. 2) Revisar `estado[\"auditoria\"]`.",
         esperado="Un intento de autenticación fallido deja rastro.", observado="No se registra nada (`lab.py:102-103`, `lab.py:117-118`, `lab.py:132-137`).",
         impacto="Los ataques de adivinanza de tokens no quedan registrados.", estado_hallazgo="Confirmado",
         correccion="No corregido: requiere una política de registro (p. ej., resumen del token) fuera del alcance.",
         commits="-", evidencia="evidencias/inspeccion_estatica.md (C-19)",
         fecha="2026-10-30", estado_final="Aceptado formalmente como riesgo residual", cierre="Revisar en una versión con autenticación real."),
    dict(id="H-07", titulo="Estado compartido sin cerrojo ante solicitudes concurrentes", severidad="Baja",
         justificacion="El laboratorio es de un solo usuario en 127.0.0.1; no se ha reproducido una condición de carrera.",
         activo="A-01, A-02", req="SEC-02", casos="-", amenaza="-",
         pasos="Revisión estática de `servidor.py:9` con `ThreadingHTTPServer`.",
         esperado="Acceso serializado al estado compartido.", observado="Sin `threading.Lock`.",
         impacto="Posibles carreras entre lecturas y escrituras.", estado_hallazgo="Por investigar",
         correccion="No corregido; un sistema real usaría almacenamiento transaccional.",
         commits="-", evidencia="evidencias/inspeccion_estatica.md (C-21)",
         fecha="2026-10-30", estado_final="Aceptado formalmente como riesgo residual", cierre="Sin prueba de cierre; la condición no se reprodujo."),
    dict(id="H-08", titulo="No existe un manejador general de excepciones en el servidor", severidad="Baja",
         justificacion="Una excepción inesperada cierra la conexión y deja la traza solo en la consola local.",
         activo="A-06", req="SEC-07", casos="TC-17, TC-18", amenaza="R-08",
         pasos="Revisión estática de `servidor.py:57-71`.",
         esperado="Respuesta 500 genérica sin detalles.", observado="Comportamiento por defecto de `BaseHTTPRequestHandler`.",
         impacto="Diagnóstico menos claro; no se observa fuga de datos al cliente.", estado_hallazgo="Confirmado",
         correccion="No corregido en esta versión.",
         commits="-", evidencia="evidencias/inspeccion_estatica.md (C-11)",
         fecha="2026-10-30", estado_final="Aceptado formalmente como riesgo residual", cierre="Pendiente de una versión posterior."),
    dict(id="H-09", titulo="El 401 no envía WWW-Authenticate y el esquema Bearer distingue mayúsculas", severidad="Baja",
         justificacion="Afecta la usabilidad del cliente, no la confidencialidad.",
         activo="A-06", req="SEC-03", casos="TC-13", amenaza="-",
         pasos="1) Enviar `Authorization: bearer lab-ana` (minúscula). 2) Revisar cabeceras del 401.",
         esperado="El esquema se acepta sin distinguir mayúsculas y el 401 incluye `WWW-Authenticate: Bearer`.",
         observado="Token ignorado por `startswith(\"Bearer \")` y sin cabecera `WWW-Authenticate` (`servidor.py:_token`).",
         impacto="Clientes bien intencionados reciben un 401 difícil de diagnosticar.", estado_hallazgo="Confirmado",
         correccion="No corregido; se propone como mejora de usabilidad.",
         commits="-", evidencia="Sección de usabilidad del informe",
         fecha="2026-10-30", estado_final="Abierto", cierre="Candidato al siguiente ciclo TDD."),
]

HALLAZGO_CAMPOS = [
    ("id", "ID"), ("titulo", "Título"), ("severidad", "Severidad"), ("justificacion", "Justificación de la severidad"),
    ("activo", "Activo"), ("req", "Requisito"), ("casos", "Casos afectados"), ("amenaza", "Amenaza"),
    ("pasos", "Pasos para reproducir"), ("esperado", "Resultado esperado"), ("observado", "Resultado observado"),
    ("impacto", "Impacto"), ("estado_hallazgo", "Estado del hallazgo"), ("correccion", "Corrección o tratamiento"),
    ("commits", "Commits"), ("evidencia", "Evidencia"), ("fecha", "Fecha"), ("estado_final", "Estado final"),
    ("cierre", "Prueba de cierre"),
]

# Resultados no concluyentes y fallos de herramienta (no del producto)
NO_CONCLUYENTES = [
    ("NC-01", "bandit sin hallazgos", "Resultado no concluyente",
     "bandit analiza patrones inseguros genéricos; no conoce la política rol-sede, por lo que 'sin hallazgos' no demuestra que la autorización sea correcta. "
     "Se complementa con la lista de comprobación y las pruebas (evidencias/sast_bandit.txt)."),
    ("NC-02", "Error al grabar la primera evidencia roja (UnicodeDecodeError)", "Fallo de la herramienta, no del producto",
     "`tools/registrar_evidencia.py` leyó la salida de la suite con la codificación cp1252 de Windows. Se forzó UTF-8 en el subproceso; las pruebas no cambiaron."),
    ("NC-03", "Prueba intermitente TC-22 durante el ciclo 3", "Falso diagnóstico inicial resuelto",
     "El fallo ocasional parecía un problema de la prueba; la repetición de 200 solicitudes (TC-23) demostró que era un defecto real del servidor (H-04), por lo que se corrigió el producto y no la aserción."),
]

# Cambios de mantenibilidad en pruebas (Fase E: nombres, datos y mensajes)
AJUSTES_PRUEBAS = [
    ("test_N01_estudiante_no_consulta_expediente_ajeno", "test_TC02_estudiante_no_lee_expediente_ajeno",
     "El nombre incluye el ID del caso; la aserción ahora indica `lectura ajena` y se agrega la comprobación de que los expedientes no cambiaron."),
    ("test_F03_expediente_inexistente_da_404_sin_datos", "test_TC12_expediente_inexistente_no_permite_enumerar_ids",
     "El nombre describe el comportamiento de seguridad (no enumerar IDs); el mensaje de fallo explica la causa: `404 vs 403 permite enumerar expedientes`."),
    ("test_N02 / test_N03 (revocada, vencida)", "test_TC04a / test_TC04b / test_TC04c",
     "Un identificador por escenario facilita el diagnóstico: la prueba que falla indica si fue sesión revocada, vencida o con bandera."),
    ("test_X01_auditoria_no_contiene_tokens", "test_TC15_auditoria_registra_denegados_y_nunca_tokens",
     "Se verifica la secuencia exacta de resultados [permitida, permitida, denegada] además de la ausencia de tokens, y el mensaje muestra el registro filtrado."),
]

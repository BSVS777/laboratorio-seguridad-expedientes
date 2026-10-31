# Laboratorio local: seguridad de expedientes académicos

**Material didáctico, NO apto para producción.** Solo ejecutar en una máquina propia, en `127.0.0.1`, con datos y credenciales completamente ficticias. No publicar en Internet ni conectar a datos reales.

## Requisitos

- Python 3.10 o superior.
- Biblioteca estándar de Python: **no hay que instalar paquetes**.
- Opcional: un editor y Postman o PowerShell para peticiones HTTP.

## Primeros pasos (desde la carpeta del proyecto)

1. Ejecutar pruebas: `python -m unittest discover -s tests -v` (las 16 deben pasar en verde).
2. Ejecutar servidor local, en otra terminal: `python servidor.py`
3. Probar endpoint de salud: `curl.exe http://127.0.0.1:8765/health`
4. Detener con CTRL+C.

Para ejecutar todo de una vez (pruebas unitarias, servidor, 20 pruebas de API y resumen, regenerando `evidencia.txt`):
`powershell -ExecutionPolicy Bypass -File .\ejecutar_todo.ps1`

## Ejemplos de peticiones en Windows PowerShell

- Consulta legítima: `curl.exe -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/101`
- Consulta entre sedes (denegada con 403 y sin datos): `curl.exe -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/202`
- Cambio legítimo: `Invoke-RestMethod -Uri "http://127.0.0.1:8765/expedientes/101/nota" -Method Post -Headers @{ Authorization = "Bearer lab-maria" } -ContentType "application/json" -Body '{"nota":85}'`
- Revocar sesión: `curl.exe -X POST -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/sesiones/revocar`

Para reiniciar todos los datos y sesiones HTTP, detener y volver a ejecutar `servidor.py`.
Las pruebas `unittest` reinician el estado automáticamente antes de cada caso.

## Actores y reglas esperadas

| Actor | Token sintético | Sede | Permisos esperados |
| --- | --- | --- | --- |
| Ana, estudiante | `lab-ana` | Central | Leer solo su expediente 101 |
| Luis, estudiante | `lab-luis` | Pacífico | Leer solo su expediente 202 |
| María, docente | `lab-maria` | Central | Leer y modificar solo notas de su sede |
| Pedro, docente | `lab-pedro` | Pacífico | Leer y modificar solo notas de su sede |
| Admin | `lab-admin` | Global | Leer expedientes; no cambiar notas |
| Cuenta con sesión expirada | `lab-vencida` | Central | No debe consultar ni modificar |

Los códigos esperados para acceso denegado son `403`, para sesión ausente/revocada/expirada `401`, para datos inválidos `400`, y para operación permitida `200`. Para errores de permiso no incluir notas ni otros datos confidenciales; las decisiones no deben depender exclusivamente del código HTTP. Cualquier cambio rechazado debe conservar intacta la nota original.

## Trabajo estudiantil y dónde está cada entregable

| Requisito del laboratorio | Entregable |
| --- | --- |
| Requisitos (8), amenazas (7) y matriz requisito-riesgo-prueba | `INFORME.md` secciones 2 a 4 |
| 12 casos de diseño (3 positivos, 6 negativos, 3 frontera) + extras, todos automatizados | `INFORME.md` sección 5, `tests/test_laboratorio.py` |
| Dos ciclos TDD rojo-verde-refactor | `INFORME.md` sección 6 |
| Corrección de defectos (SEC-01 a SEC-06) y hallazgos | `src/lab.py`, `servidor.py`, `INFORME.md` sección 7 |
| Pruebas de API y evidencia de ejecución | `ejecutar_todo.ps1`, `evidencia.txt` |
| Dictamen de liberación o bloqueo con riesgo residual | `INFORME.md` sección 8 |
| Informe para entregar | `Informe_Seguridad_Expedientes.pdf` (completar nombre, curso y docente) |

El dictamen no afirma seguridad absoluta: es liberable solo como material didáctico local y está bloqueado para cualquier uso real.

## Estructura

- `src/lab.py`: modelo de negocio con los defectos SEC-01 a SEC-04 ya corregidos y auditoría sin tokens.
- `servidor.py`: API local mínima para pruebas HTTP (corrige además SEC-06).
- `tests/test_laboratorio.py`: suite de 16 pruebas (12 casos de diseño + 4 extras).
- `ejecutar_todo.ps1`: ejecuta pruebas unitarias y de API y regenera `evidencia.txt`.

El proyecto no usa contraseñas reales y los tokens no son credenciales reales. Los estudiantes **no deben copiar esta estrategia de autenticación a un sistema real**.

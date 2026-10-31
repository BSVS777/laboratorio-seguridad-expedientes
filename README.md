# Laboratorio local: seguridad de expedientes académicos

**Material didáctico, NO apto para producción.** Solo ejecutar en una máquina propia, en `127.0.0.1`, con datos y credenciales completamente ficticias.
No publicar en Internet ni conectar a datos reales. Los tokens (`lab-ana`, etc.) no son credenciales reales y esta estrategia de autenticación no debe copiarse a un sistema real.

## 1. Requisitos del entorno

| Requisito | Detalle |
| --- | --- |
| Python | 3.10 o superior (verificado con 3.12.10) |
| Paquetes | Ninguno: solo la biblioteca estándar de Python. **No hay que instalar nada** |
| Git | Para clonar el repositorio |
| Windows PowerShell + `curl.exe` | Opcional: pruebas manuales y `ejecutar_todo.ps1` |
| Microsoft Edge | Opcional: solo para regenerar `informe_seguridad.pdf` |

> **Windows:** si al escribir `python` se abre Microsoft Store, desactive el alias en *Configuración > Aplicaciones > Configuración avanzada de aplicaciones >
> Alias de ejecución de aplicaciones* (Python), o use `py` en lugar de `python` en todos los comandos.

## 2. Instalación

```
git clone https://github.com/BSVS777/laboratorio-seguridad-expedientes.git
cd laboratorio-seguridad-expedientes
python --version
```

No hay paso de instalación de dependencias. Todos los comandos siguientes se ejecutan **desde la carpeta raíz del proyecto**.

## 3. Comandos exactos

| Acción | Comando |
| --- | --- |
| Ejecutar toda la suite (34 pruebas, unidad e integración, unos 6 s) | `python -m unittest discover -s tests -v` |
| Solo pruebas de unidad | `python -m unittest tests.test_laboratorio -v` |
| Solo pruebas de integración con la API | `python -m unittest tests.test_api -v` |
| Iniciar el servidor local (otra terminal) | `python servidor.py` |
| Comprobar que responde | `curl.exe http://127.0.0.1:8765/health` |
| Detener el servidor | `CTRL+C` |
| Todo en uno (suite + servidor + 21 pruebas de API + resumen) | `powershell -ExecutionPolicy Bypass -File .\ejecutar_todo.ps1` |

Resultado esperado de la suite: `Ran 34 tests ... OK`. Todas las pruebas deben pasar; si alguna falla, es un defecto real o un problema del entorno, no un estado inicial "rojo".

## 4. Restablecer los datos sintéticos

- **Servidor:** detenga con `CTRL+C` y vuelva a ejecutar `python servidor.py`. Los expedientes, las sesiones (incluidas las revocadas) y la bitácora viven en memoria y se recrean al iniciar.
- **Pruebas `unittest`:** cada prueba crea un estado nuevo con `estado_inicial()`; las pruebas de API levantan su propio servidor en un puerto libre de 127.0.0.1. No hay que limpiar nada.
- Datos iniciales: expediente `101` (Ana, Central, nota 82) y `202` (Luis, Pacífico, nota 91).

## 5. Ejemplos de peticiones (Windows PowerShell)

- Consulta legítima: `curl.exe -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/101`
- Consulta entre sedes (403 sin datos): `curl.exe -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/202`
- Cambio legítimo: `Invoke-RestMethod -Uri "http://127.0.0.1:8765/expedientes/101/nota" -Method Post -Headers @{ Authorization = "Bearer lab-maria" } -ContentType "application/json" -Body '{"nota":85}'`
- Revocar sesión: `curl.exe -X POST -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/sesiones/revocar`

## 6. Actores y reglas esperadas

| Actor | Token sintético | Sede | Permisos esperados |
| --- | --- | --- | --- |
| Ana, estudiante | `lab-ana` | Central | Leer solo su expediente 101 |
| Luis, estudiante | `lab-luis` | Pacífico | Leer solo su expediente 202 |
| María, docente | `lab-maria` | Central | Leer y modificar solo notas de su sede |
| Pedro, docente | `lab-pedro` | Pacífico | Leer y modificar solo notas de su sede |
| Admin | `lab-admin` | Global | Leer expedientes; no cambiar notas |
| Cuenta con sesión vencida | `lab-vencida` | Central | No debe consultar ni modificar |

Códigos: `403` acceso denegado, `401` sesión ausente/desconocida/revocada/vencida, `400` datos inválidos, `413` cuerpo mayor a 1024 bytes, `200` operación permitida.
Las respuestas de error no incluyen notas ni datos confidenciales, y un ID inexistente es indistinguible de uno ajeno para quien no es administrador.
Cualquier cambio rechazado conserva intacta la nota original.

## 7. Estructura del repositorio

```
src/lab.py                      Modelo de negocio (autenticar, autorizar, validar, auditar)
servidor.py                     API HTTP local (127.0.0.1:8765)
tests/test_laboratorio.py       Pruebas de unidad (identificadores TC-xx en los nombres)
tests/test_api.py               Pruebas de integración contra el servidor real (puerto efímero)
ejecutar_todo.ps1               Suite + 21 pruebas de API con curl + evidencia
evidencias/                     Evidencias saneadas (ver sección 8)
tools/                          Herramientas de evidencia: registrar_evidencia, ejecucion_limpia, mutaciones
informe/                        Datos (datos.py), equipo (equipo.json) y generador del informe y los CSV
informe_seguridad.pdf           Informe técnico
matriz_trazabilidad.csv         Matriz requisito - riesgo - caso de prueba
casos_prueba.csv                Registro de los casos de prueba (plantilla A.1)
hallazgos.csv                   Bitácora de hallazgos (plantilla A.2)
```

## 8. Evidencias y cómo reproducirlas

| Evidencia | Ubicación | Cómo reproducirla |
| --- | --- | --- |
| Ciclos TDD rojo-verde-refactor con hash de commit | `evidencias/tdd/` (`REGISTRO_TDD.md`) | `git checkout <hash>` y `python -m unittest discover -s tests -v` (luego `git checkout main`) |
| Dos ejecuciones en estado limpio (clon nuevo) | `evidencias/ejecucion_limpia_1.txt`, `_2.txt` | `python tools/ejecucion_limpia.py` |
| Pruebas de API con `ejecutar_todo.ps1` | `evidencias/ejecucion_ps1.txt` | Comando de la sección 3 |
| Pruebas manuales por la API (curl) | `evidencias/pruebas_manuales_api.md` | Comandos incluidos en el archivo |
| Inspección estática y SAST (bandit) | `evidencias/inspeccion_estatica.md`, `evidencias/sast_bandit.txt` | Lista de comprobación; bandit es opcional |
| Prueba de mutación | `evidencias/mutaciones.md` | `python tools/mutaciones.py` (unos 2 minutos) |

Para registrar una evidencia propia: `python tools/registrar_evidencia.py evidencias/mi_evidencia.txt "Título"` (incluye fecha, versiones, commit y rutas saneadas).

## 9. Regenerar los entregables del informe

1. Complete `informe/equipo.json` (curso, integrantes, revisor, compañero). Los campos con `[COMPLETAR...]` o `[PENDIENTE...]` aparecen resaltados en el PDF.
2. `python informe/generar.py` ejecuta la suite, calcula las métricas, reescribe los tres CSV y genera `informe_seguridad.pdf` (requiere Microsoft Edge; sin él deja el HTML en `informe/_build/`).

## 10. Equipo y contribuciones

Cada integrante debe realizar al menos 2 commits significativos en al menos 2 días distintos. El informe calcula este requisito desde `git log` usando los autores de `informe/equipo.json`.

## 11. Reglas de seguridad de este laboratorio

Probar únicamente este laboratorio local (u otro sistema propio con autorización). No evaluar plataformas reales ni de terceros. No incluir tokens ni datos personales reales en el repositorio o el informe.
No alterar una aserción para ocultar un fallo confirmado.

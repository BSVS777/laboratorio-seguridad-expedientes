# Laboratorio local: seguridad de expedientes académicos

**Material didáctico, NO apto para producción.** Solo ejecutar en una máquina propia, en `127.0.0.1`, con datos y credenciales completamente ficticias. No publicar en Internet ni conectar a datos reales.

## Requisitos

- Python 3.10 o superior.
- Biblioteca estándar de Python: **no hay que instalar paquetes**.
- Opcional: un editor y Postman o PowerShell para peticiones HTTP.

## Primeros pasos (desde la carpeta del proyecto)

1. Ejecutar pruebas: `python -m unittest discover -s tests -v`
2. Observar que algunas pruebas **fallan intencionalmente**: es el estado rojo inicial (NO significa que falte instalar algo).
3. Ejecutar servidor local, en otra terminal: `python servidor.py`
4. Probar endpoint de salud: `curl.exe http://127.0.0.1:8765/health`
5. Detener con CTRL+C.

## Ejemplos de peticiones en Windows PowerShell

- Consulta legítima: `curl.exe -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/101`
- Consulta entre sedes (debería denegarse tras corrección): `curl.exe -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/202`
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

## Trabajo estudiantil

- Requisitos y amenazas: mínimo 6 requisitos, 5 amenazas, matriz requisito-riesgo-prueba.
- Diseñar 12 casos: 3 positivos, 6 negativos y 3 de frontera; mínimo 8 automatizados.
- Aplicar **dos ciclos TDD rojo-verde-refactor**. Los 2 tests iniciales marcados `test_rojo_...` son ejemplos, **no sustituyen la ampliación** de la suite.
- Corregir los problemas observados, inspeccionar código y pruebas, realizar pruebas de API y documentar hallazgos.
- Comprobar sesiones revocadas y expiradas, acceso horizontal y vertical, cambios no autorizados, valores de nota fuera de `[0,100]`, confidencialidad de respuestas y auditoría sin tokens.
- Presentar un dictamen de liberación o bloqueo con riesgo residual. Evitar afirmaciones de seguridad absoluta.

## Estructura

- `src/lab.py`: modelo de negocio con **defectos didácticos intencionales**.
- `servidor.py`: API local mínima para pruebas HTTP.
- `tests/test_laboratorio.py`: suite inicial con verificaciones positivas y dos casos rojos.

El proyecto no usa contraseñas reales y los tokens no son credenciales reales. Los estudiantes **no deben copiar esta estrategia de autenticación a un sistema real**.

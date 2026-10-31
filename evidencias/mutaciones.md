# Prueba de mutacion manual (¿las pruebas fallan cuando el control falla?)

Linea base sin mutar: 34 pruebas, todas aprobadas. Cada fila rompe **un** control en una copia temporal.
Resultado: **15 de 15 mutaciones detectadas** (100%).

| Mutacion | Requisito | Control roto | ¿Detectada? | Casos que fallan |
| --- | --- | --- | --- | --- |
| M-01 | SEC-01 | El docente puede leer expedientes de cualquier sede | Si | TC-10, TC-12 |
| M-02 | SEC-02 | El docente puede modificar notas de otra sede | Si | TC-03, TC-20 |
| M-03 | SEC-02 | Se elimina la comprobacion de rol docente al modificar | Si | TC-09, TC-16 |
| M-04 | SEC-04 | Se elimina la validacion de rango de la nota | Si | TC-05 |
| M-05 | SEC-04 | Un booleano se acepta como nota | Si | TC-14 |
| M-06 | SEC-03 | Una sesion revocada sigue autenticando | Si | TC-04 |
| M-07 | SEC-03 | Se ignora la bandera 'expirada' (antes la tapaba el reloj) | Si | TC-04 |
| M-08 | SEC-03 | La sesion no caduca por reloj | Si | TC-19 |
| M-09 | SEC-05 | Un ID inexistente responde 404 a cualquier rol (enumeracion) | Si | TC-12 |
| M-10 | SEC-05 | Escribir sobre un ID inexistente deja de ser 403 | Si | TC-20 |
| M-11 | SEC-06 | Las denegaciones dejan de auditarse | Si | TC-15 |
| M-12 | SEC-06 | La bitacora guarda un valor con forma de token | Si | TC-15 |
| M-13 | SEC-03 | El servidor procesa el cuerpo antes de autenticar | Si | TC-22 |
| M-14 | SEC-05 | Se elimina Cache-Control: no-store | Si | TC-21 |
| M-15 | SEC-07 | Se acepta Content-Length negativo | Si | TC-18 |

## Sobrevivientes
- Ninguno.

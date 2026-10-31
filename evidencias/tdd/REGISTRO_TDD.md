# Registro de evidencia TDD (rojo - verde - refactor)

Cada paso es un commit real del repositorio. La salida de la suite de cada paso esta en este mismo directorio
(generada con `python tools/registrar_evidencia.py`, con rutas saneadas). Puede verificarse con `git show <hash>`.

## Ciclo 1 - Acceso indebido: enumeracion de expedientes (SEC-05, amenaza R-07, relacionado con SEC-01)

Problema: para un estudiante o docente, un ID inexistente respondia `404 No existe` y un expediente ajeno
`403 Operacion denegada`. La diferencia permite descubrir que IDs existen (enumeracion).

| Paso | Commit | Evidencia | Resultado de la suite |
| --- | --- | --- | --- |
| ROJO | `a501914` | `ciclo1_1_ROJO.txt` | 27 pruebas, 2 fallos: TC-12 y TC-20 (`403 != 404`, la causa esperada) |
| VERDE | `d7fe59d` | `ciclo1_2_VERDE.txt` | 27 pruebas, OK. Cambio minimo: 403 auditado para IDs inexistentes a no administradores |
| REFACTOR | `e29e531` | `ciclo1_3_REFACTOR.txt` | 27 pruebas, OK. `_denegar()` centraliza todas las respuestas 403 |

Nota de honestidad: el criterio previo de TC-12 (`404` para el estudiante) codificaba la debilidad. Se reemplazo
conscientemente por el requisito SEC-05 y se anoto en el commit rojo; no se altero para ocultar un fallo.

## Ciclo 2 - Validez de sesion: caducidad por reloj (SEC-03, amenaza R-04)

Problema: la caducidad era solo una bandera booleana (`expirada`); una sesion con vigencia vencida seguia
autenticando y no existia caducidad real (riesgo residual declarado en la primera version del informe).

| Paso | Commit | Evidencia | Resultado de la suite |
| --- | --- | --- | --- |
| ROJO | `335dfc4` | `ciclo2_1_ROJO.txt` | 31 pruebas, 4 fallos: TC-19a/b/c (`401 != 200`) y TC-19d (sin `expira_en`) |
| VERDE | `7f7fd23` | `ciclo2_2_VERDE.txt` | 31 pruebas, OK. Cambio minimo: `expira_en` + reloj inyectable `estado["ahora"]` |
| REFACTOR | `a3719fd` | `ciclo2_3_REFACTOR.txt` | 31 pruebas, OK. `_sesion_vigente()` unifica `autenticar` y `revocar_sesion` |

## Ciclo 3 (adicional) - Sesion: autenticar antes de interpretar el cuerpo (SEC-03, amenaza R-08)

Problema, hallado en la inspeccion estatica y confirmado de forma dinamica: una solicitud POST sin sesion y con JSON mal
formado recibia `400 JSON invalido` en lugar de `401`, revelando reglas de validacion a quien no esta autenticado.

| Paso | Commit | Evidencia | Resultado de la suite |
| --- | --- | --- | --- |
| ROJO | `ec13a34` | `ciclo3_1_ROJO.txt` | 32 pruebas, 1 fallo: TC-22 (`401 != 400`) |
| VERDE | `724193d` | `ciclo3_2_VERDE.txt` | 32 pruebas, OK. Se autentica antes de leer el cuerpo |
| REFACTOR | `7eff45f` | `ciclo3_3_REFACTOR.txt` | 32 pruebas, OK. `no_autenticado()` define el 401 una sola vez |

## Ciclo 4 (adicional) - El 401 podia perderse si el cliente enviaba cuerpo (SEC-03 / SEC-07)

Problema: al aplicar el ciclo 3 aparecio una prueba intermitente (`ConnectionAbortedError`). Causa: el servidor
respondia 401 y cerraba la conexion con el cuerpo de la solicitud sin leer; el sistema operativo reinicia la conexion (RST)
y el cliente puede perder la respuesta. Se confirmo como defecto del servidor (no de la prueba) repitiendo la solicitud.

| Paso | Commit | Evidencia | Resultado de la suite |
| --- | --- | --- | --- |
| ROJO | `9f73de3` | `ciclo4_1_ROJO.txt` | 34 pruebas, 1 error: TC-23 (`ConnectionAbortedError`, reproducible 3 de 3) |
| VERDE | `fff5be1` | `ciclo4_2_VERDE.txt` | 34 pruebas, OK (5 corridas completas seguidas sin intermitencia) |
| REFACTOR | `dafa7ba` | `ciclo4_3_REFACTOR.txt` | 34 pruebas, OK. `_leer_nota()` aisla la lectura del cuerpo |

## Mejora de la suite derivada de la prueba de mutacion

La primera ejecucion de `tools/mutaciones.py` dejo un mutante vivo (M-07: ignorar la bandera `expirada`), porque el reloj
la tapaba (`mutaciones_primera_ejecucion.txt`). Se agrego TC-04c en el commit `b6fc0a5` y todas las mutaciones quedaron
detectadas (`mutaciones.md`).

## Como reproducir un paso

```
git checkout <hash>
python -m unittest discover -s tests -v
git checkout main
```

## Limitacion declarada

El codigo base disponible en el repositorio ya contenia las correcciones de autorizacion, sesiones revocadas y
validacion de nota; no se conserva una version vulnerable ni su historial, por eso los dos ciclos rojo-verde-refactor documentados aqui se ejecutaron sobre
debilidades que seguian abiertas y se registraron con hashes verificables.

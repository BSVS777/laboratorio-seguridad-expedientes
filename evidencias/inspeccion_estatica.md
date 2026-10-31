# Inspeccion estatica con lista de comprobacion (SAST manual)

Tecnica: **analisis estatico**, el codigo se lee sin ejecutarlo. Se distingue del analisis dinamico (`pruebas_manuales_api.md`,
`ejecucion_ps1.txt`), donde si se envian solicitudes HTTP al servidor.

- Alcance: `src/lab.py` y `servidor.py`, commit `dafa7ba` (despues de los cuatro ciclos TDD).
- Herramienta adicional: bandit 1.9.4 (`sast_bandit.txt`): sin hallazgos; resultado **no concluyente** para reglas de negocio (ver el final).
- Referencias de linea: `lab.py:N` y `servidor.py:N` en ese commit.

## Lista de comprobacion

| # | Area | Pregunta de comprobacion | Resultado | Evidencia en el codigo | Requisito |
| --- | --- | --- | --- | --- | --- |
| C-01 | Permisos | La lectura depende de rol, sede y propiedad, no solo de tener sesion | Cumple | `lab.py:79-88` (`_puede_leer`), `lab.py:109-110` | SEC-01 |
| C-02 | Permisos | Solo el docente de la sede del expediente puede modificar notas | Cumple | `lab.py:122` | SEC-02 |
| C-03 | Permisos | El permiso se evalua antes que la validacion del dato | Cumple | `lab.py:122-126` (403 antes que 400) | SEC-05 |
| C-04 | Permisos | Hay una unica via de decision de acceso, sin rutas alternas que la eviten | Cumple | Toda lectura/escritura pasa por `autenticar` + `_puede_leer` (`lab.py:109`) o la condicion de `lab.py:122`; `servidor.py` no accede a `estado["expedientes"]` | SEC-01, SEC-02 |
| C-05 | Sesiones | Sesion ausente, desconocida, revocada o expirada (bandera o reloj) se rechaza | Cumple | `lab.py:45-52` | SEC-03 |
| C-06 | Sesiones | Revocar una sesion invalida produce el mismo 401 (no revela su estado) | Cumple | `lab.py:132-135`, `lab.py:61-63` | SEC-03 |
| C-07 | Validacion | La nota se valida por tipo y rango; rechaza bool, NaN e infinito | Cumple | `lab.py:91-97` | SEC-04 |
| C-08 | Validacion | El cuerpo JSON se valida (objeto, tamano maximo, Content-Length) | Cumple | `servidor.py:24-37` (`_leer_nota`) | SEC-07 |
| C-09 | Validacion | El ID de la ruta se usa solo como clave de un diccionario (sin archivos ni SQL) | Cumple | `lab.py:104`, `lab.py:119` | SEC-01 |
| C-10 | Manejo de errores | Los errores esperados no producen trazas ni detalles internos hacia el cliente | Cumple | `servidor.py:36-37` captura `ValueError`/`UnicodeError`; mensajes fijos | SEC-05, SEC-07 |
| C-11 | Manejo de errores | Existe un manejador general para excepciones inesperadas | Parcial | `servidor.py:57-71`: una excepcion no prevista la trata `BaseHTTPRequestHandler` (cierra la conexion y escribe la traza en la consola del servidor, no al cliente) | SEC-07 |
| C-12 | Exposicion de datos | 401/403/400 no incluyen campos del expediente | Cumple | `lab.py:63`, `lab.py:76`, `lab.py:126` | SEC-05 |
| C-13 | Exposicion de datos | Un ID inexistente no se distingue de uno ajeno para quien no es administrador | Cumple (corregido en el ciclo TDD 1) | `lab.py:105-108`, `lab.py:122` | SEC-05 |
| C-14 | Exposicion de datos | Las respuestas no se guardan en cache | Cumple | `servidor.py:43` (`Cache-Control: no-store`) | SEC-05 |
| C-15 | Exposicion de datos | El registro del servidor no escribe el encabezado `Authorization` | Cumple | `servidor.py:73-75` (solo linea de solicitud y codigo) | SEC-06 |
| C-16 | Exposicion de datos | La respuesta 200 devuelve una copia del expediente, no la referencia interna | Cumple | `lab.py:112`, `lab.py:129` (`dict(expediente)`) | SEC-01 |
| C-17 | Auditoria | Se registra usuario, accion, ID y resultado y nunca el token | Cumple | `lab.py:66-70` | SEC-06 |
| C-18 | Auditoria | Los intentos denegados y rechazados tambien se auditan | Cumple | `lab.py:75`, `lab.py:125` | SEC-06 |
| C-19 | Auditoria | Los intentos sin sesion valida (401) y las revocaciones se auditan | **No cumple** (limitacion) | `lab.py:102-103`, `lab.py:117-118`, `lab.py:132-137` no llaman a `_auditar` | SEC-06 |
| C-20 | Configuracion | El servidor solo escucha en la interfaz local | Cumple | `servidor.py:79` (`127.0.0.1`) | Reglas de seguridad |
| C-21 | Concurrencia | El estado compartido esta protegido ante solicitudes simultaneas | **No cumple** (limitacion) | `servidor.py:9` (estado de clase) con `ThreadingHTTPServer` y sin cerrojo | SEC-02 |
| C-22 | Secretos | No hay credenciales reales en el repositorio | Cumple | Tokens `lab-*` ficticios en `lab.py:38-40` | Reglas de seguridad |
| C-23 | Sesiones | La autenticacion ocurre antes de procesar el cuerpo de la solicitud | Cumple (corregido en el ciclo TDD 3; antes: No cumple) | `servidor.py:63-65` | SEC-03 |
| C-24 | Sesiones | El servidor consume el cuerpo pendiente antes de cerrar, para que el 401 no se pierda por un reinicio de la conexion | Cumple (corregido en el ciclo TDD 4; antes: No cumple) | `servidor.py:15-22`, `servidor.py:64` | SEC-03, SEC-07 |

## Resumen

- 24 comprobaciones: **21 cumplen**, **1 parcial** (C-11) y **2 no cumplen** (C-19, C-21).
- C-13, C-23 y C-24 eran no conformidades confirmadas y se corrigieron con TDD (hallazgos H-01, H-03 y H-04, ver `hallazgos.csv`).
- C-11, C-19 y C-21 son **limitaciones aceptadas del laboratorio** (hallazgos H-08, H-06 y H-07), no defectos de los requisitos elegidos:
  - C-19: los intentos sin sesion valida no tienen un usuario identificable; auditarlos exige una politica adicional
    (por ejemplo, registrar un resumen del token) que el alcance del laboratorio no define.
  - C-21: el laboratorio es de un solo usuario en 127.0.0.1; un sistema real usaria un almacenamiento transaccional.

## Alertas no concluyentes y falsos positivos

- bandit no genero alertas. Esto **no demuestra** que la autorizacion sea correcta: una herramienta SAST generica no conoce
  la politica rol-sede. El resultado es **no concluyente** para SEC-01..SEC-05 y se verifica con pruebas unitarias, de
  integracion y manuales. No hubo falsos positivos que descartar.

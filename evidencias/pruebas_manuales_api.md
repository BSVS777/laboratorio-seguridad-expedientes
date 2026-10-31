# Pruebas manuales de la API (analisis dinamico)

Ejecutadas con `curl` contra el servidor local autorizado (`python servidor.py`, 127.0.0.1:8765) con el estado sintetico recien iniciado.
Fecha: 2026-10-30T21:42:35-06:00 · curl 8.21.0 · Python 3.12.10 · commit base `7b62895`.
Los tokens son ficticios del laboratorio. La salida se copio sin modificar (solo se normalizaron saltos de linea).

Esto es analisis **dinamico** (el sistema se ejecuta y se observa su comportamiento). La revision del codigo sin ejecutarlo esta en `inspeccion_estatica.md`.
Las solicitudes se pueden repetir en Windows PowerShell con `curl.exe` (con la `.exe`, para no invocar el alias de `Invoke-WebRequest`).

## PM-01 - Ana intenta leer el expediente de Luis

- Caso relacionado: TC-02 / SEC-01 (acceso horizontal entre estudiantes)

```
> curl.exe -s -i -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/202
HTTP/1.0 403 Forbidden
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 32

{"error": "Operación denegada"}
```

## PM-02 - Maria (Central) intenta cambiar la nota de un expediente de Pacifico

- Caso relacionado: TC-03 / SEC-02 (acceso entre sedes, escritura)

```
> curl.exe -s -i -X POST -H "Authorization: Bearer lab-maria" -H "Content-Type: application/json" -d '{"nota":10}' http://127.0.0.1:8765/expedientes/202/nota
HTTP/1.0 403 Forbidden
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 32

{"error": "Operación denegada"}
```

## PM-03 - Maria envia una nota fuera de rango (101)

- Caso relacionado: TC-05 / SEC-04 (entrada invalida)

```
> curl.exe -s -i -X POST -H "Authorization: Bearer lab-maria" -H "Content-Type: application/json" -d '{"nota":101}' http://127.0.0.1:8765/expedientes/101/nota
HTTP/1.0 400 Bad Request
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 27

{"error": "Nota inválida"}
```

## PM-04 - Maria envia JSON mal formado

- Caso relacionado: TC-17 / SEC-07 (entrada invalida)

```
> curl.exe -s -i -X POST -H "Authorization: Bearer lab-maria" -H "Content-Type: application/json" -d '{nota:' http://127.0.0.1:8765/expedientes/101/nota
HTTP/1.0 400 Bad Request
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 27

{"error": "JSON inválido"}
```

## PM-05 - Ana revoca su sesion

- Caso relacionado: TC-04 / SEC-03 (sesion revocada, paso 1)

```
> curl.exe -s -i -X POST -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/sesiones/revocar
HTTP/1.0 200 OK
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 31

{"mensaje": "Sesión revocada"}
```

## PM-06 - Ana reutiliza la sesion revocada

- Caso relacionado: TC-04 / SEC-03 (sesion revocada, paso 2)

```
> curl.exe -s -i -H "Authorization: Bearer lab-ana" http://127.0.0.1:8765/expedientes/101
HTTP/1.0 401 Unauthorized
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 27

{"error": "No autenticado"}
```

## PM-07 - Luis consulta un ID inexistente (999)

- Caso relacionado: TC-12 / SEC-05 (enumeracion, estudiante)

```
> curl.exe -s -i -H "Authorization: Bearer lab-luis" http://127.0.0.1:8765/expedientes/999
HTTP/1.0 403 Forbidden
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 32

{"error": "Operación denegada"}
```

## PM-08 - El administrador consulta un ID inexistente (999)

- Caso relacionado: TC-12 / SEC-05 (enumeracion, administrador)

```
> curl.exe -s -i -H "Authorization: Bearer lab-admin" http://127.0.0.1:8765/expedientes/999
HTTP/1.0 404 Not Found
Server: BaseHTTP/0.6 Python/3.12.10
Date: Sat, 31 Oct 2026 03:42:35 GMT
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
Content-Length: 22

{"error": "No existe"}
```

## PM-09 - El administrador comprueba que el expediente 101 conserva su nota original (82)

- Caso relacionado: Integridad tras los rechazos (SEC-02, SEC-04)

```
> curl.exe -s -H "Authorization: Bearer lab-admin" http://127.0.0.1:8765/expedientes/101
{"id": "101", "estudiante": "ana", "sede": "Central", "nota": 82}
```

## PM-10 - El administrador comprueba que el expediente 202 conserva su nota original (91)

- Caso relacionado: Integridad tras los rechazos (SEC-02)

```
> curl.exe -s -H "Authorization: Bearer lab-admin" http://127.0.0.1:8765/expedientes/202
{"id": "202", "estudiante": "luis", "sede": "Pacifico", "nota": 91}
```

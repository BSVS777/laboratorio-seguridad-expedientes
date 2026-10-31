# Informe: seguridad de expedientes académicos (laboratorio local)

> Material didáctico. Datos y tokens ficticios, solo en 127.0.0.1. Este informe describe lo verificado en el laboratorio; no afirma seguridad absoluta.

## 1. Actores y alcance
Estudiantes (Ana/Central, Luis/Pacífico), docentes (María/Central, Pedro/Pacífico), Admin (global) y una sesión expirada. Operaciones: leer expediente, actualizar nota, revocar sesión.

## 2. Requisitos de seguridad
| ID | Requisito |
| --- | --- |
| R1 | Un estudiante solo puede leer su propio expediente. |
| R2 | Un docente solo puede leer y modificar notas de expedientes de su sede. |
| R3 | El administrador puede leer todos los expedientes pero no modificar notas. |
| R4 | Sesiones ausentes, desconocidas, revocadas o expiradas reciben 401 y no acceden a nada. |
| R5 | La nota debe ser un número real en [0,100]; cualquier otro valor da 400. |
| R6 | Las respuestas de error (401/403/400) no incluyen notas ni datos confidenciales. |
| R7 | Un cambio rechazado deja intacta la nota original. |
| R8 | La auditoría registra usuario, acción y resultado, nunca el token. |

## 3. Amenazas
| ID | Amenaza | Categoría |
| --- | --- | --- |
| A1 | Acceso horizontal: Ana lee el expediente de Luis (IDOR). | Divulgación de información |
| A2 | Acceso vertical: estudiante o admin modifican notas. | Elevación de privilegios |
| A3 | Docente de una sede modifica o lee notas de otra sede. | Elevación / divulgación |
| A4 | Reutilización de sesión revocada o expirada. | Suplantación |
| A5 | Notas manipuladas con valores fuera de rango o de tipo inesperado (-1, 1000, true, NaN). | Manipulación de datos |
| A6 | Fuga de tokens por la bitácora de auditoría. | Divulgación de información |
| A7 | Mensajes de error que revelan datos o reglas internas. | Divulgación de información |

## 4. Matriz requisito - riesgo - prueba
| Requisito | Amenaza | Defecto | Pruebas |
| --- | --- | --- | --- |
| R1 | A1 | SEC-01 | N01, P01 |
| R2 | A3 | SEC-01 / SEC-02 | N04, N06, P02 |
| R3 | A2 | SEC-02 | N05, P03 |
| R4 | A4 | SEC-03 | N02, N03, N07 |
| R5 | A5 | SEC-04 | N08, F01, F02 |
| R6 | A7 | SEC-01 | N01, N04, F03 |
| R7 | A5 | SEC-02 / SEC-04 | N03, N04, N08, F02 |
| R8 | A6 | Auditoría | X01 |

## 5. Los 12 casos de diseño (todos automatizados)
**Positivos (3):** P01 estudiante lee lo suyo; P02 docente cambia nota en su sede; P03 admin lee ambas sedes.
**Negativos (6):** N01 estudiante lee expediente ajeno; N02 sesión revocada; N03 sesión expirada (lectura y escritura); N04 docente cambia nota de otra sede; N05 estudiante/admin cambian nota; N06 docente lee otra sede.
**Frontera (3):** F01 notas 0 y 100 aceptadas; F02 notas -1, -0.01, 100.01, 101, 1000 rechazadas; F03 expediente inexistente (404 sin datos).
**Extras:** N07 token vacío/desconocido; N08 tipos inválidos (texto, null, true, NaN, inf, lista); X01 auditoría sin tokens; X02 permisos antes que validación de datos.

Total: 16 pruebas unitarias + 20 pruebas de API (`ejecutar_todo.ps1`).

## 6. TDD
**Ciclo 1 (SEC-01 y SEC-03)**
- Rojo: N01, N06 (lectura entre estudiantes y entre sedes devolvía 200 con la nota), N02/N03 (sesión revocada y expirada devolvía 200).
- Verde: `_puede_leer()` por rol/sede/propiedad y `autenticar()` que rechaza revocada/expirada.
- Refactor: la política de lectura quedó en una función única y la auditoría en `_auditar()`.

**Ciclo 2 (SEC-02 y SEC-04)**
- Rojo: N04 (María cambiaba notas de Pacífico), N08 (`true` se aceptaba como nota) y F02 (rangos).
- Verde: verificación de sede en `actualizar_nota()` y `_nota_valida()` (rechaza bool, NaN, infinito y fuera de [0,100]).
- Refactor: permisos se evalúan antes que la validación del dato (X02), para no revelar reglas a quien no tiene permiso.

Antes de corregir, la suite nueva dio **8 fallos de 16**; después de corregir, **16 de 16 en verde**.

## 7. Hallazgos
| ID | Severidad | Hallazgo | Corrección |
| --- | --- | --- | --- |
| SEC-01 | Alta | Cualquier sesión válida leía cualquier expediente (horizontal y entre sedes). | Autorización por rol, sede y propiedad; 403 sin datos. |
| SEC-02 | Alta | Cualquier docente modificaba notas de otra sede. | Verificación de sede; 403 y nota intacta. |
| SEC-03 | Alta | Sesiones revocadas y expiradas seguían autenticando; revocar no tenía efecto real. | `autenticar()` las rechaza con 401. |
| SEC-04 | Media | Se aceptaban notas fuera de [0,100] y booleanos (`True` cuenta como número en Python). | `_nota_valida()`. |
| SEC-05 | Media | La auditoría guardaba el token completo. | Se registra usuario, acción, id y resultado. Los denegados también se auditan. |
| SEC-06 | Baja | Content-Length negativo en el servidor podía dejar la petición esperando datos. | Se responde 400. |

## 8. Dictamen de liberación
**Para el alcance del laboratorio (uso didáctico local): LIBERABLE.** Los defectos SEC-01 a SEC-06 están corregidos y verificados con pruebas unitarias y de API.

**Para cualquier uso real: BLOQUEADO.** Riesgo residual:
- La autenticación es sintética: los tokens son texto fijo (`lab-ana`), sin firma, contraseñas ni caducidad real.
- Las sesiones "expiradas" son una bandera; no hay reloj ni expiración automática.
- No hay HTTPS, límite de intentos, protección contra fuerza bruta ni aislamiento por tenant en el almacenamiento.
- Un 404 frente a un 403 permite confirmar si un ID de expediente existe (enumeración).
- La auditoría vive en memoria y no es inmutable.
- La cobertura se limita a los casos diseñados; no sustituye una revisión de seguridad completa.

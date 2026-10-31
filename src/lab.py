"""Laboratorio didactico (version CORREGIDA).

No reutilizar en produccion: los tokens son sinteticos y no hay autenticacion real.
Correcciones: SEC-01 autorizacion en lectura, SEC-02 sede del docente,
SEC-03 sesiones revocadas/expiradas, SEC-04 validacion de nota, y auditoria sin tokens.
"""
import math

USUARIOS = {
    "ana": {"id": "ana", "rol": "estudiante", "sede": "Central"},
    "luis": {"id": "luis", "rol": "estudiante", "sede": "Pacifico"},
    "maria": {"id": "maria", "rol": "docente", "sede": "Central"},
    "pedro": {"id": "pedro", "rol": "docente", "sede": "Pacifico"},
    "admin": {"id": "admin", "rol": "administrador", "sede": None},
}

NOTA_MIN, NOTA_MAX = 0, 100


def estado_inicial():
    """Crea datos de laboratorio independientes para cada ejecucion."""
    return {
        "expedientes": {
            "101": {"id": "101", "estudiante": "ana", "sede": "Central", "nota": 82},
            "202": {"id": "202", "estudiante": "luis", "sede": "Pacifico", "nota": 91},
        },
        "sesiones": {
            f"lab-{id_usuario}": {"usuario": id_usuario, "revocada": False, "expirada": False}
            for id_usuario in USUARIOS
        } | {"lab-vencida": {"usuario": "ana", "revocada": False, "expirada": True}},
        "auditoria": [],
    }


def autenticar(estado, token):
    """SEC-03: una sesion revocada o expirada NO autentica."""
    sesion = estado["sesiones"].get(token)
    if sesion is None or sesion["revocada"] or sesion["expirada"]:
        return None
    return USUARIOS.get(sesion["usuario"])


def _auditar(estado, accion, usuario, expediente_id, resultado):
    # Nunca se guarda el token: solo el id del usuario.
    estado["auditoria"].append(
        {"accion": accion, "usuario": usuario["id"], "id": expediente_id, "resultado": resultado}
    )


def _puede_leer(usuario, expediente):
    """SEC-01: estudiante solo lo propio, docente solo su sede, admin todo."""
    rol = usuario["rol"]
    if rol == "administrador":
        return True
    if rol == "docente":
        return expediente["sede"] == usuario["sede"]
    if rol == "estudiante":
        return expediente["estudiante"] == usuario["id"]
    return False


def _nota_valida(nota):
    """SEC-04: numero real en [0,100]; rechaza bool, NaN e infinito."""
    if isinstance(nota, bool) or not isinstance(nota, (int, float)):
        return False
    if isinstance(nota, float) and not math.isfinite(nota):
        return False
    return NOTA_MIN <= nota <= NOTA_MAX


def leer_expediente(estado, token, expediente_id):
    usuario = autenticar(estado, token)
    if usuario is None:
        return 401, {"error": "No autenticado"}
    expediente = estado["expedientes"].get(expediente_id)
    if expediente is None:
        return 404, {"error": "No existe"}
    if not _puede_leer(usuario, expediente):
        _auditar(estado, "lectura", usuario, expediente_id, "denegada")
        return 403, {"error": "Operación denegada"}  # sin datos confidenciales
    _auditar(estado, "lectura", usuario, expediente_id, "permitida")
    return 200, dict(expediente)


def actualizar_nota(estado, token, expediente_id, nota):
    usuario = autenticar(estado, token)
    if usuario is None:
        return 401, {"error": "No autenticado"}
    expediente = estado["expedientes"].get(expediente_id)
    if expediente is None:
        return 404, {"error": "No existe"}
    # Permisos primero (rol y SEC-02: sede), validacion de datos despues.
    if usuario["rol"] != "docente" or expediente["sede"] != usuario["sede"]:
        _auditar(estado, "actualizacion", usuario, expediente_id, "denegada")
        return 403, {"error": "Operación denegada"}
    if not _nota_valida(nota):
        _auditar(estado, "actualizacion", usuario, expediente_id, "rechazada")
        return 400, {"error": "Nota inválida"}
    expediente["nota"] = nota
    _auditar(estado, "actualizacion", usuario, expediente_id, "permitida")
    return 200, dict(expediente)


def revocar_sesion(estado, token):
    sesion = estado["sesiones"].get(token)
    if sesion is None or sesion["revocada"] or sesion["expirada"]:
        return 401, {"error": "No autenticado"}
    sesion["revocada"] = True
    return 200, {"mensaje": "Sesión revocada"}

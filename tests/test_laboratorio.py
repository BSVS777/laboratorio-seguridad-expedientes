"""Pruebas unitarias (logica de negocio) de seguridad de expedientes academicos.

Cada prueba lleva el identificador del caso de prueba (TC-xx) en su nombre y el
requisito (SEC-xx) en su docstring, para mantener la trazabilidad con
`matriz_trazabilidad.csv` y `casos_prueba.csv`.

Tipos: [P] positivo, [N] negativo, [F] frontera, [X] caso adicional.
"""
import copy
import unittest

from src.lab import estado_inicial, leer_expediente, actualizar_nota, revocar_sesion

CAMPOS_CONFIDENCIALES = ("nota", "estudiante", "sede")


class PruebaSeguridadBase(unittest.TestCase):
    def setUp(self):
        self.estado = estado_inicial()  # Estado independiente por prueba.
        self.expedientes_iniciales = copy.deepcopy(self.estado["expedientes"])

    def assertSinDatosProtegidos(self, datos, contexto=""):
        for campo in CAMPOS_CONFIDENCIALES:
            self.assertNotIn(campo, datos, f"{contexto}: la respuesta filtra '{campo}'")

    def assertExpedientesIntactos(self, contexto=""):
        self.assertEqual(
            self.expedientes_iniciales,
            self.estado["expedientes"],
            f"{contexto}: los expedientes cambiaron tras una operacion que debia fallar",
        )


class SeguridadExpedientes(PruebaSeguridadBase):
    # ---------- Positivos ----------
    def test_TC01_estudiante_lee_su_expediente(self):
        """[P] SEC-01: el estudiante A lee su propio expediente."""
        codigo, datos = leer_expediente(self.estado, "lab-ana", "101")
        self.assertEqual(200, codigo)
        self.assertEqual("ana", datos.get("estudiante"))
        self.assertEqual(82, datos.get("nota"))

    def test_TC06_docente_actualiza_nota_de_su_sede(self):
        """[P] SEC-02: el docente cambia la nota de un expediente de su sede."""
        codigo, datos = actualizar_nota(self.estado, "lab-maria", "101", 85)
        self.assertEqual(200, codigo)
        self.assertEqual(85, datos.get("nota"))
        self.assertEqual(85, self.estado["expedientes"]["101"]["nota"], "la nota debe persistir")

    def test_TC07_admin_lee_expedientes_de_ambas_sedes(self):
        """[P] SEC-01: el administrador lee expedientes de Central y Pacifico."""
        for expediente in ("101", "202"):
            codigo, _ = leer_expediente(self.estado, "lab-admin", expediente)
            self.assertEqual(200, codigo, f"admin deberia leer {expediente}")

    # ---------- Negativos ----------
    def test_TC02_estudiante_no_lee_expediente_ajeno(self):
        """[N] SEC-01/SEC-05: el estudiante A pide el expediente de B: 403 sin datos."""
        codigo, datos = leer_expediente(self.estado, "lab-ana", "202")
        self.assertEqual(403, codigo)
        self.assertSinDatosProtegidos(datos, "lectura ajena")
        self.assertExpedientesIntactos("lectura ajena")

    def test_TC03_docente_no_modifica_nota_de_otra_sede(self):
        """[N] SEC-02: Maria (Central) intenta cambiar el expediente de Pacifico."""
        codigo, datos = actualizar_nota(self.estado, "lab-maria", "202", 10)
        self.assertEqual(403, codigo)
        self.assertSinDatosProtegidos(datos, "escritura entre sedes")
        self.assertEqual(91, self.estado["expedientes"]["202"]["nota"], "la nota original debe quedar intacta")
        self.assertExpedientesIntactos("escritura entre sedes")

    def test_TC04a_sesion_revocada_no_accede(self):
        """[N] SEC-03: tras revocar la sesion, ni lectura ni escritura."""
        codigo, _ = revocar_sesion(self.estado, "lab-ana")
        self.assertEqual(200, codigo, "la revocacion de una sesion vigente debe funcionar")
        codigo, datos = leer_expediente(self.estado, "lab-ana", "101")
        self.assertEqual(401, codigo)
        self.assertSinDatosProtegidos(datos, "lectura con sesion revocada")

    def test_TC04b_sesion_vencida_no_lee_ni_modifica(self):
        """[N] SEC-03: la sesion marcada como vencida no lee ni modifica."""
        codigo, datos = leer_expediente(self.estado, "lab-vencida", "101")
        self.assertEqual(401, codigo)
        self.assertSinDatosProtegidos(datos, "lectura con sesion vencida")
        codigo, _ = actualizar_nota(self.estado, "lab-vencida", "101", 50)
        self.assertEqual(401, codigo)
        self.assertExpedientesIntactos("escritura con sesion vencida")

    def test_TC04c_bandera_expirada_prevalece_aunque_el_reloj_no_haya_vencido(self):
        """[N] SEC-03: una sesion marcada como expirada se rechaza aunque expira_en sea futuro.

        Hallazgo de la prueba de mutacion (M-07): sin este caso, la bandera 'expirada' quedaba
        tapada por la comprobacion de reloj y ninguna prueba detectaria que se eliminara.
        """
        self.estado["sesiones"]["lab-ana"]["expirada"] = True
        self.assertGreater(self.estado["sesiones"]["lab-ana"]["expira_en"], self.estado["ahora"]())
        codigo, datos = leer_expediente(self.estado, "lab-ana", "101")
        self.assertEqual(401, codigo)
        self.assertSinDatosProtegidos(datos, "sesion marcada como expirada")

    def test_TC08_admin_no_modifica_notas(self):
        """[N] SEC-02: escalada vertical, el administrador no puede cambiar notas."""
        codigo, _ = actualizar_nota(self.estado, "lab-admin", "101", 100)
        self.assertEqual(403, codigo)
        self.assertExpedientesIntactos("admin escribe")

    def test_TC09_estudiante_no_modifica_su_propia_nota(self):
        """[N] SEC-02: escalada vertical, el estudiante no puede cambiar notas."""
        codigo, _ = actualizar_nota(self.estado, "lab-ana", "101", 100)
        self.assertEqual(403, codigo)
        self.assertExpedientesIntactos("estudiante escribe")

    def test_TC10_docente_no_lee_expediente_de_otra_sede(self):
        """[N] SEC-01: Maria (Central) intenta leer el expediente de Pacifico."""
        codigo, datos = leer_expediente(self.estado, "lab-maria", "202")
        self.assertEqual(403, codigo)
        self.assertSinDatosProtegidos(datos, "lectura entre sedes")

    # ---------- Frontera ----------
    def test_TC05_nota_fuera_de_rango_se_rechaza_y_no_persiste(self):
        """[F] SEC-04: valores justo fuera de [0,100] dan 400 y no se guardan."""
        for nota in (-1, -0.01, 100.01, 101, 1000):
            codigo, _ = actualizar_nota(self.estado, "lab-maria", "101", nota)
            self.assertEqual(400, codigo, f"la nota {nota} deberia rechazarse")
        self.assertExpedientesIntactos("notas fuera de rango")

    def test_TC11_limites_0_y_100_son_validos(self):
        """[F] SEC-04: los limites inclusivos 0 y 100 se aceptan y persisten."""
        for nota in (0, 100):
            codigo, datos = actualizar_nota(self.estado, "lab-maria", "101", nota)
            self.assertEqual(200, codigo, f"la nota {nota} deberia aceptarse")
            self.assertEqual(nota, self.estado["expedientes"]["101"]["nota"])

    def test_TC12_expediente_inexistente_no_permite_enumerar_ids(self):
        """[F] SEC-05: para quien no es administrador, un ID inexistente es
        indistinguible de un expediente ajeno (misma respuesta 403, sin datos).
        Solo el administrador puede saber que un ID no existe (404)."""
        codigo_admin, datos_admin = leer_expediente(self.estado, "lab-admin", "999")
        self.assertEqual(404, codigo_admin)
        self.assertSinDatosProtegidos(datos_admin, "expediente inexistente (admin)")
        for token in ("lab-ana", "lab-maria"):
            ajeno = leer_expediente(self.estado, token, "202")  # existe, pero no es suyo
            inexistente = leer_expediente(self.estado, token, "999")
            self.assertEqual(ajeno, inexistente, f"{token}: 404 vs 403 permite enumerar expedientes")

    # ---------- Casos adicionales (no cuentan para el minimo de 12) ----------
    def test_TC13_token_ausente_o_desconocido_da_401(self):
        """[N] SEC-03: sin sesion o con token desconocido no se accede a nada."""
        for token in ("", "lab-inexistente"):
            codigo, datos = leer_expediente(self.estado, token, "101")
            self.assertEqual(401, codigo, f"token {token!r}")
            self.assertSinDatosProtegidos(datos, f"token {token!r}")

    def test_TC14_tipos_invalidos_de_nota_se_rechazan(self):
        """[N] SEC-04: texto, null, booleano, NaN, infinito y lista no son notas."""
        for invalido in ("85", None, True, float("nan"), float("inf"), [85]):
            codigo, _ = actualizar_nota(self.estado, "lab-maria", "101", invalido)
            self.assertEqual(400, codigo, f"valor {invalido!r}")
        self.assertExpedientesIntactos("tipos invalidos")

    def test_TC15_auditoria_registra_denegados_y_nunca_tokens(self):
        """[X] SEC-06: la bitacora guarda usuario/accion/resultado, jamas el token."""
        leer_expediente(self.estado, "lab-ana", "101")
        actualizar_nota(self.estado, "lab-maria", "101", 90)
        leer_expediente(self.estado, "lab-ana", "202")  # denegado: tambien se audita
        resultados = [registro["resultado"] for registro in self.estado["auditoria"]]
        self.assertEqual(["permitida", "permitida", "denegada"], resultados)
        for registro in self.estado["auditoria"]:
            self.assertNotIn("token", registro)
            self.assertFalse(any("lab-" in str(v) for v in registro.values()), f"token filtrado: {registro}")

    def test_TC20_escritura_sobre_id_inexistente_no_permite_enumerar(self):
        """[N] SEC-05: quien no puede modificar recibe 403 tambien si el ID no existe."""
        for token in ("lab-ana", "lab-maria", "lab-admin"):
            ajeno = actualizar_nota(self.estado, token, "202", 50)
            inexistente = actualizar_nota(self.estado, token, "999", 50)
            self.assertEqual(ajeno, inexistente, f"{token}: 404 vs 403 permite enumerar expedientes")
        self.assertExpedientesIntactos("escritura sobre ids inexistentes")

    def test_TC16_permiso_se_evalua_antes_que_validacion_del_dato(self):
        """[N] SEC-05: un estudiante con dato invalido recibe 403, no 400."""
        codigo, _ = actualizar_nota(self.estado, "lab-ana", "101", 5000)
        self.assertEqual(403, codigo, "un 400 revelaria reglas internas a quien no tiene permiso")


class VigenciaDeSesion(PruebaSeguridadBase):
    """SEC-03: la sesion caduca por reloj, no solo por una bandera manual."""

    INSTANTE_EXPIRACION = 1000.0

    def preparar_sesion(self, token, ahora):
        self.estado["sesiones"][token]["expira_en"] = self.INSTANTE_EXPIRACION
        self.estado["ahora"] = lambda: ahora

    def test_TC19a_sesion_con_expiracion_pasada_no_lee_ni_modifica(self):
        """[N] SEC-03: expira_en vencido (sin bandera 'expirada') da 401."""
        self.preparar_sesion("lab-maria", ahora=self.INSTANTE_EXPIRACION + 500)
        codigo, datos = leer_expediente(self.estado, "lab-maria", "101")
        self.assertEqual(401, codigo, "una sesion vencida por reloj no debe leer")
        self.assertSinDatosProtegidos(datos, "lectura con sesion vencida por reloj")
        codigo, _ = actualizar_nota(self.estado, "lab-maria", "101", 50)
        self.assertEqual(401, codigo, "una sesion vencida por reloj no debe modificar")
        self.assertExpedientesIntactos("escritura con sesion vencida por reloj")

    def test_TC19b_frontera_de_expiracion(self):
        """[F] SEC-03: un instante antes de expirar es valida; en el instante exacto ya no."""
        self.preparar_sesion("lab-ana", ahora=self.INSTANTE_EXPIRACION - 0.001)
        self.assertEqual(200, leer_expediente(self.estado, "lab-ana", "101")[0])
        self.preparar_sesion("lab-ana", ahora=self.INSTANTE_EXPIRACION)
        self.assertEqual(401, leer_expediente(self.estado, "lab-ana", "101")[0])

    def test_TC19c_sesion_vencida_por_reloj_no_se_puede_revocar_como_vigente(self):
        """[N] SEC-03: revocar una sesion ya vencida responde 401, igual que autenticar."""
        self.preparar_sesion("lab-ana", ahora=self.INSTANTE_EXPIRACION + 1)
        self.assertEqual(401, revocar_sesion(self.estado, "lab-ana")[0])

    def test_TC19d_sesiones_nuevas_tienen_vigencia_finita(self):
        """[X] SEC-03: toda sesion vigente del estado inicial tiene un instante de expiracion."""
        for token, sesion in self.estado["sesiones"].items():
            self.assertIsNotNone(sesion.get("expira_en"), f"{token} no tiene 'expira_en'")


if __name__ == "__main__":
    unittest.main()

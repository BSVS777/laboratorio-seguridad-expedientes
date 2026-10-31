"""Suite de seguridad de expedientes academicos (12 casos de diseno + extras).

Tipos: [P] positivo, [N] negativo, [F] frontera.
Ciclo TDD 1: SEC-01 (autorizacion horizontal/vertical en lectura) y SEC-03 (sesiones).
Ciclo TDD 2: SEC-02 (sede del docente) y SEC-04 (rango de la nota).
"""
import unittest
from src.lab import estado_inicial, leer_expediente, actualizar_nota, revocar_sesion


class SeguridadExpedientes(unittest.TestCase):
    def setUp(self):
        self.estado = estado_inicial()  # Un estado independiente por prueba.

    # ---------- Positivos ----------
    def test_P01_estudiante_consulta_expediente_propio(self):
        codigo, datos = leer_expediente(self.estado, "lab-ana", "101")
        self.assertEqual(200, codigo)
        self.assertEqual("ana", datos.get("estudiante"))

    def test_P02_docente_actualiza_nota_en_su_sede(self):
        codigo, datos = actualizar_nota(self.estado, "lab-maria", "101", 85)
        self.assertEqual(200, codigo)
        self.assertEqual(85, datos.get("nota"))

    def test_P03_admin_lee_expedientes_de_todas_las_sedes(self):
        for exp in ("101", "202"):
            codigo, _ = leer_expediente(self.estado, "lab-admin", exp)
            self.assertEqual(200, codigo)

    # ---------- Negativos ----------
    def test_N01_estudiante_no_consulta_expediente_ajeno(self):  # SEC-01
        codigo, datos = leer_expediente(self.estado, "lab-ana", "202")
        self.assertEqual(403, codigo)
        self.assertNotIn("nota", datos)
        self.assertNotIn("estudiante", datos)

    def test_N02_sesion_revocada_no_permite_lecturas(self):  # SEC-03
        codigo, _ = revocar_sesion(self.estado, "lab-ana")
        self.assertEqual(200, codigo)
        codigo, datos = leer_expediente(self.estado, "lab-ana", "101")
        self.assertEqual(401, codigo)
        self.assertNotIn("nota", datos)

    def test_N03_sesion_expirada_no_lee_ni_modifica(self):  # SEC-03
        codigo, datos = leer_expediente(self.estado, "lab-vencida", "101")
        self.assertEqual(401, codigo)
        self.assertNotIn("nota", datos)
        codigo, _ = actualizar_nota(self.estado, "lab-vencida", "101", 50)
        self.assertEqual(401, codigo)
        self.assertEqual(82, self.estado["expedientes"]["101"]["nota"])

    def test_N04_docente_no_modifica_nota_de_otra_sede(self):  # SEC-02
        codigo, datos = actualizar_nota(self.estado, "lab-maria", "202", 10)
        self.assertEqual(403, codigo)
        self.assertNotIn("nota", datos)
        self.assertEqual(91, self.estado["expedientes"]["202"]["nota"])

    def test_N05_estudiante_y_admin_no_modifican_notas(self):  # escalada vertical
        for token in ("lab-ana", "lab-admin"):
            codigo, _ = actualizar_nota(self.estado, token, "101", 100)
            self.assertEqual(403, codigo)
        self.assertEqual(82, self.estado["expedientes"]["101"]["nota"])

    def test_N06_docente_no_lee_expediente_de_otra_sede(self):  # SEC-01
        codigo, datos = leer_expediente(self.estado, "lab-maria", "202")
        self.assertEqual(403, codigo)
        self.assertNotIn("nota", datos)

    def test_N07_token_ausente_o_desconocido(self):
        for token in ("", "lab-inexistente"):
            codigo, datos = leer_expediente(self.estado, token, "101")
            self.assertEqual(401, codigo)
            self.assertNotIn("nota", datos)

    def test_N08_tipos_invalidos_de_nota_se_rechazan(self):  # SEC-04
        for invalido in ("85", None, True, float("nan"), float("inf"), [85]):
            codigo, _ = actualizar_nota(self.estado, "lab-maria", "101", invalido)
            self.assertEqual(400, codigo, f"valor {invalido!r}")
        self.assertEqual(82, self.estado["expedientes"]["101"]["nota"])

    # ---------- Frontera ----------
    def test_F01_limites_0_y_100_son_validos(self):  # SEC-04
        for nota in (0, 100):
            codigo, datos = actualizar_nota(self.estado, "lab-maria", "101", nota)
            self.assertEqual(200, codigo)
            self.assertEqual(nota, datos["nota"])

    def test_F02_fuera_de_rango_se_rechaza_y_conserva_nota(self):  # SEC-04
        for nota in (-1, -0.01, 100.01, 101, 1000):
            codigo, _ = actualizar_nota(self.estado, "lab-maria", "101", nota)
            self.assertEqual(400, codigo, f"nota {nota}")
        self.assertEqual(82, self.estado["expedientes"]["101"]["nota"])

    def test_F03_expediente_inexistente_da_404_sin_datos(self):
        codigo, datos = leer_expediente(self.estado, "lab-ana", "999")
        self.assertEqual(404, codigo)
        self.assertNotIn("nota", datos)

    # ---------- Extras: auditoria y orden de controles ----------
    def test_X01_auditoria_no_contiene_tokens(self):
        leer_expediente(self.estado, "lab-ana", "101")
        actualizar_nota(self.estado, "lab-maria", "101", 90)
        leer_expediente(self.estado, "lab-ana", "202")  # denegado tambien se audita
        self.assertGreaterEqual(len(self.estado["auditoria"]), 3)
        for registro in self.estado["auditoria"]:
            self.assertNotIn("token", registro)
            self.assertFalse(any("lab-" in str(v) for v in registro.values()))

    def test_X02_permiso_se_evalua_antes_que_validacion_de_dato(self):
        # Un estudiante con dato invalido recibe 403, no 400 (no revela reglas internas).
        codigo, _ = actualizar_nota(self.estado, "lab-ana", "101", 5000)
        self.assertEqual(403, codigo)


if __name__ == "__main__":
    unittest.main()

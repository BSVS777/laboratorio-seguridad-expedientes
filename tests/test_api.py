"""Pruebas de integracion: interaccion real con la API HTTP (servidor.py).

El servidor se levanta en 127.0.0.1 con puerto efimero y estado sintetico nuevo
para cada prueba. Los identificadores TC-xx coinciden con `casos_prueba.csv`.
"""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

import servidor
from src.lab import estado_inicial


class PruebaApi(unittest.TestCase):
    def setUp(self):
        servidor.ServidorLaboratorio.estado = estado_inicial()
        silencio = mock.patch.object(servidor.ServidorLaboratorio, "log_message", lambda *a, **k: None)
        silencio.start()
        self.addCleanup(silencio.stop)
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), servidor.ServidorLaboratorio)
        self.puerto = self.servidor.server_address[1]
        hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(hilo.join, 5)
        self.addCleanup(self.servidor.server_close)
        self.addCleanup(self.servidor.shutdown)

    def llamar(self, metodo, ruta, token=None, cuerpo=None, encabezados=None):
        """Devuelve (codigo, texto_crudo, json_o_None)."""
        conexion = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        try:
            conexion.putrequest(metodo, ruta)
            if token:
                conexion.putheader("Authorization", f"Bearer {token}")
            datos = None
            if cuerpo is not None:
                datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode("utf-8")
                conexion.putheader("Content-Type", "application/json")
                conexion.putheader("Content-Length", str(len(datos)))
            for clave, valor in (encabezados or {}).items():
                conexion.putheader(clave, valor)
            conexion.endheaders(datos)
            respuesta = conexion.getresponse()
            texto = respuesta.read().decode("utf-8")
            try:
                parseado = json.loads(texto)
            except ValueError:
                parseado = None
            return respuesta.status, texto, parseado
        finally:
            conexion.close()

    def nota_de(self, expediente):
        """Lee la nota persistida usando al administrador (efecto sobre los datos)."""
        _, _, datos = self.llamar("GET", f"/expedientes/{expediente}", "lab-admin")
        return datos["nota"]


class SeguridadApi(PruebaApi):
    def test_api_TC01_estudiante_lee_su_expediente(self):
        codigo, _, datos = self.llamar("GET", "/expedientes/101", "lab-ana")
        self.assertEqual(200, codigo)
        self.assertEqual("ana", datos["estudiante"])

    def test_api_TC02_estudiante_no_lee_expediente_ajeno_y_no_filtra(self):
        codigo, texto, _ = self.llamar("GET", "/expedientes/202", "lab-ana")
        self.assertEqual(403, codigo)
        for secreto in ("nota", "91", "luis", "Pacifico"):
            self.assertNotIn(secreto, texto, f"el cuerpo 403 filtra '{secreto}'")

    def test_api_TC03_docente_no_modifica_otra_sede(self):
        codigo, _, _ = self.llamar("POST", "/expedientes/202/nota", "lab-maria", '{"nota": 10}')
        self.assertEqual(403, codigo)
        self.assertEqual(91, self.nota_de("202"), "la nota original debe conservarse")

    def test_api_TC04_sesiones_revocada_y_vencida_reciben_401(self):
        codigo, _, _ = self.llamar("POST", "/sesiones/revocar", "lab-ana")
        self.assertEqual(200, codigo)
        codigo, texto, _ = self.llamar("GET", "/expedientes/101", "lab-ana")
        self.assertEqual(401, codigo)
        self.assertNotIn("nota", texto)
        codigo, texto, _ = self.llamar("GET", "/expedientes/101", "lab-vencida")
        self.assertEqual(401, codigo)
        self.assertNotIn("nota", texto)

    def test_api_TC05_nota_fuera_de_rango_da_400_y_no_persiste(self):
        for nota in ("-1", "101", "1000"):
            codigo, _, _ = self.llamar("POST", "/expedientes/101/nota", "lab-maria", f'{{"nota": {nota}}}')
            self.assertEqual(400, codigo, f"nota {nota}")
        self.assertEqual(82, self.nota_de("101"))

    def test_api_TC06_docente_actualiza_nota_de_su_sede(self):
        codigo, _, _ = self.llamar("POST", "/expedientes/101/nota", "lab-maria", '{"nota": 85}')
        self.assertEqual(200, codigo)
        self.assertEqual(85, self.nota_de("101"))

    def test_api_TC17_json_invalido_o_no_objeto_da_400(self):
        for cuerpo in ("{nota:", "[85]", ""):
            codigo, _, _ = self.llamar("POST", "/expedientes/101/nota", "lab-maria", cuerpo)
            self.assertEqual(400, codigo, f"cuerpo {cuerpo!r}")
        self.assertEqual(82, self.nota_de("101"))

    def test_api_TC18_content_length_negativo_da_400_y_exceso_da_413(self):
        codigo, _, _ = self.llamar(
            "POST", "/expedientes/101/nota", "lab-maria", encabezados={"Content-Length": "-1"}
        )
        self.assertEqual(400, codigo, "un Content-Length negativo no debe dejar la peticion colgada")
        codigo, _, _ = self.llamar(
            "POST", "/expedientes/101/nota", "lab-maria", encabezados={"Content-Length": "2048"}
        )
        self.assertEqual(413, codigo)

    def test_api_TC21_respuestas_no_se_almacenan_en_cache(self):
        conexion = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        try:
            conexion.request("GET", "/expedientes/101", headers={"Authorization": "Bearer lab-ana"})
            respuesta = conexion.getresponse()
            respuesta.read()
            self.assertEqual("no-store", respuesta.getheader("Cache-Control"))
        finally:
            conexion.close()


if __name__ == "__main__":
    unittest.main()

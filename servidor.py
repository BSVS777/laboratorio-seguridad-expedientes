"""API de laboratorio; escucha SOLO en 127.0.0.1. No desplegar públicamente."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from src.lab import estado_inicial, leer_expediente, actualizar_nota, revocar_sesion


class ServidorLaboratorio(BaseHTTPRequestHandler):
    estado = estado_inicial()

    def _token(self):
        encabezado = self.headers.get("Authorization", "")
        return encabezado[7:] if encabezado.startswith("Bearer ") else ""

    def _salida(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = urlsplit(self.path).path
        if ruta == "/health":
            return self._salida(200, {"estado": "laboratorio"})
        if ruta.startswith("/expedientes/"):
            codigo, resultado = leer_expediente(self.estado, self._token(), ruta.split("/")[-1])
            return self._salida(codigo, resultado)
        return self._salida(404, {"error": "Ruta inexistente"})

    def do_POST(self):
        ruta = urlsplit(self.path).path
        if ruta == "/sesiones/revocar":
            codigo, resultado = revocar_sesion(self.estado, self._token())
            return self._salida(codigo, resultado)
        if ruta.startswith("/expedientes/") and ruta.endswith("/nota"):
            try:
                cantidad = int(self.headers.get("Content-Length", "0"))
                if cantidad < 0:
                    return self._salida(400, {"error": "Content-Length inválido"})
                if cantidad > 1024:
                    return self._salida(413, {"error": "Solicitud demasiado grande"})
                datos = json.loads(self.rfile.read(cantidad).decode("utf-8"))
                if not isinstance(datos, dict):
                    return self._salida(400, {"error": "Objeto JSON esperado"})
                nota = datos.get("nota")
            except (ValueError, UnicodeError):
                return self._salida(400, {"error": "JSON inválido"})
            codigo, resultado = actualizar_nota(self.estado, self._token(), ruta.split("/")[2], nota)
            return self._salida(codigo, resultado)
        return self._salida(404, {"error": "Ruta inexistente"})

    def log_message(self, fmt, *args):
        # Log sin encabezados de autorización.
        print("[LAB] " + fmt % args)


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("127.0.0.1", 8765), ServidorLaboratorio)
    print("Laboratorio: http://127.0.0.1:8765 (CTRL+C para finalizar)")
    servidor.serve_forever()

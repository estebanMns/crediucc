"""Login con Supabase Auth: adaptador HTTP, proveedor deshabilitado y endpoints de la API."""
import io
import urllib.error
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion_web import crear_app
from app.aplicacion.identidad import (
    CredencialesInvalidasError,
    IdentidadNoDisponibleError,
    PerfilRegistro,
    RegistroInvalidoError,
    Usuario,
)
from app.config import Configuracion
from app.contenedor import construir_identidad, construir_servicio
from app.infraestructura import identidad as modulo_identidad
from app.infraestructura.identidad import (
    ProveedorDeshabilitado,
    ProveedorSupabase,
    enviar_http,
    traducir_error,
)

URL = "https://demo.supabase.co"
CLAVE_PRUEBA = "Clave-Segura-123"  # dato de prueba, no es una credencial real
PERFIL = PerfilRegistro("Ana Pérez", 20, 5)
USUARIO_ANA = {"id": "11111111-1111-1111-1111-111111111111", "email": "ana@example.com",
               "user_metadata": {"nombre_completo": "Ana Pérez", "edad": 20, "semestre": 5}}
USUARIO_ANA_DOMINIO = Usuario("11111111-1111-1111-1111-111111111111", "ana@example.com", "Ana Pérez", 20, 5)
SESION_ANA = {"access_token": "token-ana", "expires_in": 3600, "user": USUARIO_ANA}


class HttpFalso:
    """Doble de enviar_http: responde según la ruta y registra cada llamada."""

    def __init__(self, respuestas: dict[str, tuple[int, dict]]) -> None:
        self._respuestas = respuestas
        self.llamadas: list[tuple[str, str, dict, dict | None]] = []

    def __call__(self, metodo, url, cabeceras, cuerpo):
        self.llamadas.append((metodo, url, dict(cabeceras), cuerpo))
        ruta = url.removeprefix(URL)
        return self._respuestas[ruta]


def proveedor(respuestas: dict[str, tuple[int, dict]]) -> tuple[ProveedorSupabase, HttpFalso]:
    http = HttpFalso(respuestas)
    return ProveedorSupabase(URL + "/", "llave-publica", enviar=http), http


# ------------------------------------------------------------ ProveedorSupabase
def test_registro_sin_confirmacion_entrega_sesion():
    supabase, http = proveedor({"/auth/v1/signup": (200, SESION_ANA)})

    resultado = supabase.registrar("ana@example.com", CLAVE_PRUEBA, PERFIL)

    assert resultado.requiere_confirmacion is False
    assert resultado.sesion.token_acceso == "token-ana"
    metodo, url, cabeceras, cuerpo = http.llamadas[0]
    assert (metodo, url) == ("POST", f"{URL}/auth/v1/signup")
    assert cabeceras["apikey"] == "llave-publica"
    assert cuerpo == {"email": "ana@example.com", "password": CLAVE_PRUEBA,
                      "data": {"nombre_completo": "Ana Pérez", "edad": 20, "semestre": 5}}


def test_registro_con_confirmacion_de_correo_no_entrega_sesion():
    supabase, _ = proveedor({"/auth/v1/signup": (200, USUARIO_ANA)})

    resultado = supabase.registrar("ana@example.com", CLAVE_PRUEBA, PERFIL)

    assert resultado.requiere_confirmacion is True
    assert resultado.usuario == USUARIO_ANA_DOMINIO


@pytest.mark.parametrize("codigo_error, mensaje", [
    ("user_already_exists", "Ya existe una cuenta"),
    ("weak_password", "muy débil"),
    ("otro_error", "No pudimos crear la cuenta"),
])
def test_registro_traduce_errores_de_supabase(codigo_error, mensaje):
    supabase, _ = proveedor({"/auth/v1/signup": (422, {"error_code": codigo_error})})
    with pytest.raises(RegistroInvalidoError, match=mensaje):
        supabase.registrar("ana@example.com", CLAVE_PRUEBA, PERFIL)


def test_ingreso_correcto_y_credenciales_invalidas():
    ruta = "/auth/v1/token?grant_type=password"
    supabase, _ = proveedor({ruta: (200, SESION_ANA)})
    assert supabase.ingresar("ana@example.com", CLAVE_PRUEBA).usuario.email == "ana@example.com"

    supabase, _ = proveedor({ruta: (400, {"error_code": "invalid_credentials"})})
    with pytest.raises(CredencialesInvalidasError, match="incorrectos"):
        supabase.ingresar("ana@example.com", CLAVE_PRUEBA)


def test_respuesta_inesperada_del_servicio():
    supabase, _ = proveedor({"/auth/v1/token?grant_type=password": (200, {"access_token": "x"})})
    with pytest.raises(IdentidadNoDisponibleError):
        supabase.ingresar("ana@example.com", CLAVE_PRUEBA)


@pytest.mark.parametrize("codigo, esperado", [(200, USUARIO_ANA_DOMINIO), (401, None)])
def test_usuario_de_token(codigo, esperado):
    supabase, http = proveedor({"/auth/v1/user": (codigo, USUARIO_ANA if codigo == 200 else {})})
    assert supabase.usuario_de_token("token-ana") == esperado
    assert http.llamadas[0][2]["Authorization"] == "Bearer token-ana"


def test_supabase_exige_https():
    with pytest.raises(ValueError, match="https"):
        ProveedorSupabase("http://demo.supabase.co", "llave")


def test_traducir_error_usa_code_si_falta_error_code():
    assert "confirmar tu correo" in traducir_error({"code": "email_not_confirmed"}, "x")
    assert traducir_error({}, "por defecto") == "por defecto"


# ------------------------------------------------------------------ enviar_http
class RespuestaUrllib(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_enviar_http_exito_error_http_y_sin_red(monkeypatch):
    monkeypatch.setattr(modulo_identidad.urllib.request, "urlopen",
                        lambda peticion, timeout: RespuestaUrllib(b'{"ok": true}'))
    assert enviar_http("POST", URL, {}, {"a": 1}) == (200, {"ok": True})

    def error_http(peticion, timeout):
        raise urllib.error.HTTPError(URL, 400, "Bad", {}, io.BytesIO(b"no-es-json"))

    monkeypatch.setattr(modulo_identidad.urllib.request, "urlopen", error_http)
    assert enviar_http("GET", URL, {}, None) == (400, {})

    def sin_red(peticion, timeout):
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(modulo_identidad.urllib.request, "urlopen", sin_red)
    with pytest.raises(IdentidadNoDisponibleError):
        enviar_http("GET", URL, {}, None)


def test_enviar_http_ignora_json_que_no_es_objeto(monkeypatch):
    monkeypatch.setattr(modulo_identidad.urllib.request, "urlopen",
                        lambda peticion, timeout: RespuestaUrllib(b"[1, 2]"))
    assert enviar_http("GET", URL, {}, None) == (200, {})


# ------------------------------------------------------ proveedor deshabilitado
def test_proveedor_deshabilitado():
    deshabilitado = ProveedorDeshabilitado()
    assert deshabilitado.habilitado is False
    assert deshabilitado.usuario_de_token("cualquiera") is None
    with pytest.raises(IdentidadNoDisponibleError):
        deshabilitado.registrar("a@b.co", CLAVE_PRUEBA, PERFIL)
    with pytest.raises(IdentidadNoDisponibleError):
        deshabilitado.ingresar("a@b.co", CLAVE_PRUEBA)


def test_construir_identidad_segun_configuracion():
    assert isinstance(construir_identidad(Configuracion()), ProveedorDeshabilitado)
    config = Configuracion(supabase_url=URL, supabase_llave_publica="llave")
    assert config.login_habilitado is True
    assert isinstance(construir_identidad(config), ProveedorSupabase)


# --------------------------------------------------------- API con login activo
class IdentidadFalsa:
    """Dos usuarios con token fijo; permite probar el aislamiento entre usuarios."""

    habilitado = True
    TOKENS: ClassVar[dict[str, Usuario]] = {"token-ana": Usuario("u-ana", "ana@example.com"),
                                            "token-luis": Usuario("u-luis", "luis@example.com")}

    def __init__(self, requiere_confirmacion: bool = False) -> None:
        self._requiere_confirmacion = requiere_confirmacion
        self.sesiones_cerradas: list[str] = []

    def registrar(self, email, password, perfil):
        if email == "existe@example.com":
            raise RegistroInvalidoError("Ya existe una cuenta con ese correo.")
        sesion = None if self._requiere_confirmacion else self._sesion(email, perfil.nombre_completo)
        return modulo_identidad.ResultadoRegistro(Usuario("u-nuevo", email, perfil.nombre_completo), sesion)

    def ingresar(self, email, password):
        if password != CLAVE_PRUEBA:
            raise CredencialesInvalidasError("Correo o contraseña incorrectos.")
        return self._sesion(email)

    def usuario_de_token(self, token):
        return self.TOKENS.get(token)

    def cerrar_sesion(self, token):
        self.sesiones_cerradas.append(token)

    @staticmethod
    def _sesion(email, nombre=""):
        return modulo_identidad.Sesion("token-ana", 3600, Usuario("u-ana", email, nombre))


SOLICITUD = {"nombre": "Ana", "email": "ana@example.com", "edad": 22, "score": 720,
             "ingresos": 3_000_000.0, "monto": 1_500_000.0, "es_estudiante": True}


class MonitorSano:
    def esta_sano(self) -> bool:
        return True


def cliente_con_login(identidad=None) -> TestClient:
    identidad = identidad or IdentidadFalsa()
    return TestClient(crear_app(construir_servicio(Configuracion()), MonitorSano(), "1.0.0", identidad))


def como(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health_informa_que_el_login_esta_activo():
    assert cliente_con_login().get("/health").json()["login"] is True


@pytest.mark.parametrize("cabeceras", [{}, como("token-falso"), {"Authorization": "Basic abc"}])
def test_solicitudes_exigen_sesion_valida(cabeceras):
    respuesta = cliente_con_login().get("/api/v1/solicitudes", headers=cabeceras)
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_cada_usuario_ve_solo_sus_solicitudes():
    cliente = cliente_con_login()
    de_ana = cliente.post("/api/v1/solicitudes", json=SOLICITUD, headers=como("token-ana")).json()

    propias = cliente.get("/api/v1/solicitudes", headers=como("token-ana")).json()
    assert [s["id"] for s in propias] == [de_ana["id"]]
    assert cliente.get("/api/v1/solicitudes", headers=como("token-luis")).json() == []
    assert cliente.get(f"/api/v1/solicitudes/{de_ana['id']}", headers=como("token-luis")).status_code == 404
    assert cliente.get(f"/api/v1/solicitudes/{de_ana['id']}", headers=como("token-ana")).status_code == 200


REGISTRO = {"email": " Nuevo@Example.com ", "password": CLAVE_PRUEBA,
            "nombre_completo": "  ana   maría pérez ", "edad": 20, "semestre": 5}


def test_registro_con_y_sin_confirmacion_de_correo():
    credenciales = REGISTRO

    directa = cliente_con_login().post("/api/v1/auth/registro", json=credenciales)
    assert directa.status_code == 201
    assert directa.json()["sesion"]["usuario"]["email"] == "nuevo@example.com"

    con_correo = cliente_con_login(IdentidadFalsa(requiere_confirmacion=True)).post(
        "/api/v1/auth/registro", json=credenciales)
    assert con_correo.json()["requiere_confirmacion"] is True
    assert con_correo.json()["sesion"] is None


def test_registro_normaliza_nombre_y_correo():
    respuesta = cliente_con_login().post("/api/v1/auth/registro", json=REGISTRO)
    assert respuesta.json()["sesion"]["usuario"]["nombre_completo"] == "Ana María Pérez"


def test_registro_de_correo_existente():
    datos = {**REGISTRO, "email": "existe@example.com"}
    assert cliente_con_login().post("/api/v1/auth/registro", json=datos).status_code == 400


@pytest.mark.parametrize("cambios, mensaje", [
    ({"password": "corta1"}, "entre 8 y 72"),
    ({"password": "solo-letras"}, "letras y números"),
    ({"password": "12345678"}, "letras y números"),
    ({"password": "con espacio 123"}, "sin espacios"),
    ({"nombre_completo": "Ana"}, "nombre y apellido"),
    ({"nombre_completo": "Ana P3rez"}, "solo con letras"),
    ({"nombre_completo": "Ana --"}, "solo con letras"),
    ({"edad": 15}, "entre 16 y 100"),
    ({"edad": 101}, "entre 16 y 100"),
    ({"semestre": 0}, "entre 1 y 12"),
    ({"semestre": 13}, "entre 1 y 12"),
    ({"email": "sin-arroba.com"}, "correo válido"),
    ({"email": "ana@dominio"}, "correo válido"),
])
def test_registro_rechaza_datos_invalidos_con_mensaje_claro(cambios, mensaje):
    respuesta = cliente_con_login().post("/api/v1/auth/registro", json={**REGISTRO, **cambios})
    assert respuesta.status_code == 422
    texto = respuesta.json()["detail"][0]["msg"]
    assert mensaje in texto
    assert not texto.startswith("Value error")


def test_ingreso_y_consulta_del_usuario_actual():
    cliente = cliente_con_login()
    sesion = cliente.post("/api/v1/auth/ingreso", json={"email": "ana@example.com", "password": CLAVE_PRUEBA})
    assert sesion.status_code == 200
    assert "token" not in sesion.text  # el JWT nunca va en el cuerpo: solo en la cookie HttpOnly
    yo = cliente.get("/api/v1/auth/yo").json()  # TestClient reenvía la cookie, como el navegador
    assert (yo["id"], yo["email"]) == ("u-ana", "ana@example.com")

    incorrecta = {"email": "ana@example.com", "password": "otra-clave-1"}
    assert cliente.post("/api/v1/auth/ingreso", json=incorrecta).status_code == 401


def test_sin_login_configurado_los_endpoints_de_auth_responden_503():
    cliente = TestClient(crear_app(construir_servicio(Configuracion()), MonitorSano()))
    credenciales = {"email": "ana@example.com", "password": CLAVE_PRUEBA}

    assert cliente.post("/api/v1/auth/ingreso", json=credenciales).status_code == 503
    assert cliente.post("/api/v1/auth/registro", json=REGISTRO).status_code == 503
    assert cliente.get("/api/v1/auth/yo").status_code == 401
    assert cliente.get("/api/v1/solicitudes").status_code == 200  # sin login: modo anónimo


def test_ingreso_valida_formato_del_correo_y_clave_vacia():
    cliente = cliente_con_login()
    invalidas = ({"email": "malo", "password": CLAVE_PRUEBA}, {"email": "ana@example.com", "password": ""})
    for credenciales in invalidas:
        assert cliente.post("/api/v1/auth/ingreso", json=credenciales).status_code == 422


def test_usuario_sin_metadatos_de_perfil():
    datos = {"id": "u1", "email": "x@y.co", "user_metadata": {"edad": "20"}}
    supabase, _ = proveedor({"/auth/v1/user": (200, datos)})
    assert supabase.usuario_de_token("t") == Usuario("u1", "x@y.co", "", None, None)


# ----------------------------------------------------------- sesión segura (JWT en cookie)
INGRESO = {"email": "ana@example.com", "password": CLAVE_PRUEBA}


def cookie_de_sesion(respuesta) -> str:
    return next(c for c in respuesta.headers.get_list("set-cookie") if c.startswith("crediucc_sesion="))


def test_ingreso_guarda_el_jwt_en_cookie_httponly_y_strict():
    respuesta = cliente_con_login().post("/api/v1/auth/ingreso", json=INGRESO)

    cookie = cookie_de_sesion(respuesta).lower()
    assert cookie.startswith("crediucc_sesion=token-ana")
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "max-age=3600" in cookie
    assert "secure" not in cookie  # en http local el navegador no guardaría una cookie Secure


def test_cookie_es_secure_detras_de_https():
    respuesta = cliente_con_login().post("/api/v1/auth/ingreso", json=INGRESO,
                                         headers={"X-Forwarded-Proto": "https"})
    assert "secure" in cookie_de_sesion(respuesta).lower()


def test_registro_sin_confirmacion_tambien_abre_sesion_con_cookie():
    respuesta = cliente_con_login().post("/api/v1/auth/registro", json=REGISTRO)
    assert "httponly" in cookie_de_sesion(respuesta).lower()


def test_salida_revoca_la_sesion_y_borra_la_cookie():
    identidad = IdentidadFalsa()
    cliente = cliente_con_login(identidad)
    cliente.post("/api/v1/auth/ingreso", json=INGRESO)
    assert cliente.get("/api/v1/auth/yo").status_code == 200

    salida = cliente.post("/api/v1/auth/salida")

    assert salida.status_code == 204
    assert identidad.sesiones_cerradas == ["token-ana"]
    assert 'crediucc_sesion=""' in cookie_de_sesion(salida) or "max-age=0" in cookie_de_sesion(salida).lower()
    assert cliente.get("/api/v1/auth/yo").status_code == 401


def test_salida_sin_sesion_o_sin_login_no_falla():
    assert cliente_con_login().post("/api/v1/auth/salida").status_code == 204
    sin_login = TestClient(crear_app(construir_servicio(Configuracion()), MonitorSano()))
    assert sin_login.post("/api/v1/auth/salida").status_code == 204


def test_cabeceras_de_seguridad():
    cliente = cliente_con_login()
    salud = cliente.get("/health")
    assert salud.headers["X-Content-Type-Options"] == "nosniff"
    assert salud.headers["X-Frame-Options"] == "DENY"
    assert salud.headers["Referrer-Policy"] == "no-referrer"
    assert cliente.post("/api/v1/auth/ingreso", json=INGRESO).headers["Cache-Control"] == "no-store"


def test_bearer_tiene_prioridad_sobre_la_cookie():
    cliente = cliente_con_login()
    cliente.post("/api/v1/auth/ingreso", json=INGRESO)  # cookie de Ana
    yo = cliente.get("/api/v1/auth/yo", headers=como("token-luis")).json()
    assert yo["email"] == "luis@example.com"


def test_cerrar_sesion_en_supabase_y_sin_red():
    supabase, http = proveedor({"/auth/v1/logout?scope=local": (204, {})})
    supabase.cerrar_sesion("token-ana")
    metodo, url, cabeceras, _ = http.llamadas[0]
    assert (metodo, url) == ("POST", f"{URL}/auth/v1/logout?scope=local")
    assert cabeceras["Authorization"] == "Bearer token-ana"

    def sin_red(*_):
        raise IdentidadNoDisponibleError("sin red")

    ProveedorSupabase(URL, "llave", enviar=sin_red).cerrar_sesion("token-ana")  # no lanza
    assert ProveedorDeshabilitado().cerrar_sesion("token") is None


def test_configuracion_acepta_nombres_next_public():
    entorno = {"NEXT_PUBLIC_SUPABASE_URL": "https://a.supabase.co",
               "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": "llave", "SUPABASE_URL": " "}
    config = Configuracion.desde_entorno(entorno)
    assert (config.supabase_url, config.supabase_llave_publica) == ("https://a.supabase.co", "llave")
    assert config.login_habilitado is True

"""Adaptador HTTP (FastAPI). Solo traduce HTTP <-> caso de uso; no tiene lógica de negocio.

Sesión segura: el JWT que emite Supabase Auth viaja en una cookie HttpOnly + SameSite=Strict.
El JavaScript del navegador no puede leerla (protege ante XSS) y otros sitios no pueden usarla
(protege ante CSRF). Clientes de API (Postman, pruebas) pueden enviar el mismo JWT como Bearer.
"""
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, FastAPI, Header, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.esquemas import IngresoEntrada, RegistroEntrada, SolicitudEntrada, sesion_a_dict, usuario_a_dict
from app.aplicacion.identidad import (
    CredencialesInvalidasError,
    IdentidadNoDisponibleError,
    ProveedorIdentidad,
    RegistroInvalidoError,
    Sesion,
    Usuario,
)
from app.aplicacion.puertos import MonitorSalud
from app.aplicacion.servicio_solicitudes import ServicioSolicitudes, SolicitudNoEncontradaError
from app.dominio.errores import DominioError

NOMBRE_SERVICIO = "crediucc-api"
LOGIN_NO_CONFIGURADO = "El inicio de sesión no está configurado en la API."
COOKIE_SESION = "crediucc_sesion"
rutas = APIRouter()


class NoAutenticadoError(Exception):
    def __init__(self, mensaje: str = "Debes iniciar sesión para continuar.") -> None:
        super().__init__(mensaje)


def obtener_servicio(request: Request) -> ServicioSolicitudes:
    return request.app.state.servicio


def _identidad_activa(request: Request) -> ProveedorIdentidad | None:
    identidad: ProveedorIdentidad | None = request.app.state.identidad
    return identidad if identidad is not None and identidad.habilitado else None


def _token_bearer(authorization: str | None) -> str:
    esquema, _, token = (authorization or "").partition(" ")
    return token.strip() if esquema.lower() == "bearer" else ""


def token_de_la_peticion(authorization: Annotated[str | None, Header()] = None,
                         crediucc_sesion: Annotated[str | None, Cookie()] = None) -> str:
    """El JWT llega en la cookie HttpOnly (navegador) o como Authorization: Bearer (clientes de API)."""
    return _token_bearer(authorization) or (crediucc_sesion or "").strip()


Token = Annotated[str, Depends(token_de_la_peticion)]


def usuario_actual(request: Request, token: Token) -> Usuario | None:
    """Con login habilitado exige un JWT válido; sin login devuelve None (modo anónimo)."""
    identidad = _identidad_activa(request)
    if identidad is None:
        return None
    usuario = identidad.usuario_de_token(token) if token else None
    if usuario is None:
        raise NoAutenticadoError("Tu sesión no es válida o expiró. Vuelve a iniciar sesión.")
    return usuario


def identidad_requerida(request: Request) -> ProveedorIdentidad:
    identidad = _identidad_activa(request)
    if identidad is None:
        raise IdentidadNoDisponibleError(LOGIN_NO_CONFIGURADO)
    return identidad


Servicio = Annotated[ServicioSolicitudes, Depends(obtener_servicio)]
UsuarioActual = Annotated[Usuario | None, Depends(usuario_actual)]
Identidad = Annotated[ProveedorIdentidad, Depends(identidad_requerida)]


def _id_de(usuario: Usuario | None) -> str | None:
    return None if usuario is None else usuario.id


def _es_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


def _abrir_sesion(request: Request, response: Response, sesion: Sesion) -> dict:
    response.set_cookie(COOKIE_SESION, sesion.token_acceso, max_age=sesion.expira_en_s, path="/",
                        httponly=True, samesite="strict", secure=_es_https(request))
    return sesion_a_dict(sesion)


# --------------------------------------------------------------------- salud
@rutas.get("/health")
def salud(request: Request, response: Response) -> dict:
    sano = request.app.state.monitor_salud.esta_sano()
    if not sano:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return {"status": "healthy" if sano else "unhealthy",
            "version": request.app.version, "service": NOMBRE_SERVICIO,
            "login": _identidad_activa(request) is not None}


# ------------------------------------------------------------- autenticación
@rutas.post("/api/v1/auth/registro", status_code=status.HTTP_201_CREATED)
def registrar(datos: RegistroEntrada, identidad: Identidad, request: Request, response: Response) -> dict:
    resultado = identidad.registrar(datos.email, datos.password, datos.perfil())
    if resultado.requiere_confirmacion:
        return {"requiere_confirmacion": True, "sesion": None,
                "mensaje": "Te enviamos un correo para confirmar tu cuenta. Confírmala y luego ingresa."}
    return {"requiere_confirmacion": False, "sesion": _abrir_sesion(request, response, resultado.sesion),
            "mensaje": "Cuenta creada. ¡Bienvenido a CrediUCC!"}


@rutas.post("/api/v1/auth/ingreso")
def ingresar(credenciales: IngresoEntrada, identidad: Identidad,
             request: Request, response: Response) -> dict:
    return _abrir_sesion(request, response, identidad.ingresar(credenciales.email, credenciales.password))


@rutas.post("/api/v1/auth/salida", status_code=status.HTTP_204_NO_CONTENT)
def salir(request: Request, response: Response, token: Token) -> Response:
    """Revoca la sesión en Supabase y borra la cookie. Funciona aunque la sesión ya haya expirado."""
    identidad = _identidad_activa(request)
    if identidad is not None and token:
        identidad.cerrar_sesion(token)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(COOKIE_SESION, path="/", httponly=True, samesite="strict",
                           secure=_es_https(request))
    return response


@rutas.get("/api/v1/auth/yo")
def yo(usuario: UsuarioActual) -> dict:
    if usuario is None:
        raise NoAutenticadoError()
    return usuario_a_dict(usuario)


# ---------------------------------------------------------------- solicitudes
@rutas.post("/api/v1/solicitudes", status_code=status.HTTP_201_CREATED)
def radicar_solicitud(entrada: SolicitudEntrada, servicio: Servicio, usuario: UsuarioActual) -> dict:
    return servicio.radicar(entrada.a_dominio(), _id_de(usuario)).a_dict()


@rutas.get("/api/v1/solicitudes")
def listar_solicitudes(servicio: Servicio, usuario: UsuarioActual) -> list[dict]:
    return [registro.a_dict() for registro in servicio.listar(_id_de(usuario))]


@rutas.get("/api/v1/solicitudes/{solicitud_id}")
def obtener_solicitud(solicitud_id: int, servicio: Servicio, usuario: UsuarioActual) -> dict:
    return servicio.obtener(solicitud_id, _id_de(usuario)).a_dict()


# ------------------------------------------------------------------- errores
def _error(codigo: int, exc: Exception, cabeceras: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"detail": str(exc)}, headers=cabeceras)


def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    """422 con mensajes legibles: quita el prefijo técnico "Value error, " de los validadores."""
    detalles = [{"loc": list(error.get("loc", ())), "type": error.get("type", ""),
                 "msg": str(error.get("msg", "")).removeprefix("Value error, ")} for error in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": detalles})


def _error_dominio(_: Request, exc: DominioError) -> JSONResponse:
    return _error(status.HTTP_400_BAD_REQUEST, exc)


def _no_encontrada(_: Request, exc: SolicitudNoEncontradaError) -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, exc)


def _no_autenticado(_: Request, exc: NoAutenticadoError) -> JSONResponse:
    return _error(status.HTTP_401_UNAUTHORIZED, exc, {"WWW-Authenticate": "Bearer"})


def _credenciales_invalidas(_: Request, exc: CredencialesInvalidasError) -> JSONResponse:
    return _error(status.HTTP_401_UNAUTHORIZED, exc)


def _registro_invalido(_: Request, exc: RegistroInvalidoError) -> JSONResponse:
    return _error(status.HTTP_400_BAD_REQUEST, exc)


def _identidad_no_disponible(_: Request, exc: IdentidadNoDisponibleError) -> JSONResponse:
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, exc)


async def cabeceras_de_seguridad(request: Request, siguiente):
    """Cabeceras HTTP defensivas en todas las respuestas; las de autenticación nunca se guardan en caché."""
    respuesta = await siguiente(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/v1/auth"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def crear_app(servicio: ServicioSolicitudes, monitor_salud: MonitorSalud,
              version: str = "1.0.0", identidad: ProveedorIdentidad | None = None) -> FastAPI:
    """Fábrica: las dependencias llegan desde fuera (fácil de probar con dobles).

    identidad=None (o un proveedor deshabilitado) = API sin login, como en el CI.
    """
    app = FastAPI(title="CrediUCC API", version=version)
    app.state.servicio = servicio
    app.state.monitor_salud = monitor_salud
    app.state.identidad = identidad
    app.include_router(rutas)
    app.middleware("http")(cabeceras_de_seguridad)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(DominioError, _error_dominio)
    app.add_exception_handler(SolicitudNoEncontradaError, _no_encontrada)
    app.add_exception_handler(NoAutenticadoError, _no_autenticado)
    app.add_exception_handler(CredencialesInvalidasError, _credenciales_invalidas)
    app.add_exception_handler(RegistroInvalidoError, _registro_invalido)
    app.add_exception_handler(IdentidadNoDisponibleError, _identidad_no_disponible)
    return app

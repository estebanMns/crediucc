"""Adaptadores del puerto ProveedorIdentidad.

- ProveedorSupabase: registro, ingreso y verificación de tokens con la API REST de Supabase Auth.
  Las contraseñas nunca pasan por nuestra base de datos: las guarda y cifra Supabase.
- ProveedorDeshabilitado: sin Supabase configurado (pruebas, CI, demo local) la API funciona sin login.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from contextlib import suppress
from typing import Any

from app.aplicacion.identidad import (
    CredencialesInvalidasError,
    IdentidadNoDisponibleError,
    PerfilRegistro,
    RegistroInvalidoError,
    ResultadoRegistro,
    Sesion,
    Usuario,
)

# (método, url, cabeceras, cuerpo JSON) -> (código HTTP, cuerpo JSON)
EnviarHttp = Callable[[str, str, Mapping[str, str], dict | None], tuple[int, dict]]

SIN_CONEXION = "No pudimos conectar con el servicio de autenticación. Inténtalo de nuevo en unos minutos."

MENSAJES_SUPABASE = {
    "user_already_exists": "Ya existe una cuenta con ese correo. Ingresa con tu contraseña.",
    "email_exists": "Ya existe una cuenta con ese correo. Ingresa con tu contraseña.",
    "invalid_credentials": "Correo o contraseña incorrectos.",
    "email_not_confirmed": "Debes confirmar tu correo antes de ingresar. Revisa tu bandeja de entrada.",
    "email_address_invalid": "El correo no es válido.",
    "validation_failed": "Revisa el correo y la contraseña.",
    "over_email_send_rate_limit": "Se enviaron demasiados correos. Espera unos minutos e inténtalo de nuevo.",
    "over_request_rate_limit": "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
    "signup_disabled": "El registro de usuarios está deshabilitado en Supabase.",
    "unexpected_failure": "No pudimos guardar tu perfil. Revisa los datos e inténtalo de nuevo.",
}


def _leer_json(contenido: bytes) -> dict:
    try:
        datos = json.loads(contenido or b"{}")
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def enviar_http(metodo: str, url: str, cabeceras: Mapping[str, str], cuerpo: dict | None,
                timeout_s: float = 10) -> tuple[int, dict]:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(url, data=datos, headers=dict(cabeceras), method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=timeout_s) as respuesta:  # URL fija: https validado
            return respuesta.status, _leer_json(respuesta.read())
    except urllib.error.HTTPError as error:
        return error.code, _leer_json(error.read())
    except (urllib.error.URLError, TimeoutError) as error:
        raise IdentidadNoDisponibleError(SIN_CONEXION) from error


CLAVE_DEBIL = "La contraseña es muy débil. Usa al menos 6 caracteres."


def traducir_error(datos: Mapping[str, Any], por_defecto: str) -> str:
    codigo = str(datos.get("error_code") or datos.get("code") or "")
    if codigo.startswith("weak_"):  # Supabase rechazó la contraseña por débil
        return CLAVE_DEBIL
    return MENSAJES_SUPABASE.get(codigo, por_defecto)


def _entero(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _usuario(datos: Mapping[str, Any]) -> Usuario | None:
    """El perfil (nombre, edad, semestre) viaja en user_metadata de Supabase Auth."""
    if not datos.get("id"):
        return None
    perfil = datos.get("user_metadata") or {}
    return Usuario(id=str(datos["id"]), email=str(datos.get("email") or ""),
                   nombre_completo=str(perfil.get("nombre_completo") or ""),
                   edad=_entero(perfil.get("edad")), semestre=_entero(perfil.get("semestre")))


class ProveedorSupabase:
    def __init__(self, url: str, llave_publica: str, enviar: EnviarHttp = enviar_http) -> None:
        if not url.startswith("https://"):
            raise ValueError("SUPABASE_URL debe empezar por https://")
        self._url = url.rstrip("/")
        self._llave = llave_publica
        self._enviar = enviar

    @property
    def habilitado(self) -> bool:
        return True

    def _llamar(self, metodo: str, ruta: str, cuerpo: dict | None = None,
                token: str | None = None) -> tuple[int, dict]:
        cabeceras = {"apikey": self._llave, "Content-Type": "application/json"}
        if token:
            cabeceras["Authorization"] = f"Bearer {token}"
        return self._enviar(metodo, f"{self._url}{ruta}", cabeceras, cuerpo)

    def _sesion(self, datos: Mapping[str, Any]) -> Sesion:
        usuario = _usuario(datos.get("user") or {})
        if usuario is None or not datos.get("access_token"):
            raise IdentidadNoDisponibleError("Respuesta inesperada del servicio de autenticación.")
        return Sesion(token_acceso=str(datos["access_token"]),
                      expira_en_s=int(datos.get("expires_in") or 3600), usuario=usuario)

    def registrar(self, email: str, password: str, perfil: PerfilRegistro) -> ResultadoRegistro:
        cuerpo = {"email": email, "password": password, "data": perfil.a_metadatos()}
        codigo, datos = self._llamar("POST", "/auth/v1/signup", cuerpo)
        if codigo >= 400:
            raise RegistroInvalidoError(traducir_error(datos, "No pudimos crear la cuenta."))
        if datos.get("access_token"):  # confirmación de correo desactivada: ya queda con sesión
            sesion = self._sesion(datos)
            return ResultadoRegistro(sesion.usuario, sesion)
        # Con confirmación de correo activa, Supabase devuelve solo el usuario.
        return ResultadoRegistro(_usuario(datos.get("user") or datos), None)

    def ingresar(self, email: str, password: str) -> Sesion:
        codigo, datos = self._llamar("POST", "/auth/v1/token?grant_type=password",
                                     {"email": email, "password": password})
        if codigo >= 400:
            raise CredencialesInvalidasError(traducir_error(datos, "Correo o contraseña incorrectos."))
        return self._sesion(datos)

    def usuario_de_token(self, token: str) -> Usuario | None:
        """Supabase valida la firma, la expiración y que la sesión no haya sido revocada del JWT."""
        codigo, datos = self._llamar("GET", "/auth/v1/user", token=token)
        return _usuario(datos) if codigo == 200 else None

    def cerrar_sesion(self, token: str) -> None:
        """Revoca la sesión en Supabase (el refresh token deja de servir). Si falla, no bloquea la salida."""
        with suppress(IdentidadNoDisponibleError):  # sin red: la cookie se borra igual y el JWT expira solo
            self._llamar("POST", "/auth/v1/logout?scope=local", token=token)


class ProveedorDeshabilitado:
    MENSAJE = ("El inicio de sesión no está configurado: faltan SUPABASE_URL y "
               "SUPABASE_PUBLISHABLE_KEY en el entorno de la API.")

    @property
    def habilitado(self) -> bool:
        return False

    def registrar(self, email: str, password: str, perfil: PerfilRegistro) -> ResultadoRegistro:
        raise IdentidadNoDisponibleError(self.MENSAJE)

    def ingresar(self, email: str, password: str) -> Sesion:
        raise IdentidadNoDisponibleError(self.MENSAJE)

    def usuario_de_token(self, _token: str) -> Usuario | None:
        return None  # sin login no hay tokens que validar

    def cerrar_sesion(self, _token: str) -> None:
        return None  # sin login no hay sesión que revocar

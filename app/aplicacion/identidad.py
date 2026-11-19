"""Identidad de usuarios: modelos, errores y el puerto que implementa cada proveedor.

DIP: la API depende de ProveedorIdentidad; Supabase Auth es solo un adaptador más
(ver app/infraestructura/identidad_supabase.py). Sin Supabase configurado se usa un
proveedor deshabilitado y la API funciona sin login (modo de las pruebas y del CI).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PerfilRegistro:
    """Datos que el estudiante entrega al crear su cuenta (ya validados por la API)."""

    nombre_completo: str
    edad: int
    semestre: int

    def a_metadatos(self) -> dict:
        return {"nombre_completo": self.nombre_completo, "edad": self.edad, "semestre": self.semestre}


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    nombre_completo: str = ""
    edad: int | None = None
    semestre: int | None = None


@dataclass(frozen=True)
class Sesion:
    token_acceso: str
    expira_en_s: int
    usuario: Usuario


@dataclass(frozen=True)
class ResultadoRegistro:
    usuario: Usuario | None
    sesion: Sesion | None

    @property
    def requiere_confirmacion(self) -> bool:
        """Supabase no entrega sesión cuando exige confirmar el correo."""
        return self.sesion is None


class IdentidadError(Exception):
    """Error de autenticación con un mensaje apto para mostrar al usuario."""


class CredencialesInvalidasError(IdentidadError):
    pass


class RegistroInvalidoError(IdentidadError):
    pass


class IdentidadNoDisponibleError(IdentidadError):
    pass


class ProveedorIdentidad(Protocol):
    @property
    def habilitado(self) -> bool: ...

    def registrar(self, email: str, password: str, perfil: PerfilRegistro) -> ResultadoRegistro: ...

    def ingresar(self, email: str, password: str) -> Sesion: ...

    def usuario_de_token(self, token: str) -> Usuario | None: ...

    def cerrar_sesion(self, token: str) -> None: ...

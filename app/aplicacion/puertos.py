"""Puertos (interfaces) que necesita el caso de uso.

ISP: interfaces pequeñas y específicas; ningún adaptador implementa métodos que no usa.
DIP: la capa de aplicación define estas abstracciones y la infraestructura las implementa.
"""
from typing import Protocol

from app.dominio.modelos import ResultadoEvaluacion, SolicitudCredito, SolicitudRegistrada


class RepositorioSolicitudes(Protocol):
    """Cada solicitud pertenece a un usuario; usuario_id=None es el modo sin login."""

    def agregar(self, solicitud: SolicitudCredito, resultado: ResultadoEvaluacion,
                usuario_id: str | None = None) -> SolicitudRegistrada: ...

    def actualizar(self, registro: SolicitudRegistrada) -> None: ...

    def obtener(self, solicitud_id: int, usuario_id: str | None = None) -> SolicitudRegistrada | None: ...

    def listar(self, usuario_id: str | None = None) -> list[SolicitudRegistrada]: ...


class PublicadorEventos(Protocol):
    def publicar_aprobacion(self, registro: SolicitudRegistrada) -> bool: ...


class CentralRiesgo(Protocol):
    def consultar(self, solicitud: SolicitudCredito) -> None: ...


class MonitorSalud(Protocol):
    def esta_sano(self) -> bool: ...

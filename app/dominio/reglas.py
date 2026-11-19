"""Reglas de elegibilidad como estrategias intercambiables.

OCP: para agregar una política nueva (p. ej. "no tener mora") se crea otra
subclase de ReglaElegibilidad; el EvaluadorCredito no se modifica.
LSP: todas las reglas cumplen el mismo contrato y son sustituibles entre sí.
"""
from abc import ABC, abstractmethod

from app.dominio.modelos import Motivo, Rango, SolicitudCredito


class ReglaElegibilidad(ABC):
    @abstractmethod
    def motivo_rechazo(self, solicitud: SolicitudCredito) -> Motivo | None:
        """Devuelve el motivo si la solicitud incumple la regla, o None si la cumple."""


EDAD_APROBABLE = Rango(18, 65)


class ReglaEdad(ReglaElegibilidad):
    def __init__(self, rango_permitido: Rango = EDAD_APROBABLE) -> None:
        self._rango = rango_permitido

    def motivo_rechazo(self, solicitud: SolicitudCredito) -> Motivo | None:
        return None if self._rango.contiene(solicitud.edad) else Motivo.EDAD_FUERA_DE_RANGO


class ReglaScoreMinimo(ReglaElegibilidad):
    def __init__(self, minimo: int = 600) -> None:
        self._minimo = minimo

    def motivo_rechazo(self, solicitud: SolicitudCredito) -> Motivo | None:
        return None if solicitud.score >= self._minimo else Motivo.SCORE_INSUFICIENTE


class ReglaIngresoMinimo(ReglaElegibilidad):
    def __init__(self, minimo: float = 2_000_000.0) -> None:
        self._minimo = minimo

    def motivo_rechazo(self, solicitud: SolicitudCredito) -> Motivo | None:
        return None if solicitud.ingresos >= self._minimo else Motivo.INGRESOS_INSUFICIENTES


def reglas_por_defecto() -> tuple[ReglaElegibilidad, ...]:
    """Orden = prioridad del motivo de rechazo que se reporta."""
    return ReglaEdad(), ReglaScoreMinimo(), ReglaIngresoMinimo()

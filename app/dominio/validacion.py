"""Validación defensiva de entradas (Semana 2: entradas destructivas).

SRP: esta clase solo decide si los datos son procesables; no decide el crédito.
"""
from dataclasses import dataclass

from app.dominio.errores import TipoInvalidoError, ValorFueraDeDominioError
from app.dominio.modelos import Rango, SolicitudCredito


def _es_entero(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_numero(valor: object) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


EDAD_DOMINIO = Rango(0, 120)
SCORE_DOMINIO = Rango(300, 850)
MONTO_DOMINIO = Rango(100_000.0, 5_000_000.0)  # pesos colombianos (COP)


@dataclass(frozen=True)
class LimitesDominio:
    edad: Rango = EDAD_DOMINIO
    score: Rango = SCORE_DOMINIO
    monto: Rango = MONTO_DOMINIO
    ingresos_minimos: float = 0.0


LIMITES_POR_DEFECTO = LimitesDominio()


class ValidadorSolicitud:
    def __init__(self, limites: LimitesDominio = LIMITES_POR_DEFECTO) -> None:
        self._limites = limites

    def validar(self, solicitud: SolicitudCredito) -> None:
        self._validar_tipos(solicitud)
        self._validar_dominio(solicitud)

    @staticmethod
    def _validar_tipos(solicitud: SolicitudCredito) -> None:
        verificaciones = (
            ("edad", solicitud.edad, _es_entero),
            ("score", solicitud.score, _es_entero),
            ("ingresos", solicitud.ingresos, _es_numero),
            ("monto", solicitud.monto, _es_numero),
        )
        for campo, valor, es_valido in verificaciones:
            if not es_valido(valor):
                raise TipoInvalidoError(f"El campo '{campo}' tiene un tipo inválido: {valor!r}")

    def _validar_dominio(self, solicitud: SolicitudCredito) -> None:
        limites = self._limites
        if not limites.edad.contiene(solicitud.edad):
            raise ValorFueraDeDominioError("Edad fuera del dominio permitido (0-120).")
        if not limites.score.contiene(solicitud.score):
            raise ValorFueraDeDominioError("Score fuera de rango financiero permitido (300-850).")
        if solicitud.ingresos < limites.ingresos_minimos:
            raise ValorFueraDeDominioError("Los ingresos no pueden ser negativos.")
        if not limites.monto.contiene(solicitud.monto):
            raise ValorFueraDeDominioError("Monto fuera de rango (100.000-5.000.000 COP).")

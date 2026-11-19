"""Dominio: Semana 1 (AAA) y Semana 2 (EP, BVA, parametrize, pytest.raises)."""
import pytest

from app.dominio.errores import TipoInvalidoError, ValorFueraDeDominioError
from app.dominio.evaluador import EvaluadorCredito
from app.dominio.modelos import Decision, Motivo, ResultadoEvaluacion, SolicitudCredito
from app.dominio.reglas import ReglaElegibilidad, reglas_por_defecto
from app.dominio.tasas import PoliticaTasaUCC
from app.dominio.validacion import ValidadorSolicitud
from tests.unit.conftest import nueva_solicitud


@pytest.fixture
def evaluador() -> EvaluadorCredito:
    return EvaluadorCredito.por_defecto()


# ------------------------------------------------------------- Semana 1: AAA
def test_estudiante_con_buen_perfil_es_aprobado_patron_aaa(evaluador):
    # Arrange
    solicitud = nueva_solicitud(edad=22, score=720, ingresos=3_000_000.0, es_estudiante=True)
    # Act
    resultado = evaluador.evaluar(solicitud)
    # Assert
    assert resultado == ResultadoEvaluacion.aprobado(PoliticaTasaUCC.TASA_ESTUDIANTE)


# ------------------------------------------ Semana 2: Partición de Equivalencia
@pytest.mark.parametrize("edad, decision", [
    (15, Decision.RECHAZADO),  # clase inválida menor
    (40, Decision.APROBADO),   # clase válida
    (70, Decision.RECHAZADO),  # clase inválida mayor
])
def test_particion_equivalencia_edad(evaluador, edad, decision):
    assert evaluador.evaluar(nueva_solicitud(edad=edad)).decision is decision


# ------------------------------------------------ Semana 2: Valores Límite
@pytest.mark.parametrize("cambios, motivo_esperado", [
    ({"edad": 17}, Motivo.EDAD_FUERA_DE_RANGO),          # off point -1
    ({"edad": 18}, Motivo.CUMPLE_POLITICA),              # on point inferior
    ({"edad": 65}, Motivo.CUMPLE_POLITICA),              # on point superior
    ({"edad": 66}, Motivo.EDAD_FUERA_DE_RANGO),          # off point +1
    ({"score": 599}, Motivo.SCORE_INSUFICIENTE),
    ({"score": 600}, Motivo.CUMPLE_POLITICA),
    ({"score": 850}, Motivo.CUMPLE_POLITICA),
    ({"ingresos": 1_999_999.0}, Motivo.INGRESOS_INSUFICIENTES),
    ({"ingresos": 2_000_000.0}, Motivo.CUMPLE_POLITICA),
    ({"monto": 100_000.0}, Motivo.CUMPLE_POLITICA),
    ({"monto": 5_000_000.0}, Motivo.CUMPLE_POLITICA),
])
def test_valores_limite_bva(evaluador, cambios, motivo_esperado):
    assert evaluador.evaluar(nueva_solicitud(**cambios)).motivo is motivo_esperado


def test_se_reporta_el_primer_motivo_por_prioridad(evaluador):
    resultado = evaluador.evaluar(nueva_solicitud(edad=17, score=599, ingresos=10.0))
    assert resultado.motivo is Motivo.EDAD_FUERA_DE_RANGO


# --------------------------------------------- Semana 2: entradas destructivas
@pytest.mark.parametrize("cambios, excepcion", [
    ({"edad": -1}, ValorFueraDeDominioError),
    ({"edad": 121}, ValorFueraDeDominioError),
    ({"score": 299}, ValorFueraDeDominioError),
    ({"score": 851}, ValorFueraDeDominioError),
    ({"ingresos": -50.0}, ValorFueraDeDominioError),
    ({"monto": 99_999.0}, ValorFueraDeDominioError),
    ({"monto": 5_000_001.0}, ValorFueraDeDominioError),
    ({"edad": "treinta"}, TipoInvalidoError),
    ({"score": "700"}, TipoInvalidoError),
    ({"score": True}, TipoInvalidoError),   # bool es subclase de int: trampa clásica
    ({"ingresos": None}, TipoInvalidoError),
    ({"monto": "mil"}, TipoInvalidoError),
])
def test_entradas_destructivas(evaluador, cambios, excepcion):
    with pytest.raises(excepcion):
        evaluador.evaluar(nueva_solicitud(**cambios))


def test_errores_de_dominio_son_compatibles_con_excepciones_nativas():
    assert issubclass(ValorFueraDeDominioError, ValueError)
    assert issubclass(TipoInvalidoError, TypeError)


# ------------------------------------------------- Tasas: todas las ramas
@pytest.mark.parametrize("score, es_estudiante, tasa", [
    (749, True, PoliticaTasaUCC.TASA_ESTUDIANTE),     # off point de la preferencial
    (750, True, PoliticaTasaUCC.TASA_PREFERENCIAL),   # on point de la preferencial
    (800, False, PoliticaTasaUCC.TASA_GENERAL),
])
def test_politica_tasa(score, es_estudiante, tasa):
    solicitud = nueva_solicitud(score=score, es_estudiante=es_estudiante)
    assert PoliticaTasaUCC().tasa_para(solicitud) == tasa


# --------------------------------------------- SOLID: Abierto/Cerrado (OCP)
class ReglaListaNegra(ReglaElegibilidad):
    """Regla nueva creada en la prueba SIN modificar el evaluador."""

    def __init__(self, emails_bloqueados: set[str]) -> None:
        self._bloqueados = emails_bloqueados

    def motivo_rechazo(self, solicitud: SolicitudCredito):
        return Motivo.SCORE_INSUFICIENTE if solicitud.email in self._bloqueados else None


def test_evaluador_acepta_reglas_nuevas_sin_modificarse():
    reglas = (*reglas_por_defecto(), ReglaListaNegra({"moroso@example.com"}))
    evaluador = EvaluadorCredito(reglas, PoliticaTasaUCC(), ValidadorSolicitud())

    assert evaluador.evaluar(nueva_solicitud(email="moroso@example.com")).es_aprobado is False
    assert evaluador.evaluar(nueva_solicitud()).es_aprobado is True

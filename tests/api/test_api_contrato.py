"""Semana 5: pruebas de API REST en caja negra desde el contenedor test-runner.

Los 3 niveles: (1) status HTTP, (2) cabeceras y tiempo, (3) contrato JSON Schema.
"""
import os

import pytest
import requests
from jsonschema import validate

BASE_URL = os.getenv("API_URL", "http://localhost:8000")
LATENCIA_MAX_S = float(os.getenv("LATENCIA_MAX_S", "2.0"))

SOLICITUD_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "nombre": {"type": "string"},
        "email": {"type": "string"},
        "monto": {"type": "number"},
        "decision": {"type": "string", "enum": ["APROBADO", "RECHAZADO"]},
        "motivo": {"type": "string"},
        "tasa_mensual": {"type": ["number", "null"]},
        "notificado": {"type": "boolean"},
        "creado_en": {"type": "string"},
    },
    "required": ["id", "nombre", "email", "monto", "decision", "motivo",
                 "tasa_mensual", "notificado", "creado_en"],
}

BASE = {"nombre": "Ana Gomez", "email": "ana@example.com", "edad": 21,
        "score": 780, "ingresos": 2_600_000.0, "monto": 900_000.0, "es_estudiante": True}


def crear(**cambios):
    return requests.post(f"{BASE_URL}/api/v1/solicitudes", json={**BASE, **cambios}, timeout=10)


def test_health_200_y_cabeceras():
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/json")
    assert r.elapsed.total_seconds() < LATENCIA_MAX_S
    assert r.json()["status"] == "healthy"


def test_crear_solicitud_201_cumple_contrato():
    r = crear()
    assert r.status_code == 201
    validate(instance=r.json(), schema=SOLICITUD_SCHEMA)


@pytest.mark.parametrize(
    "cambios, decision",
    [
        ({"edad": 17}, "RECHAZADO"),
        ({"edad": 18}, "APROBADO"),
        ({"score": 599}, "RECHAZADO"),
        ({"score": 600}, "APROBADO"),
        ({"ingresos": 1_999_999.0}, "RECHAZADO"),
        ({"ingresos": 2_000_000.0}, "APROBADO"),
    ],
)
def test_bva_extremo_a_extremo(cambios, decision):
    assert crear(**cambios).json()["decision"] == decision


@pytest.mark.parametrize("cambios, status", [({"score": 851}, 400), ({"monto": 50_000}, 400),
                                             ({"edad": "veinte"}, 422)])
def test_peticiones_invalidas(cambios, status):
    assert crear(**cambios).status_code == status


def test_listado_cumple_contrato():
    r = requests.get(f"{BASE_URL}/api/v1/solicitudes", timeout=5)
    assert r.status_code == 200
    for solicitud in r.json():
        validate(instance=solicitud, schema=SOLICITUD_SCHEMA)


def test_solicitud_inexistente_404():
    assert requests.get(f"{BASE_URL}/api/v1/solicitudes/999999", timeout=5).status_code == 404

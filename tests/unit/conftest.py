"""Fixtures y fábricas compartidas (DRY en la suite)."""
import os
from dataclasses import replace

import pytest

from app.dominio.modelos import SolicitudCredito

# Las pruebas nunca leen el .env real (con credenciales de Supabase) al importar app.main.
os.environ["CREDIUCC_ENV_FILE"] = ""

SOLICITUD_BASE = SolicitudCredito(nombre="Laura Rojas", email="laura@example.com", edad=30,
                                  score=700, ingresos=2_500_000.0, monto=1_000_000.0, es_estudiante=False)


def nueva_solicitud(**cambios) -> SolicitudCredito:
    """Solicitud válida por defecto; cada prueba cambia solo la variable que estudia."""
    return replace(SOLICITUD_BASE, **cambios)


@pytest.fixture(autouse=True)
def credenciales_aws_falsas(monkeypatch):
    """Nunca usar credenciales reales en pruebas unitarias."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(autouse=True)
def sin_supabase(monkeypatch):
    """Ninguna prueba unitaria se conecta a la base de datos ni a Supabase Auth reales."""
    for variable in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY"):
        monkeypatch.delenv(variable, raising=False)

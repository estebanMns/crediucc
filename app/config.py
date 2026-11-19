"""Configuración inmutable leída del entorno (12-Factor: nada sensible en el código)."""
from __future__ import annotations

import os
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Configuracion:
    version: str = "1.0.0"
    nube_habilitada: bool = False
    aws_endpoint: str = "http://localhost:4566"
    aws_region: str = "us-east-1"
    bucket: str = "crediucc-expedientes"
    cola: str = "crediucc-notificaciones"
    latencia_central_ms: int = 0
    # Supabase: con DATABASE_URL las solicitudes se guardan en PostgreSQL;
    # con SUPABASE_URL + SUPABASE_PUBLISHABLE_KEY se exige login. Vacíos = memoria y sin login.
    database_url: str = ""
    supabase_url: str = ""
    supabase_llave_publica: str = ""

    @property
    def login_habilitado(self) -> bool:
        return bool(self.supabase_url and self.supabase_llave_publica)

    @classmethod
    def desde_entorno(cls, entorno: MutableMapping[str, str] = os.environ) -> Configuracion:
        return cls(
            version=entorno.get("APP_VERSION", cls.version),
            nube_habilitada=entorno.get("CLOUD_ENABLED", "false").lower() == "true",
            aws_endpoint=entorno.get("AWS_ENDPOINT_URL", cls.aws_endpoint),
            aws_region=entorno.get("AWS_DEFAULT_REGION", cls.aws_region),
            bucket=entorno.get("S3_BUCKET", cls.bucket),
            cola=entorno.get("SQS_QUEUE", cls.cola),
            latencia_central_ms=int(entorno.get("CENTRAL_RIESGO_LATENCIA_MS", "0")),
            database_url=_primera(entorno, "DATABASE_URL"),
            # Se aceptan también los nombres con prefijo NEXT_PUBLIC_ que muestra el panel de Supabase.
            supabase_url=_primera(entorno, "SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
            supabase_llave_publica=_primera(entorno, "SUPABASE_PUBLISHABLE_KEY",
                                            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
                                            "SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"),
        )


def _primera(entorno: MutableMapping[str, str], *claves: str) -> str:
    """Valor de la primera variable definida y no vacía de la lista."""
    for clave in claves:
        valor = entorno.get(clave, "").strip()
        if valor:
            return valor
    return ""


def cargar_archivo_env(ruta: Path, entorno: MutableMapping[str, str] = os.environ) -> int:
    """Carga variables KEY=valor de un archivo .env sin pisar las que ya existen en el entorno.

    Devuelve cuántas variables cargó. Ignora líneas vacías, comentarios (#) y comillas externas.
    """
    if not ruta.is_file():
        return 0
    cargadas = 0
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = (parte.strip() for parte in linea.split("=", 1))
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if clave and clave not in entorno:
            entorno[clave] = valor
            cargadas += 1
    return cargadas

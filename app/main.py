"""Punto de entrada ASGI: `uvicorn app.main:app`.

En local lee el archivo .env de la raíz del proyecto, sin importar desde qué carpeta se arranque
(ruta configurable con CREDIUCC_ENV_FILE; vacío = no leer). En Docker y en GitHub Actions las
variables llegan directamente por el entorno.
"""
import os
from pathlib import Path

from app.api.aplicacion_web import crear_app
from app.config import Configuracion, cargar_archivo_env
from app.contenedor import construir_identidad, construir_servicio
from app.infraestructura.servicios_externos import MonitorSaludPorEntorno

ENV_DEL_PROYECTO = Path(__file__).resolve().parent.parent / ".env"

archivo_env = os.getenv("CREDIUCC_ENV_FILE", str(ENV_DEL_PROYECTO))
if archivo_env:
    cargar_archivo_env(Path(archivo_env))

configuracion = Configuracion.desde_entorno()
app = crear_app(construir_servicio(configuracion), MonitorSaludPorEntorno(), configuracion.version,
                construir_identidad(configuracion))

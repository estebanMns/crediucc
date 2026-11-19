"""Raíz de composición: único lugar que conoce las clases concretas y las ensambla."""
import boto3

from app.aplicacion.identidad import ProveedorIdentidad
from app.aplicacion.puertos import PublicadorEventos, RepositorioSolicitudes
from app.aplicacion.servicio_solicitudes import ServicioSolicitudes
from app.config import Configuracion
from app.dominio.evaluador import EvaluadorCredito
from app.infraestructura.identidad import ProveedorDeshabilitado, ProveedorSupabase
from app.infraestructura.publicadores import PublicadorAWS, PublicadorNulo
from app.infraestructura.repositorio_memoria import RepositorioEnMemoria
from app.infraestructura.repositorio_postgres import RepositorioPostgres
from app.infraestructura.servicios_externos import CentralRiesgoSimulada


def construir_publicador(config: Configuracion) -> PublicadorEventos:
    if not config.nube_habilitada:
        return PublicadorNulo()
    # Credenciales: boto3 las toma del entorno (GitHub Secrets / LocalStack usa "test").
    sesion = boto3.session.Session(region_name=config.aws_region)
    cliente = {"endpoint_url": config.aws_endpoint}
    return PublicadorAWS(sesion.client("s3", **cliente), sesion.client("sqs", **cliente),
                         config.bucket, config.cola)


def crear_pool_postgres(database_url: str):  # pragma: no cover - requiere una base de datos real
    """Pool de conexiones a Supabase. Abre en segundo plano: la API arranca aunque la BD tarde."""
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    return ConnectionPool(
        database_url, min_size=1, max_size=5, timeout=10, open=True,
        check=ConnectionPool.check_connection,  # descarta conexiones que el pooler cerró
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None},
    )


def construir_repositorio(config: Configuracion, crear_pool=crear_pool_postgres) -> RepositorioSolicitudes:
    if not config.database_url:
        return RepositorioEnMemoria()
    return RepositorioPostgres(crear_pool(config.database_url))


def construir_identidad(config: Configuracion) -> ProveedorIdentidad:
    if not config.login_habilitado:
        return ProveedorDeshabilitado()
    return ProveedorSupabase(config.supabase_url, config.supabase_llave_publica)


def construir_servicio(config: Configuracion, crear_pool=crear_pool_postgres) -> ServicioSolicitudes:
    return ServicioSolicitudes(
        evaluador=EvaluadorCredito.por_defecto(),
        repositorio=construir_repositorio(config, crear_pool),
        publicador=construir_publicador(config),
        central_riesgo=CentralRiesgoSimulada(config.latencia_central_ms),
    )

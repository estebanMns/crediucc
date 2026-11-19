"""Scripts de soporte del pipeline: CD (Semana 9), SLO (Semana 8) e IaC (Semana 10)."""
import json
from pathlib import Path

import boto3
import pytest
import requests
from botocore.exceptions import EndpointConnectionError
from moto import mock_aws

from deploy.deploy import (
    ClienteStaging,
    NotificadorConsola,
    PipelineDespliegue,
    RegistroReleases,
    construir_pipeline,
    enmascarar,
)
from infra.init_infra import AprovisionadorIaC, EstadoDeseado
from load.verificar_slo import AcuerdoNivelServicio, ReporteCarga
from load.verificar_slo import main as verificar_slo


# ------------------------------------------------------------- dobles HTTP
class RespuestaFalsa:
    def __init__(self, codigo: int, cuerpo: dict | None = None) -> None:
        self.status_code, self._cuerpo = codigo, cuerpo or {}

    def json(self) -> dict:
        return self._cuerpo


class HttpFalso:
    def __init__(self, salud=200, transaccion=201, decision="APROBADO", caido=False) -> None:
        self._salud, self._transaccion, self._decision, self._caido = salud, transaccion, decision, caido
        self.posts: list[str] = []

    def get(self, url, timeout):
        if self._caido:
            raise requests.ConnectionError("rechazado")
        return RespuestaFalsa(self._salud)

    def post(self, url, json, timeout):
        self.posts.append(url)
        return RespuestaFalsa(self._transaccion, {"decision": self._decision})


class NotificadorEspia(NotificadorConsola):
    def __init__(self) -> None:
        self.mensajes: list[str] = []

    def notificar(self, mensaje: str) -> None:
        self.mensajes.append(mensaje)


def pipeline(tmp_path: Path, http: HttpFalso, notificador=None):
    notificador = notificador or NotificadorEspia()
    registro = RegistroReleases(tmp_path / "releases.json")
    staging = ClienteStaging("http://staging", http=http, dormir=lambda _: None)
    salida: list[str] = []
    return (PipelineDespliegue(staging, registro, notificador, "abc123", "s3cr3t-clave", salida.append),
            registro, notificador, salida)


# --------------------------------------------------------------------- CD
def test_caso_a_smoke_ok_promueve_a_produccion(tmp_path):
    ejecucion, registro, notificador, salida = pipeline(tmp_path, HttpFalso())
    assert ejecucion.ejecutar() == 0
    assert registro.version_estable == "abc123"
    assert RegistroReleases(tmp_path / "releases.json").version_estable == "abc123"  # persistió
    assert "DESPLIEGUE EXITOSO" in notificador.mensajes[0]
    assert all("s3cr3t-clave" not in linea for linea in salida)  # secreto enmascarado


@pytest.mark.parametrize("http, motivo", [
    (HttpFalso(salud=500), "HTTP 500"),
    (HttpFalso(transaccion=400), "transacción de humo inválida"),
    (HttpFalso(decision="RECHAZADO"), "transacción de humo inválida"),
    (HttpFalso(caido=True), "inaccesible"),
])
def test_caso_b_fallo_en_staging_activa_rollback(tmp_path, http, motivo):
    ejecucion, registro, notificador, _ = pipeline(tmp_path, http)
    assert ejecucion.ejecutar() == 1
    assert registro.version_estable == "1.0.0"
    assert "ROLLBACK" in notificador.mensajes[0]
    assert motivo in notificador.mensajes[0]


def test_enmascarar():
    assert (enmascarar("supersecreto"), enmascarar("")) == ("sup***", "(no configurado)")


def test_notificador_consola(capsys):
    NotificadorConsola().notificar("*titulo*\ndetalle")
    assert "*titulo*" in capsys.readouterr().out


def test_construir_pipeline_desde_entorno(tmp_path):
    assert isinstance(construir_pipeline({"REGISTRO_RELEASES": str(tmp_path / "r.json")}),
                      PipelineDespliegue)


# --------------------------------------------------------------------- SLO
CABECERA = "Type,Name,Request Count,Failure Count,50%,95%,Requests/s\n"


def escribir_csv(tmp_path: Path, p95: int, fallos: int) -> Path:
    ruta = tmp_path / "stats.csv"
    ruta.write_text(CABECERA + f"GET,/health,100,0,5,{p95},20.0\n"
                    f",Aggregated,100,{fallos},5,{p95},20.0\n", encoding="utf-8")
    return ruta


@pytest.mark.parametrize("p95, fallos, codigo", [(900, 0, 0), (1001, 0, 1), (100, 2, 1)])
def test_quality_gate_de_rendimiento(tmp_path, p95, fallos, codigo):
    argumentos = [str(escribir_csv(tmp_path, p95, fallos)), "1000", "1"]
    assert verificar_slo(argumentos, directorio_base=tmp_path) == codigo


def test_slo_rechaza_rutas_fuera_del_directorio_base(tmp_path):
    base = tmp_path / "reportes"
    base.mkdir()
    escribir_csv(tmp_path, 50, 0)
    assert verificar_slo(["../stats.csv"], directorio_base=base) == 2


def test_reporte_y_slo_por_defecto(tmp_path):
    reporte = ReporteCarga.desde_csv(escribir_csv(tmp_path, 50, 0))
    assert [m.nombre for m in reporte.endpoints] == ["GET /health"]
    assert "Agregado: 100 peticiones" in AcuerdoNivelServicio().resumen(reporte)


def test_slo_sin_argumentos_muestra_ayuda():
    assert verificar_slo([]) == 2


# --------------------------------------------------------------------- IaC
@mock_aws
def test_iac_es_idempotente():
    aprovisionador = AprovisionadorIaC(boto3.client("s3"), boto3.client("sqs"), informar=lambda _: None)
    estado = EstadoDeseado(buckets=("bucket-prueba",), colas=("cola-prueba",))

    assert aprovisionador.esperar_disponibilidad() is True
    assert aprovisionador.aplicar(estado) == ["s3:bucket-prueba", "sqs:cola-prueba"]
    assert aprovisionador.aplicar(estado) == []  # 2ª ejecución: sin cambios


def test_iac_espera_y_se_rinde_si_la_nube_no_responde():
    class S3Caido:
        def list_buckets(self):
            raise EndpointConnectionError(endpoint_url="http://localstack:4566")

    pausas = []
    aprovisionador = AprovisionadorIaC(S3Caido(), None, dormir=pausas.append)
    assert aprovisionador.esperar_disponibilidad(intentos=3) is False
    assert len(pausas) == 3


def test_estado_deseado_desde_entorno(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "otro")
    assert EstadoDeseado.desde_entorno().buckets == ("otro",)


def test_registro_releases_mantiene_historial(tmp_path):
    ruta = tmp_path / "r.json"
    registro = RegistroReleases(ruta)
    registro.promover("v2")
    registro.promover("v3")
    assert json.loads(ruta.read_text())["historial"] == ["1.0.0", "v2"]

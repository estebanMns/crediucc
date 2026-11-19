"""Semana 9: motor de Despliegue Continuo con Smoke Test y Rollback automático.

El secreto API_SECRET_KEY se inyecta desde GitHub Secrets y nunca se imprime completo.
Las notificaciones se escriben en la salida del pipeline (log de GitHub Actions).

Variables de entorno:
  STAGING_URL, VERSION_CANDIDATA, API_SECRET_KEY, REGISTRO_RELEASES
"""
from __future__ import annotations

import json
import os
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import requests

VERSION_INICIAL = "1.0.0"
SOLICITUD_DE_HUMO = {"nombre": "Smoke", "email": "smoke@example.com", "edad": 25,
                     "score": 700, "ingresos": 2500.0, "monto": 500.0, "es_estudiante": True}


def enmascarar(secreto: str) -> str:
    return f"{secreto[:3]}***" if secreto else "(no configurado)"


# ----------------------------------------------------------------- notificación
class Notificador(ABC):
    @abstractmethod
    def notificar(self, mensaje: str) -> None: ...


class NotificadorConsola(Notificador):
    def __init__(self, escribir: Callable[[str], None] = print) -> None:
        self._escribir = escribir

    def notificar(self, mensaje: str) -> None:
        self._escribir(f"   [notificación] {mensaje.splitlines()[0]}")


# ------------------------------------------------------------------ smoke test
@dataclass(frozen=True)
class ResultadoSmoke:
    exitoso: bool
    detalle: str


class ClienteStaging:
    def __init__(self, url_base: str, http=requests, intentos: int = 3,
                 dormir: Callable[[float], None] = time.sleep) -> None:
        self._url = url_base.rstrip("/")
        self._http = http
        self._intentos = intentos
        self._dormir = dormir

    def ejecutar_smoke_test(self) -> ResultadoSmoke:
        for _ in range(self._intentos):
            try:
                return self._verificar_salud_y_transaccion()
            except requests.RequestException:
                self._dormir(2)
        return ResultadoSmoke(False, "servidor de staging inaccesible")

    def _verificar_salud_y_transaccion(self) -> ResultadoSmoke:
        salud = self._http.get(f"{self._url}/health", timeout=3)
        if salud.status_code != 200:
            return ResultadoSmoke(False, f"/health respondió HTTP {salud.status_code}")
        transaccion = self._http.post(f"{self._url}/api/v1/solicitudes",
                                      json=SOLICITUD_DE_HUMO, timeout=5)
        if transaccion.status_code != 201 or transaccion.json().get("decision") != "APROBADO":
            return ResultadoSmoke(False, f"transacción de humo inválida (HTTP {transaccion.status_code})")
        return ResultadoSmoke(True, "200 OK en /health y 201 APROBADO en la transacción de humo")


# --------------------------------------------------------- registro de versiones
class RegistroReleases:
    """Guarda la última versión estable (Last Known Good Build) y el historial."""

    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        self._datos = (json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists()
                       else {"produccion": VERSION_INICIAL, "historial": []})

    @property
    def version_estable(self) -> str:
        return self._datos["produccion"]

    def promover(self, version: str) -> None:
        self._datos["historial"].append(self.version_estable)
        self._datos["produccion"] = version
        self._ruta.write_text(json.dumps(self._datos, indent=2), encoding="utf-8")


# ------------------------------------------------------------------- pipeline
class PipelineDespliegue:
    def __init__(self, staging: ClienteStaging, registro: RegistroReleases,
                 notificador: Notificador, version_candidata: str, secreto: str,
                 escribir: Callable[[str], None] = print) -> None:
        self._staging = staging
        self._registro = registro
        self._notificador = notificador
        self._candidata = version_candidata
        self._secreto = secreto
        self._escribir = escribir

    def ejecutar(self) -> int:
        estable = self._registro.version_estable
        self._escribir("=== PIPELINE DE DESPLIEGUE CONTINUO (CD) — CrediUCC ===")
        self._escribir(f"[1/4] Secreto inyectado: {enmascarar(self._secreto)}")
        self._escribir(f"[2/4] Versión candidata: {self._candidata} | estable: {estable}")
        self._escribir("[3/4] Ejecutando smoke test en staging...")
        resultado = self._staging.ejecutar_smoke_test()
        return self._promover(resultado) if resultado.exitoso else self._revertir(resultado, estable)

    def _promover(self, resultado: ResultadoSmoke) -> int:
        self._escribir(f"   -> [OK] {resultado.detalle}")
        self._escribir(f"[4/4] PROMOCIONANDO {self._candidata} A PRODUCCIÓN")
        self._registro.promover(self._candidata)
        self._notificador.notificar(f"*DESPLIEGUE EXITOSO* 🚀\n• Versión: `{self._candidata}`\n"
                                    f"• Smoke test: {resultado.detalle}")
        return 0

    def _revertir(self, resultado: ResultadoSmoke, estable: str) -> int:
        self._escribir(f"   -> [ERROR] {resultado.detalle}")
        self._escribir(f"[4/4] ROLLBACK AUTOMÁTICO: se mantiene la versión estable {estable}")
        self._notificador.notificar(f"*ALERTA: ROLLBACK AUTOMÁTICO* 🚨\n"
                                    f"• Candidata rechazada: `{self._candidata}`\n"
                                    f"• Motivo: {resultado.detalle}\n• Producción sigue en: `{estable}`")
        return 1


def construir_pipeline(entorno: Mapping[str, str]) -> PipelineDespliegue:
    return PipelineDespliegue(
        staging=ClienteStaging(entorno.get("STAGING_URL", "http://localhost:8000")),
        registro=RegistroReleases(Path(entorno.get("REGISTRO_RELEASES", "releases.json"))),
        notificador=NotificadorConsola(),
        version_candidata=entorno.get("VERSION_CANDIDATA", VERSION_INICIAL),
        secreto=entorno.get("API_SECRET_KEY", ""),
    )


if __name__ == "__main__":
    sys.exit(construir_pipeline(os.environ).ejecutar())

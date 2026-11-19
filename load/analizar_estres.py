"""Analiza la prueba de estrés: punto de quiebre por escalón y recuperación del sistema.

Uso (desde la raíz del proyecto):
  python -m load.analizar_estres estres_stats_history.csv [p95_max_ms] [fallos_max_pct]

- Divide el historial de Locust por escalones (según el plan de load/plan_estres.py).
- PUNTO DE QUIEBRE: primer escalón donde el p95 supera el límite o los fallos superan el máximo.
- RECUPERACIÓN (Quality Gate): al volver a pocos usuarios, el sistema debe cumplir otra vez el SLO.
  Exit code 0 = se recuperó; 1 = no se recuperó (el pipeline falla); 2 = uso incorrecto.

Que el sistema se rompa NO es un fallo de la prueba: encontrar ese punto es el objetivo.
"""
from __future__ import annotations

import csv
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from load.plan_estres import Etapa, PlanEstres
from load.verificar_slo import resolver_ruta_segura

FILA_AGREGADA = "Aggregated"


@dataclass(frozen=True)
class MuestraHistorial:
    segundo: int
    usuarios: int
    rps: float
    p95_ms: float | None
    total_peticiones: int
    total_fallos: int

    @classmethod
    def desde_fila(cls, fila: Mapping[str, str]) -> MuestraHistorial:
        p95 = fila.get("95%", "N/A")
        return cls(segundo=int(fila["Timestamp"]), usuarios=int(fila["User Count"]),
                   rps=float(fila["Requests/s"]), p95_ms=None if p95 in ("", "N/A") else float(p95),
                   total_peticiones=int(fila["Total Request Count"]),
                   total_fallos=int(fila["Total Failure Count"]))


@dataclass(frozen=True)
class MedicionEtapa:
    etapa: Etapa
    usuarios_max: int
    peticiones: int
    fallos: int
    p95_ms: float | None
    rps: float

    @property
    def porcentaje_fallos(self) -> float:
        return 100 * self.fallos / self.peticiones if self.peticiones else 0.0


@dataclass(frozen=True)
class Umbral:
    p95_max_ms: float = 1000.0
    fallos_max_pct: float = 1.0

    def se_cumple(self, medicion: MedicionEtapa) -> bool:
        p95_ok = medicion.p95_ms is not None and medicion.p95_ms <= self.p95_max_ms
        return medicion.peticiones > 0 and p95_ok and medicion.porcentaje_fallos <= self.fallos_max_pct


@dataclass(frozen=True)
class ResultadoEstres:
    mediciones: tuple[MedicionEtapa, ...]
    umbral: Umbral

    @property
    def punto_de_quiebre(self) -> MedicionEtapa | None:
        subida = (m for m in self.mediciones if not m.etapa.es_recuperacion)
        return next((m for m in subida if not self.umbral.se_cumple(m)), None)

    @property
    def capacidad_segura(self) -> MedicionEtapa | None:
        """Último escalón que cumplió el SLO antes del punto de quiebre."""
        segura = None
        for medicion in self.mediciones:
            if medicion.etapa.es_recuperacion or not self.umbral.se_cumple(medicion):
                break
            segura = medicion
        return segura

    @property
    def recuperacion(self) -> MedicionEtapa | None:
        return next((m for m in self.mediciones if m.etapa.es_recuperacion), None)

    @property
    def se_recupero(self) -> bool:
        return self.recuperacion is not None and self.umbral.se_cumple(self.recuperacion)


def leer_historial(ruta: Path) -> list[MuestraHistorial]:
    with ruta.open(newline="", encoding="utf-8") as archivo:
        filas = [f for f in csv.DictReader(archivo) if f.get("Name") == FILA_AGREGADA]
    return sorted((MuestraHistorial.desde_fila(f) for f in filas), key=lambda m: m.segundo)


def analizar(muestras: Iterable[MuestraHistorial], plan: PlanEstres, umbral: Umbral) -> ResultadoEstres:
    muestras = list(muestras)
    if not muestras:
        return ResultadoEstres((), umbral)
    inicio = muestras[0].segundo
    por_etapa: dict[int, list[MuestraHistorial]] = {}
    for muestra in muestras:
        indice = plan.indice_etapa(muestra.segundo - inicio)
        por_etapa.setdefault(len(plan.etapas) - 1 if indice is None else indice, []).append(muestra)

    mediciones = []
    acumulado_peticiones = acumulado_fallos = 0
    for indice, etapa in enumerate(plan.etapas):
        grupo = por_etapa.get(indice, [])
        if not grupo:
            continue
        ultima = grupo[-1]
        p95s = [m.p95_ms for m in grupo if m.p95_ms is not None]
        mediciones.append(MedicionEtapa(
            etapa=etapa, usuarios_max=max(m.usuarios for m in grupo),
            peticiones=ultima.total_peticiones - acumulado_peticiones,
            fallos=ultima.total_fallos - acumulado_fallos,
            p95_ms=max(p95s) if p95s else None,
            rps=sum(m.rps for m in grupo) / len(grupo),
        ))
        acumulado_peticiones, acumulado_fallos = ultima.total_peticiones, ultima.total_fallos
    return ResultadoEstres(tuple(mediciones), umbral)


def _p95(medicion: MedicionEtapa) -> str:
    return "—" if medicion.p95_ms is None else f"{medicion.p95_ms:,.0f} ms"


def informe_markdown(resultado: ResultadoEstres) -> str:
    umbral = resultado.umbral
    lineas = ["## Prueba de estrés — CrediUCC", "",
              f"SLO por escalón: p95 ≤ {umbral.p95_max_ms:,.0f} ms "
              f"y fallos ≤ {umbral.fallos_max_pct:.2f} %", "",
              "| Etapa | Usuarios | Peticiones | RPS | p95 | Fallos | SLO |",
              "|---|---:|---:|---:|---:|---:|:---:|"]
    for m in resultado.mediciones:
        marca = "✅" if umbral.se_cumple(m) else "❌"
        lineas.append(f"| {m.etapa.nombre} | {m.etapa.usuarios} | {m.peticiones} | {m.rps:.1f} | {_p95(m)} "
                      f"| {m.porcentaje_fallos:.2f} % | {marca} |")
    lineas.append("")

    if not resultado.mediciones:
        lineas.append("**Sin datos:** el historial de Locust está vacío.")
        return "\n".join(lineas)

    quiebre, segura = resultado.punto_de_quiebre, resultado.capacidad_segura
    if quiebre is None:
        lineas.append("**Punto de quiebre:** no se alcanzó. El sistema aguantó todos los escalones; "
                      "sube ESTRES_ESCALONES para encontrar su límite.")
    else:
        lineas.append(f"**Punto de quiebre:** {quiebre.etapa.nombre} — p95 {_p95(quiebre)}, "
                      f"fallos {quiebre.porcentaje_fallos:.2f} %.")
    if segura is not None:
        lineas.append(f"**Capacidad segura:** hasta {segura.etapa.nombre} "
                      f"({segura.rps:.1f} RPS) cumpliendo el SLO.")
    lineas.append("**Recuperación:** " + ("✅ el sistema volvió a cumplir el SLO al bajar la carga."
                                         if resultado.se_recupero else
                                         "❌ el sistema NO volvió a cumplir el SLO al bajar la carga."))
    return "\n".join(lineas)


def main(argumentos: list[str], directorio_base: Path | None = None,
         plan: PlanEstres | None = None) -> int:
    if not argumentos:
        print(__doc__)
        return 2
    ruta = resolver_ruta_segura(argumentos[0], directorio_base or Path.cwd())
    if ruta is None or not ruta.is_file():
        print(f"[ERROR] No se encontró el historial dentro del directorio de trabajo: {argumentos[0]}")
        return 2
    umbral = Umbral(*(float(a) for a in argumentos[1:3]))
    resultado = analizar(leer_historial(ruta), plan or PlanEstres.desde_entorno(), umbral)
    print(informe_markdown(resultado))
    return 0 if resultado.se_recupero else 1


if __name__ == "__main__":  # pragma: no cover
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))

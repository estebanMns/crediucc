"""Plan de la prueba de estrés: escalones de usuarios que suben hasta romper el sistema.

Prueba de CARGA (load/locustfile.py): ¿aguanta el tráfico esperado (200 usuarios)?
Prueba de ESTRÉS (load/estres.py):   ¿en qué punto se rompe y se recupera después?

El plan es lógica pura (sin importar Locust) para poder probarlo unitariamente:
    100 → 250 → 500 → 750 → 1000 usuarios (un escalón por minuto) → recuperación con 50 usuarios.

Variables de entorno (opcionales): ESTRES_ESCALONES="100,250,500", ESTRES_DURACION_S=60,
ESTRES_USUARIOS_RECUPERACION=50, ESTRES_TASA_LLEGADA=50.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ESCALONES_POR_DEFECTO = (100, 250, 500, 750, 1000)


@dataclass(frozen=True)
class Etapa:
    nombre: str
    usuarios: int
    es_recuperacion: bool = False


@dataclass(frozen=True)
class PlanEstres:
    escalones: tuple[int, ...] = ESCALONES_POR_DEFECTO
    duracion_s: int = 60
    usuarios_recuperacion: int = 50
    tasa_llegada: float = 50.0  # usuarios nuevos por segundo al subir de escalón

    def __post_init__(self) -> None:
        if not self.escalones or any(u <= 0 for u in self.escalones):
            raise ValueError("Los escalones deben ser números de usuarios mayores que cero.")
        if list(self.escalones) != sorted(self.escalones):
            raise ValueError("Los escalones deben ir de menor a mayor.")
        if self.duracion_s <= 0 or self.usuarios_recuperacion <= 0 or self.tasa_llegada <= 0:
            raise ValueError("Duración, usuarios de recuperación y tasa deben ser mayores que cero.")

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str] = os.environ) -> PlanEstres:
        texto = entorno.get("ESTRES_ESCALONES", "").strip()
        escalones = (tuple(int(u) for u in texto.split(",") if u.strip()) if texto
                     else ESCALONES_POR_DEFECTO)
        return cls(escalones=escalones,
                   duracion_s=int(entorno.get("ESTRES_DURACION_S", "60")),
                   usuarios_recuperacion=int(entorno.get("ESTRES_USUARIOS_RECUPERACION", "50")),
                   tasa_llegada=float(entorno.get("ESTRES_TASA_LLEGADA", "50")))

    @property
    def etapas(self) -> tuple[Etapa, ...]:
        subida = tuple(Etapa(f"{u} usuarios", u) for u in self.escalones)
        recuperacion = Etapa(f"recuperación ({self.usuarios_recuperacion})", self.usuarios_recuperacion, True)
        return (*subida, recuperacion)

    @property
    def duracion_total_s(self) -> int:
        return len(self.etapas) * self.duracion_s

    def indice_etapa(self, segundos: float) -> int | None:
        """Etapa que corresponde a un instante desde el inicio; None cuando la prueba terminó."""
        if segundos < 0:
            return 0
        indice = int(segundos // self.duracion_s)
        return indice if indice < len(self.etapas) else None

    def objetivo(self, segundos: float) -> tuple[int, float] | None:
        """(usuarios, tasa de llegada) que Locust debe tener en ese instante; None = terminar."""
        indice = self.indice_etapa(segundos)
        if indice is None:
            return None
        etapa = self.etapas[indice]
        # Al bajar a la etapa de recuperación los usuarios salen de inmediato.
        tasa = self.tasa_llegada
        if etapa.es_recuperacion:
            tasa = max(self.tasa_llegada, float(self.escalones[-1]))
        return etapa.usuarios, tasa

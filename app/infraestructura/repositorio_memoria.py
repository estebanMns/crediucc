"""Adaptador de persistencia en memoria (seguro para hilos: Uvicorn atiende en paralelo).

Se usa cuando no hay DATABASE_URL: pruebas, CI y la demo local sin Supabase.
"""
from itertools import count
from threading import Lock

from app.dominio.modelos import ResultadoEvaluacion, SolicitudCredito, SolicitudRegistrada


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self._registros: dict[int, SolicitudRegistrada] = {}
        self._secuencia = count(1)
        self._candado = Lock()

    def agregar(self, solicitud: SolicitudCredito, resultado: ResultadoEvaluacion,
                usuario_id: str | None = None) -> SolicitudRegistrada:
        with self._candado:
            registro = SolicitudRegistrada(next(self._secuencia), solicitud, resultado, usuario_id=usuario_id)
            self._registros[registro.id] = registro
        return registro

    def actualizar(self, registro: SolicitudRegistrada) -> None:
        with self._candado:
            self._registros[registro.id] = registro

    def obtener(self, solicitud_id: int, usuario_id: str | None = None) -> SolicitudRegistrada | None:
        registro = self._registros.get(solicitud_id)
        return registro if registro is not None and registro.usuario_id == usuario_id else None

    def listar(self, usuario_id: str | None = None) -> list[SolicitudRegistrada]:
        with self._candado:
            return [r for r in self._registros.values() if r.usuario_id == usuario_id]

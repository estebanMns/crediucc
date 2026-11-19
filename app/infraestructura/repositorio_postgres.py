"""Adaptador de persistencia en PostgreSQL (Supabase).

Cumple el mismo puerto RepositorioSolicitudes que RepositorioEnMemoria (LSP): el dominio,
el caso de uso y la API no saben qué base de datos hay detrás. El esquema está en
db/001_crear_solicitudes.sql.

Recibe un pool de conexiones con filas tipo diccionario (psycopg dict_row); en las
pruebas se reemplaza por un doble que no necesita base de datos.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from app.dominio.modelos import (
    Decision,
    Motivo,
    ResultadoEvaluacion,
    SolicitudCredito,
    SolicitudRegistrada,
)

# Consultas fijas y parametrizadas (%s): nunca se concatenan datos del usuario al SQL.
SQL_INSERTAR = """
    INSERT INTO public.solicitudes
        (usuario_id, nombre, email, edad, score, ingresos, monto, es_estudiante,
         decision, motivo, tasa_mensual, notificado)
    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, usuario_id, nombre, email, edad, score, ingresos, monto, es_estudiante,
              decision, motivo, tasa_mensual, notificado, creado_en
"""

SQL_ACTUALIZAR_NOTIFICACION = "UPDATE public.solicitudes SET notificado = %s WHERE id = %s"

SQL_OBTENER = """
    SELECT id, usuario_id, nombre, email, edad, score, ingresos, monto, es_estudiante,
           decision, motivo, tasa_mensual, notificado, creado_en
    FROM public.solicitudes
    WHERE id = %s AND usuario_id IS NOT DISTINCT FROM %s::uuid
"""

SQL_LISTAR = """
    SELECT id, usuario_id, nombre, email, edad, score, ingresos, monto, es_estudiante,
           decision, motivo, tasa_mensual, notificado, creado_en
    FROM public.solicitudes
    WHERE usuario_id IS NOT DISTINCT FROM %s::uuid
    ORDER BY id
"""


def _decimal_a_float(valor: Decimal | float | None) -> float | None:
    return None if valor is None else float(valor)


def fila_a_registro(fila: Mapping[str, Any]) -> SolicitudRegistrada:
    solicitud = SolicitudCredito(
        nombre=fila["nombre"], email=fila["email"], edad=fila["edad"], score=fila["score"],
        ingresos=float(fila["ingresos"]), monto=float(fila["monto"]), es_estudiante=fila["es_estudiante"],
    )
    resultado = ResultadoEvaluacion(Decision(fila["decision"]), Motivo(fila["motivo"]),
                                    _decimal_a_float(fila["tasa_mensual"]))
    usuario_id = fila["usuario_id"]
    return SolicitudRegistrada(
        id=int(fila["id"]), solicitud=solicitud, resultado=resultado, notificado=fila["notificado"],
        creado_en=fila["creado_en"], usuario_id=None if usuario_id is None else str(usuario_id),
    )


class RepositorioPostgres:
    def __init__(self, pool) -> None:
        self._pool = pool

    def agregar(self, solicitud: SolicitudCredito, resultado: ResultadoEvaluacion,
                usuario_id: str | None = None) -> SolicitudRegistrada:
        parametros = (usuario_id, solicitud.nombre, solicitud.email, solicitud.edad, solicitud.score,
                      solicitud.ingresos, solicitud.monto, solicitud.es_estudiante,
                      resultado.decision.value, resultado.motivo.value, resultado.tasa_mensual, False)
        with self._pool.connection() as conexion:
            fila = conexion.execute(SQL_INSERTAR, parametros).fetchone()
        return fila_a_registro(fila)

    def actualizar(self, registro: SolicitudRegistrada) -> None:
        with self._pool.connection() as conexion:
            conexion.execute(SQL_ACTUALIZAR_NOTIFICACION, (registro.notificado, registro.id))

    def obtener(self, solicitud_id: int, usuario_id: str | None = None) -> SolicitudRegistrada | None:
        with self._pool.connection() as conexion:
            fila = conexion.execute(SQL_OBTENER, (solicitud_id, usuario_id)).fetchone()
        return None if fila is None else fila_a_registro(fila)

    def listar(self, usuario_id: str | None = None) -> list[SolicitudRegistrada]:
        with self._pool.connection() as conexion:
            filas = conexion.execute(SQL_LISTAR, (usuario_id,)).fetchall()
        return [fila_a_registro(fila) for fila in filas]

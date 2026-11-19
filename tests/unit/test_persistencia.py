"""Persistencia: repositorio PostgreSQL (con un pool falso), selección de repositorio y archivo .env."""
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from app.config import Configuracion, cargar_archivo_env
from app.contenedor import construir_repositorio
from app.dominio.modelos import Motivo, ResultadoEvaluacion
from app.infraestructura.repositorio_memoria import RepositorioEnMemoria
from app.infraestructura.repositorio_postgres import (
    SQL_ACTUALIZAR_NOTIFICACION,
    SQL_INSERTAR,
    SQL_LISTAR,
    SQL_OBTENER,
    RepositorioPostgres,
    fila_a_registro,
)
from tests.unit.conftest import nueva_solicitud

AHORA = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
USUARIO = "11111111-1111-1111-1111-111111111111"


def fila(**cambios) -> dict:
    """Fila tal como la entrega psycopg con dict_row (numeric llega como Decimal)."""
    base = {"id": 7, "usuario_id": USUARIO, "nombre": "Laura Rojas", "email": "laura@example.com",
            "edad": 30, "score": 700, "ingresos": Decimal("2500000.00"), "monto": Decimal("1000000.00"),
            "es_estudiante": False, "decision": "APROBADO", "motivo": "CUMPLE_POLITICA",
            "tasa_mensual": Decimal("1.90"), "notificado": False, "creado_en": AHORA}
    return {**base, **cambios}


class CursorFalso:
    def __init__(self, filas: list[dict]) -> None:
        self._filas = filas

    def fetchone(self):
        return self._filas[0] if self._filas else None

    def fetchall(self):
        return self._filas


class PoolFalso:
    """Imita psycopg_pool.ConnectionPool: registra cada SQL ejecutado y devuelve filas fijas."""

    def __init__(self, filas: list[dict]) -> None:
        self._filas = filas
        self.ejecutados: list[tuple[str, tuple]] = []

    @contextmanager
    def connection(self):
        yield self

    def execute(self, sql: str, parametros: tuple) -> CursorFalso:
        self.ejecutados.append((sql, parametros))
        return CursorFalso(self._filas)


def test_fila_a_registro_convierte_tipos_de_postgres():
    registro = fila_a_registro(fila())
    assert registro.solicitud.ingresos == 2_500_000.0
    assert isinstance(registro.solicitud.monto, float)
    assert registro.resultado.tasa_mensual == 1.9
    assert registro.usuario_id == USUARIO
    assert registro.a_dict()["creado_en"] == AHORA.isoformat()


def test_fila_rechazada_sin_tasa_y_sin_usuario():
    registro = fila_a_registro(fila(decision="RECHAZADO", motivo="SCORE_INSUFICIENTE",
                                    tasa_mensual=None, usuario_id=None))
    assert registro.resultado.motivo is Motivo.SCORE_INSUFICIENTE
    assert (registro.resultado.tasa_mensual, registro.usuario_id) == (None, None)


def test_agregar_inserta_con_parametros_y_devuelve_el_registro():
    pool = PoolFalso([fila()])
    resultado = ResultadoEvaluacion.aprobado(1.9)
    registro = RepositorioPostgres(pool).agregar(nueva_solicitud(), resultado, USUARIO)

    sql, parametros = pool.ejecutados[0]
    assert sql == SQL_INSERTAR
    assert parametros[0] == USUARIO
    assert parametros[8:] == ("APROBADO", "CUMPLE_POLITICA", 1.9, False)
    assert registro.id == 7


def test_actualizar_obtener_y_listar_filtran_por_usuario():
    pool = PoolFalso([fila(notificado=True)])
    repositorio = RepositorioPostgres(pool)

    registro = repositorio.obtener(7, USUARIO)
    repositorio.actualizar(registro)
    listado = repositorio.listar(USUARIO)

    assert pool.ejecutados == [(SQL_OBTENER, (7, USUARIO)),
                               (SQL_ACTUALIZAR_NOTIFICACION, (True, 7)),
                               (SQL_LISTAR, (USUARIO,))]
    assert [r.id for r in listado] == [7]


def test_obtener_inexistente_devuelve_none():
    assert RepositorioPostgres(PoolFalso([])).obtener(99, USUARIO) is None


def test_consultas_son_parametrizadas():
    for sql in (SQL_INSERTAR, SQL_OBTENER, SQL_LISTAR, SQL_ACTUALIZAR_NOTIFICACION):
        assert "%s" in sql
        assert "{" not in sql  # sin formateo de cadenas: no hay inyección SQL posible


def test_construir_repositorio_segun_database_url():
    assert isinstance(construir_repositorio(Configuracion()), RepositorioEnMemoria)

    pools = []
    config = Configuracion(database_url="postgresql://usuario@host/db")
    repositorio = construir_repositorio(config, crear_pool=lambda url: pools.append(url) or PoolFalso([]))
    assert isinstance(repositorio, RepositorioPostgres)
    assert pools == ["postgresql://usuario@host/db"]


def test_repositorio_en_memoria_aisla_usuarios():
    repositorio = RepositorioEnMemoria()
    de_ana = repositorio.agregar(nueva_solicitud(), ResultadoEvaluacion.aprobado(1.5), "ana")
    repositorio.agregar(nueva_solicitud(), ResultadoEvaluacion.aprobado(1.5), "luis")

    assert [r.id for r in repositorio.listar("ana")] == [de_ana.id]
    assert repositorio.obtener(de_ana.id, "luis") is None
    assert repositorio.obtener(de_ana.id, "ana") == de_ana
    assert repositorio.listar() == []  # el modo anónimo no ve solicitudes de usuarios


# ------------------------------------------------------------------- archivo .env
def test_cargar_archivo_env(tmp_path):
    ruta = tmp_path / ".env"
    ruta.write_text("# comentario\n\nSUPABASE_URL=https://demo.supabase.co\nCOMILLAS=\"con espacios\"\n"
                    "YA_DEFINIDA=del-archivo\nLINEA_SIN_IGUAL\nVACIA=\n", encoding="utf-8")
    entorno = {"YA_DEFINIDA": "del-entorno"}

    assert cargar_archivo_env(ruta, entorno) == 3
    assert entorno == {"YA_DEFINIDA": "del-entorno", "SUPABASE_URL": "https://demo.supabase.co",
                       "COMILLAS": "con espacios", "VACIA": ""}


def test_cargar_archivo_env_inexistente(tmp_path):
    assert cargar_archivo_env(tmp_path / "no-existe.env", {}) == 0


def test_configuracion_lee_supabase_del_entorno():
    config = Configuracion.desde_entorno({"DATABASE_URL": " postgresql://x ", "SUPABASE_URL": "https://a.supabase.co",
                                          "SUPABASE_PUBLISHABLE_KEY": "llave"})
    assert (config.database_url, config.login_habilitado) == ("postgresql://x", True)
    assert Configuracion.desde_entorno({}).login_habilitado is False

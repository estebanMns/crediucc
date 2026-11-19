"""Prueba de estrés: plan de escalones y analizador del punto de quiebre (sin ejecutar Locust)."""
from pathlib import Path

import pytest

from load.analizar_estres import (
    MuestraHistorial,
    Umbral,
    analizar,
    informe_markdown,
    leer_historial,
    main,
)
from load.plan_estres import ESCALONES_POR_DEFECTO, PlanEstres

PLAN = PlanEstres(escalones=(100, 200, 400), duracion_s=10, usuarios_recuperacion=20, tasa_llegada=25)
CABECERA = ("Timestamp,User Count,Type,Name,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,"
            "99.9%,99.99%,100%,Total Request Count,Total Failure Count,Total Median Response Time,"
            "Total Average Response Time,Total Min Response Time,Total Max Response Time,"
            "Total Average Content Size\n")


# --------------------------------------------------------------------- plan
@pytest.mark.parametrize("segundo, esperado", [
    (0, (100, 25.0)), (9.9, (100, 25.0)), (10, (200, 25.0)), (25, (400, 25.0)),
    (30, (20, 400.0)),  # recuperación: los usuarios salen de inmediato
    (40, None),         # fin de la prueba
])
def test_plan_sube_por_escalones_y_luego_se_recupera(segundo, esperado):
    assert PLAN.objetivo(segundo) == esperado


def test_plan_por_defecto_y_duracion_total():
    plan = PlanEstres()
    assert plan.escalones == ESCALONES_POR_DEFECTO
    assert plan.duracion_total_s == 6 * 60
    assert [e.nombre for e in plan.etapas][-1] == "recuperación (50)"
    assert plan.indice_etapa(-5) == 0


def test_plan_desde_entorno():
    plan = PlanEstres.desde_entorno({"ESTRES_ESCALONES": "50, 150,300", "ESTRES_DURACION_S": "20",
                                     "ESTRES_USUARIOS_RECUPERACION": "10", "ESTRES_TASA_LLEGADA": "30"})
    assert (plan.escalones, plan.duracion_s) == ((50, 150, 300), 20)
    assert (plan.usuarios_recuperacion, plan.tasa_llegada) == (10, 30)
    assert PlanEstres.desde_entorno({}).escalones == ESCALONES_POR_DEFECTO


@pytest.mark.parametrize("parametros", [
    {"escalones": ()}, {"escalones": (100, 0)}, {"escalones": (300, 100)},
    {"duracion_s": 0}, {"usuarios_recuperacion": 0}, {"tasa_llegada": 0},
])
def test_plan_rechaza_configuraciones_invalidas(parametros):
    with pytest.raises(ValueError):
        PlanEstres(**parametros)


# ---------------------------------------------------------------- analizador
def muestra(segundo, usuarios, total, fallos, p95, rps=10.0):
    return MuestraHistorial(segundo=1000 + segundo, usuarios=usuarios, rps=rps, p95_ms=p95,
                            total_peticiones=total, total_fallos=fallos)


def historial(p95_400=4000, fallos_400=60, p95_recuperacion=80):
    """100 y 200 usuarios cumplen el SLO; 400 rompe; la recuperación vuelve a cumplir (por defecto)."""
    return [
        muestra(0, 50, 0, 0, None), muestra(5, 100, 100, 0, 90),            # 100 usuarios
        muestra(12, 200, 300, 1, 300), muestra(18, 200, 400, 1, 450),       # 200 usuarios
        muestra(22, 400, 500, 1 + fallos_400 // 2, p95_400),                # 400 usuarios
        muestra(28, 400, 600, 1 + fallos_400, p95_400),
        muestra(35, 20, 700, 1 + fallos_400, p95_recuperacion),             # recuperación
    ]


def test_detecta_punto_de_quiebre_capacidad_segura_y_recuperacion():
    resultado = analizar(historial(), PLAN, Umbral(1000, 1))

    assert [m.peticiones for m in resultado.mediciones] == [100, 300, 200, 100]
    assert resultado.punto_de_quiebre.etapa.usuarios == 400
    assert resultado.punto_de_quiebre.porcentaje_fallos == 30.0
    assert resultado.capacidad_segura.etapa.usuarios == 200
    assert resultado.mediciones[1].p95_ms == 450
    assert resultado.se_recupero is True


def test_sin_punto_de_quiebre_cuando_todo_cumple():
    resultado = analizar(historial(p95_400=600, fallos_400=0), PLAN, Umbral(1000, 1))
    assert resultado.punto_de_quiebre is None
    assert resultado.capacidad_segura.etapa.usuarios == 400
    assert "no se alcanzó" in informe_markdown(resultado)


def test_no_se_recupera_si_la_ultima_etapa_viola_el_slo():
    resultado = analizar(historial(p95_recuperacion=2500), PLAN, Umbral(1000, 1))
    assert resultado.se_recupero is False
    assert "NO volvió a cumplir" in informe_markdown(resultado)


def test_muestras_despues_del_fin_cuentan_como_recuperacion_y_etapas_sin_datos_se_omiten():
    resultado = analizar([muestra(0, 100, 50, 0, 80), muestra(45, 20, 90, 0, 70)], PLAN, Umbral())
    assert [m.etapa.nombre for m in resultado.mediciones] == ["100 usuarios", "recuperación (20)"]


def test_historial_vacio():
    resultado = analizar([], PLAN, Umbral())
    assert resultado.punto_de_quiebre is None
    assert (resultado.capacidad_segura, resultado.se_recupero) == (None, False)
    assert "Sin datos" in informe_markdown(resultado)


def test_etapa_sin_peticiones_o_sin_p95_no_cumple():
    resultado = analizar([muestra(0, 100, 0, 0, None)], PLAN, Umbral())
    medicion = resultado.mediciones[0]
    assert medicion.porcentaje_fallos == 0.0
    assert Umbral().se_cumple(medicion) is False


def test_informe_markdown_tiene_tabla_y_conclusiones():
    texto = informe_markdown(analizar(historial(), PLAN, Umbral(1000, 1)))
    assert "| 400 usuarios | 400 | 200 |" in texto
    assert "**Punto de quiebre:** 400 usuarios" in texto
    assert "**Capacidad segura:** hasta 200 usuarios" in texto
    assert "✅ el sistema volvió" in texto


# ------------------------------------------------------------ CSV y comando
def escribir_csv(directorio: Path) -> Path:
    ruta = directorio / "estres_stats_history.csv"
    filas = [
        "1000,0,,Aggregated,0,0,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,0,0,0,0,0,0,0",
        "1005,100,,Aggregated,20,0,50,50,50,50,60,90,90,90,90,90,90,100,0,50,50,1,90,0",
        "1001,100,GET,/health,5,0,5,5,5,5,5,5,5,5,5,5,5,10,0,5,5,1,5,0",  # filas por endpoint se ignoran
        "1015,200,,Aggregated,30,0,80,80,80,80,90,300,300,300,300,300,300,300,0,80,80,1,300,0",
        "1025,400,,Aggregated,25,10,900,900,900,900,1500,3000,3000,3000,3000,3000,3000,500,80,900,900,1,3000,0",
        "1035,20,,Aggregated,10,0,40,40,40,40,50,70,70,70,70,70,70,600,80,40,40,1,70,0",
    ]
    ruta.write_text(CABECERA + "\n".join(filas) + "\n", encoding="utf-8")
    return ruta


def test_leer_historial_solo_toma_la_fila_agregada_y_ordena_por_tiempo(tmp_path):
    muestras = leer_historial(escribir_csv(tmp_path))
    assert [m.segundo for m in muestras] == [1000, 1005, 1015, 1025, 1035]
    assert muestras[0].p95_ms is None


def test_main_exit_0_si_se_recupera(tmp_path, capsys):
    assert main([str(escribir_csv(tmp_path)), "1000", "1"], directorio_base=tmp_path, plan=PLAN) == 0
    assert "**Punto de quiebre:** 400 usuarios" in capsys.readouterr().out


def test_main_exit_1_si_no_se_recupera(tmp_path):
    assert main([str(escribir_csv(tmp_path)), "50", "1"], directorio_base=tmp_path, plan=PLAN) == 1


@pytest.mark.parametrize("argumentos", [[], ["no-existe.csv"], ["../fuera.csv"]])
def test_main_uso_incorrecto(tmp_path, argumentos):
    assert main(argumentos, directorio_base=tmp_path, plan=PLAN) == 2

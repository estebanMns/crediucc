"""Prueba de ESTRÉS con Locust: sube los usuarios por escalones hasta romper la API.

Usa el mismo comportamiento de usuario que la prueba de carga (EstudianteSolicitante) y una
forma de carga (LoadTestShape) que sigue el plan de load/plan_estres.py.

Uso (headless, la forma controla usuarios y duración: no se pasan -u ni -t):
  locust -f load/estres.py --headless --host http://localhost:8000 \
         --csv estres --html estres.html --exit-code-on-error 0
  python -m load.analizar_estres estres_stats_history.csv
"""
from locust import LoadTestShape
from locustfile import EstudianteSolicitante  # noqa: F401  (Locust descubre la clase de usuario aquí)
from plan_estres import PlanEstres


class EscalonesHastaRomper(LoadTestShape):
    plan = PlanEstres.desde_entorno()

    def tick(self):
        return self.plan.objetivo(self.get_run_time())

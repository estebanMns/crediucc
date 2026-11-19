"""Semana 8: enjambre de usuarios que emula la temporada de matrículas.

Mezcla de tareas 3:1:1 -> consultas frecuentes, solicitudes menos frecuentes.
Uso headless (CI):
  locust -f load/locustfile.py --headless -u 200 -r 20 -t 60s \
         --host http://localhost:8000 --csv reporte_carga
"""
import random

from locust import HttpUser, between, task


class EstudianteSolicitante(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def consultar_estado_servicio(self):
        self.client.get("/health", name="GET /health")

    @task(1)
    def listar_solicitudes(self):
        self.client.get("/api/v1/solicitudes", name="GET /api/v1/solicitudes")

    @task(1)
    def solicitar_credito(self):
        with self.client.post("/api/v1/solicitudes", name="POST /api/v1/solicitudes",
                              catch_response=True, json={
                                  "nombre": "Carga", "email": "carga@example.com",
                                  "edad": random.randint(18, 40),
                                  "score": random.randint(550, 850),
                                  "ingresos": round(random.uniform(1_500_000, 4_000_000)),
                                  "monto": round(random.uniform(100_000, 5_000_000)),
                                  "es_estudiante": random.choice([True, False]),
                              }) as respuesta:
            if respuesta.status_code != 201:
                respuesta.failure(f"Esperado 201, recibido {respuesta.status_code}")

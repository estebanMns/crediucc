"""Semana 10 + 5: prueba de integración API -> S3/SQS (LocalStack).

Verifica que un crédito aprobado deja su expediente en S3 y un evento en SQS.
Se omite si no hay endpoint de nube configurado.
"""
import json
import os

import boto3
import pytest
import requests

AWS_ENDPOINT = os.getenv("AWS_ENDPOINT_URL")
BASE_URL = os.getenv("API_URL", "http://localhost:8000")

pytestmark = pytest.mark.skipif(not AWS_ENDPOINT, reason="Sin AWS_ENDPOINT_URL (LocalStack)")


def _cliente(servicio):
    # Región y credenciales (dummy de LocalStack) llegan por variables de entorno desde docker-compose.
    return boto3.client(servicio, endpoint_url=AWS_ENDPOINT)


def test_aprobacion_publica_expediente_y_evento():
    r = requests.post(f"{BASE_URL}/api/v1/solicitudes", timeout=10, json={
        "nombre": "Integracion", "email": "integracion@example.com", "edad": 30,
        "score": 700, "ingresos": 3_000_000.0, "monto": 2_000_000.0, "es_estudiante": False})
    solicitud = r.json()
    assert solicitud["decision"] == "APROBADO"
    assert solicitud["notificado"] is True

    expediente = _cliente("s3").get_object(Bucket="crediucc-expedientes",
                                           Key=f"solicitudes/{solicitud['id']}.json")
    assert json.loads(expediente["Body"].read())["id"] == solicitud["id"]

    sqs = _cliente("sqs")
    url = sqs.get_queue_url(QueueName="crediucc-notificaciones")["QueueUrl"]
    mensajes = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=2)
    ids = [json.loads(m["Body"])["id"] for m in mensajes.get("Messages", [])]
    assert solicitud["id"] in ids

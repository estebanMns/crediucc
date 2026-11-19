# CrediUCC — Proyecto integrador de Pruebas y Mantenimiento de Software

Sistema de **solicitud y aprobación de microcréditos estudiantiles** que integra lo que se vio en las semanas 1 a 10:
Pytest (AAA, BVA, parametrización), cobertura con Quality Gate, Docker y Docker Compose, pruebas de API con JSON Schema,
CI con GitHub Actions, análisis estático (Ruff y SonarCloud), pruebas de carga con Locust, CD con smoke test y
rollback automático, e IaC con LocalStack (S3 + SQS).

## Arquitectura (capas + SOLID)

```
app/
├── dominio/            Reglas de negocio puras (sin frameworks)
│   ├── modelos.py        Entidades y objetos de valor inmutables (dataclass frozen, StrEnum)
│   ├── errores.py        DominioError → TipoInvalidoError / ValorFueraDeDominioError
│   ├── validacion.py     ValidadorSolicitud (entradas destructivas)
│   ├── reglas.py         ReglaElegibilidad (ABC) → ReglaEdad, ReglaScoreMinimo, ReglaIngresoMinimo
│   ├── tasas.py          PoliticaTasa (ABC) → PoliticaTasaUCC
│   └── evaluador.py      EvaluadorCredito (recibe reglas y política por constructor)
├── aplicacion/
│   ├── puertos.py        Interfaces (Protocol): Repositorio, Publicador, CentralRiesgo, MonitorSalud
│   └── servicio_solicitudes.py   Caso de uso: radicar / obtener / listar
├── infraestructura/    Adaptadores: RepositorioEnMemoria, PublicadorAWS, PublicadorNulo,
│                       CentralRiesgoSimulada, MonitorSaludPorEntorno
├── api/                Adaptador HTTP FastAPI (crear_app = fábrica con dependencias inyectadas)
├── config.py           Configuracion inmutable desde variables de entorno
├── contenedor.py       Raíz de composición (único lugar que conoce las clases concretas)
└── main.py             Punto de entrada ASGI
deploy/deploy.py        PipelineDespliegue, ClienteStaging, RegistroReleases, NotificadorConsola
infra/init_infra.py     AprovisionadorIaC + EstadoDeseado (idempotente)
load/                   locustfile.py (enjambre) + verificar_slo.py (Quality Gate de rendimiento)
tests/unit/             75 pruebas, ~94 % de cobertura de líneas y ramas
tests/api/              Pruebas de caja negra en el contenedor test-runner (JSON Schema + S3/SQS)
```

| Principio | Dónde se aplica |
|---|---|
| **S** — Responsabilidad única | El validador solo valida, cada regla evalúa una condición, el servicio solo orquesta y la API solo traduce HTTP. |
| **O** — Abierto/cerrado | Para crear una regla o política de tasa nueva se agrega una subclase y el evaluador no se toca (ver `test_evaluador_acepta_reglas_nuevas_sin_modificarse`). |
| **L** — Sustitución de Liskov | `PublicadorNulo` ↔ `PublicadorAWS` son intercambiables, y en las pruebas un `NotificadorEspia` sustituye a `NotificadorConsola` sin cambiar el pipeline. |
| **I** — Segregación de interfaces | Hay cuatro puertos pequeños en lugar de una interfaz "Dios". |
| **D** — Inversión de dependencias | El dominio y la aplicación dependen de abstracciones. Las implementaciones concretas se inyectan desde `contenedor.py`. |

## Ejecución local (sin Docker)

```bash
python -m venv venv && source venv/bin/activate      # Windows: .\venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest                                     # unitarias + Quality Gate de cobertura (≥ 80 %)
python -m ruff check .                               # linter
python -m uvicorn app.main:app --port 8000 --reload  # terminal 1: API
```

En otra terminal, inicia el frontend Next.js:

```bash
cd frontend
npm ci
npm run dev
```

La interfaz web queda disponible en **http://localhost:3000/** y la documentación de la API en **http://localhost:8000/docs**. Next.js reenvía las peticiones del frontend a la API; por defecto, esta debe estar en `http://localhost:8000` (se puede cambiar con `API_URL`).

## Entorno completo con Docker Compose (QA y staging)

```bash
docker compose --profile qa up --build --exit-code-from test-runner   # LocalStack + IaC + API + frontend + test-runner
docker compose up -d --build frontend                                  # frontend + API + LocalStack
docker compose down -v                                                 # destruir todo
```

En Docker Compose, el frontend se publica en **http://localhost:3000/**.

## Prueba de carga y SLO

```bash
python -m locust -f load/locustfile.py --headless -u 200 -r 20 -t 60s \
  --host http://localhost:8000 --csv reporte_carga --exit-code-on-error 0
python load/verificar_slo.py reporte_carga_stats.csv 1000 1      # p95 ≤ 1000 ms y fallos ≤ 1 %
```

## Despliegue continuo

```bash
API_SECRET_KEY=xxx VERSION_CANDIDATA=2.0.0 python deploy/deploy.py   # exit 0 = promovido, 1 = rollback
```

En GitHub Actions, el workflow `.github/workflows/cd.yml` corre en cada push a `main` (o a mano desde **Actions → CD → Run workflow**) y encadena tres etapas con `needs:`. Si una falla, las siguientes no se ejecutan:

1. **qa-contrato**: `docker compose --profile qa up` levanta LocalStack, la IaC y la API, y el `test-runner` valida el contrato con JSON Schema (Gate 3).
2. **carga**: Locust con 200 usuarios concurrentes y `verificar_slo.py`. El reporte CSV se publica como *artifact* del workflow, no se versiona.
3. **despliegue**: entorno `produccion`. Levanta la versión candidata en staging y ejecuta `deploy.py` (smoke test → promoción o rollback).

## Análisis con SonarCloud

El workflow `.github/workflows/sonarcloud.yml` ejecuta Ruff, las pruebas Python con cobertura, y lint, type-check y build del frontend en `windows-latest`. Después envía el análisis a SonarCloud en cada push o pull request a `main`, usando la autenticación OIDC de SonarSource. También se puede iniciar manualmente desde **Actions → SonarQube → Run workflow**.

Para usar el análisis desde CI, abre el proyecto en SonarCloud y desactiva **Automatic Analysis** en **Administration → Analysis Method**. SonarCloud no permite combinar el análisis automático con el escaneo de GitHub Actions. Las claves del proyecto están configuradas en `sonar-project.properties` como `estebanmns` y `estebanMns_crediucc`.

## Secretos de GitHub requeridos

`API_SECRET_KEY` se usa en el despliegue (`cd.yml`) y se imprime enmascarado. El análisis SonarCloud usa autenticación OIDC desde GitHub Actions. Si creas el entorno `produccion` con *Required reviewers*, el pipeline pasa de Continuous Deployment a Continuous Delivery.

## Inyección de fallas (demostración de los Quality Gates)

| Falla | Cómo inyectarla | Gate que la detiene |
|---|---|---|
| Off-by-one | En `reglas.py`, cambiar `>=` por `>` en `ReglaScoreMinimo` | Gate 1: la prueba BVA con score 600 falla |
| Contrato roto | En `modelos.a_dict`, renombrar `tasa_mensual` a `tasaMensual` | Gate 3: `ValidationError` de JSON Schema |
| Pruebas eliminadas | Borrar archivos de `tests/unit` | Gate 1: la cobertura cae por debajo del 80 % |
| Secreto en el código | Escribir un token en cualquier `.py` | Gate 2: SonarCloud |
| Cuello de botella | `CENTRAL_RIESGO_LATENCIA_MS=1200` | Gate de carga: el p95 viola el SLO |
| Staging enfermo | `APP_HEALTHY=false` | CD: el smoke test falla y hay rollback automático (exit code 1) |

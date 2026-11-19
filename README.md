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
│   ├── identidad.py      Usuario, Sesion y el puerto ProveedorIdentidad (login)
│   └── servicio_solicitudes.py   Caso de uso: radicar / obtener / listar (por usuario)
├── infraestructura/    Adaptadores: RepositorioEnMemoria, RepositorioPostgres (Supabase),
│                       ProveedorSupabase / ProveedorDeshabilitado (login), PublicadorAWS,
│                       PublicadorNulo, CentralRiesgoSimulada, MonitorSaludPorEntorno
├── api/                Adaptador HTTP FastAPI (crear_app = fábrica con dependencias inyectadas)
├── config.py           Configuracion inmutable desde variables de entorno
├── contenedor.py       Raíz de composición (único lugar que conoce las clases concretas)
└── main.py             Punto de entrada ASGI (lee el .env en local)
db/                     001_crear_solicitudes.sql y 002_crear_perfiles.sql: esquema en Supabase con RLS
deploy/deploy.py        PipelineDespliegue, ClienteStaging, RegistroReleases, NotificadorConsola
infra/init_infra.py     AprovisionadorIaC + EstadoDeseado (idempotente)
load/                   locustfile.py (enjambre) + verificar_slo.py (Quality Gate de rendimiento)
tests/unit/             125 pruebas, ~96 % de cobertura de líneas y ramas
tests/api/              Pruebas de caja negra en el contenedor test-runner (JSON Schema + S3/SQS)
```

| Principio | Dónde se aplica |
|---|---|
| **S** — Responsabilidad única | El validador solo valida, cada regla evalúa una condición, el servicio solo orquesta y la API solo traduce HTTP. |
| **O** — Abierto/cerrado | Para crear una regla o política de tasa nueva se agrega una subclase y el evaluador no se toca (ver `test_evaluador_acepta_reglas_nuevas_sin_modificarse`). |
| **L** — Sustitución de Liskov | `RepositorioEnMemoria` ↔ `RepositorioPostgres` y `PublicadorNulo` ↔ `PublicadorAWS` son intercambiables, y en las pruebas un `NotificadorEspia` sustituye a `NotificadorConsola` sin cambiar el pipeline. |
| **I** — Segregación de interfaces | Hay cuatro puertos pequeños en lugar de una interfaz "Dios". |
| **D** — Inversión de dependencias | El dominio y la aplicación dependen de abstracciones. Las implementaciones concretas se inyectan desde `contenedor.py`. |

## Base de datos y login con Supabase

La API funciona en dos modos, según las variables del archivo `.env` (plantilla en `.env.example`):

| Variables | Dónde se guardan las solicitudes | Login |
|---|---|---|
| Ninguna (pruebas, CI, Docker Compose) | En memoria | No: modo anónimo |
| `DATABASE_URL` | Tabla `solicitudes` de Supabase (PostgreSQL) | — |
| `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` | — | Sí: registro e ingreso con Supabase Auth; cada usuario ve solo sus solicitudes |

Puesta en marcha (una sola vez):

1. En Supabase → **SQL Editor** → ejecuta, en orden, `db/001_crear_solicitudes.sql` y `db/002_crear_perfiles.sql`.
2. **Backend:** copia `.env.example` como `.env` (raíz) y llena `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` y
   `DATABASE_URL` (botón **Connect** → **Session pooler**).
3. **Frontend:** copia `frontend/.env.example` como `frontend/.env.local`; `API_URL` indica dónde está la API
   (por defecto `http://127.0.0.1:8001`). Ambos archivos están en `.gitignore`: nunca se suben.
4. Para la demo, en **Authentication → Sign In / Providers → Email** puedes desactivar *Confirm email*;
   si lo dejas activo, cada usuario debe confirmar su correo antes de ingresar (por eso el ingreso responde 401).

Registro: nombre completo (nombre y apellido, solo letras), edad (16 a 100), semestre (1 a 12), correo válido y
contraseña de 8 a 72 caracteres con letras y números, sin espacios. Se valida en el navegador y otra vez en la API
(`app/api/esquemas.py`), que es la validación que cuenta. El perfil se guarda en la tabla `perfiles`.

Endpoints de acceso: `POST /api/v1/auth/registro`, `POST /api/v1/auth/ingreso` y `GET /api/v1/auth/yo`.
Las contraseñas las guarda y cifra Supabase Auth; la API solo verifica el token de cada petición.

## Ejecución local (sin Docker)

```bash
python -m venv venv && source venv/bin/activate      # Windows: .\venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest                                     # unitarias + Quality Gate de cobertura (≥ 80 %)
python -m ruff check .                               # linter
python -m uvicorn app.main:app --port 8001 --reload  # terminal 1: API
```

En otra terminal, inicia el frontend Next.js:

```bash
cd frontend
npm ci
npm run dev
```

También se puede abrir desde la IP de la red local (la URL "Network" que muestra `npm run dev`, por ejemplo desde el celular); eso funciona gracias a `allowedDevOrigins` en `frontend/next.config.ts`.

La interfaz web queda disponible en **http://localhost:3000/** y la documentación de la API en **http://localhost:8001/docs**. Next.js reenvía las peticiones del frontend a la API; por defecto, esta debe estar en `http://localhost:8001` (se puede cambiar con `API_URL`).

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

## Prueba de estrés (punto de quiebre)

La prueba de **carga** confirma que el sistema aguanta el tráfico esperado (200 usuarios fijos). La de **estrés**
busca dónde se rompe: sube por escalones de 100, 250, 500, 750 y 1.000 usuarios (un minuto cada uno) y luego baja a
50 usuarios para comprobar que el sistema **se recupera**.

```bash
python -m locust -f load/estres.py --headless --host http://localhost:8000 \
  --csv estres --html estres.html --exit-code-on-error 0       # la forma de carga controla usuarios y tiempo
python -m load.analizar_estres estres_stats_history.csv 1000 1  # punto de quiebre + recuperación
```

- `load/plan_estres.py`: escalones configurables con `ESTRES_ESCALONES`, `ESTRES_DURACION_S`,
  `ESTRES_USUARIOS_RECUPERACION` y `ESTRES_TASA_LLEGADA`.
- `load/analizar_estres.py`: informa por escalón (peticiones, RPS, p95 y fallos), el **punto de quiebre** (primer
  escalón que viola el SLO), la **capacidad segura** y la **recuperación**. Encontrar el quiebre no es un fallo: el
  comando termina con error solo si el sistema no vuelve a cumplir el SLO al bajar la carga.
- En GitHub: **Actions → Prueba de estrés → Run workflow** (`.github/workflows/estres.yml`). Se ejecuta a mano porque
  tarda unos 6 minutos. El informe aparece en el resumen de la ejecución, y el CSV y el HTML de Locust se publican
  como artifact `reporte-estres`.
- Para la demo, ejecútalo con `latencia_central_ms = 1200`: el quiebre aparece desde el primer escalón.

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
| Cuello de botella | `CENTRAL_RIESGO_LATENCIA_MS=1200` | Gate de carga: el p95 viola el SLO; en la prueba de estrés, quiebre desde el primer escalón |
| Staging enfermo | `APP_HEALTHY=false` | CD: el smoke test falla y hay rollback automático (exit code 1) |

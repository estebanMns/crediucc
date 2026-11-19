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
tests/unit/             162 pruebas, ~98 % de cobertura de líneas y ramas
tests/api/              Pruebas de caja negra en el contenedor test-runner (JSON Schema + S3/SQS)
```

| Principio | Dónde se aplica |
|---|---|
| **S** — Responsabilidad única | El validador solo valida, cada regla evalúa una condición, el servicio solo orquesta y la API solo traduce HTTP. |
| **O** — Abierto/cerrado | Para crear una regla o política de tasa nueva se agrega una subclase y el evaluador no se toca (ver `test_evaluador_acepta_reglas_nuevas_sin_modificarse`). |
| **L** — Sustitución de Liskov | `RepositorioEnMemoria` ↔ `RepositorioPostgres` y `PublicadorNulo` ↔ `PublicadorAWS` son intercambiables, y en las pruebas un `NotificadorEspia` sustituye a `NotificadorConsola` sin cambiar el pipeline. |
| **I** — Segregación de interfaces | Hay cuatro puertos pequeños en lugar de una interfaz "Dios". |
| **D** — Inversión de dependencias | El dominio y la aplicación dependen de abstracciones. Las implementaciones concretas se inyectan desde `contenedor.py`. |

## Instalación y puesta en marcha

### Requisitos previos

| Herramienta | Versión | Comprobar con | Para qué |
|---|---|---|---|
| Git | cualquiera reciente | `git --version` | Descargar el proyecto |
| Python | **3.11** | `python --version` | API, pruebas, Locust, despliegue |
| Node.js | **20.9 o superior** (CI usa 24) | `node --version` | Frontend Next.js |
| Docker Desktop | con Docker Compose v2 | `docker compose version` | Solo para la opción B y las pruebas en contenedor |
| Cuenta de Supabase | plan gratuito | — | Solo si quieres login y base de datos (opción A completa) |

> En Windows usa siempre `python -m ...` (por ejemplo `python -m pytest`) para evitar el error
> *"no se reconoce como comando"* (PATH), como se explica en la Semana 2.

### Paso 1. Descargar el proyecto

```bash
git clone https://github.com/estebanMns/crediucc.git
cd crediucc
```

La aplicación se puede ejecutar de dos formas:

| | Opción A: local (recomendada para la demo) | Opción B: Docker Compose |
|---|---|---|
| Qué levanta | API (uvicorn) + frontend (Next.js) | LocalStack (S3 + SQS) + IaC + API + frontend |
| Login y base de datos | Sí, con Supabase (o modo memoria sin login) | No: modo memoria, sin login |
| Puertos | API **8001**, web **3000** | API **8000**, web **3000**, LocalStack **4566** |

### Opción A — Ejecución local

#### A1. Backend (API FastAPI)

```bash
python -m venv .venv
# Windows (PowerShell):  .\.venv\Scripts\activate
# Linux / macOS:         source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

#### A2. Base de datos y login con Supabase (opcional, una sola vez)

Si te saltas este paso, la API funciona en **modo memoria**: sin login, y las solicitudes se borran al reiniciarla.

1. Crea un proyecto en [supabase.com](https://supabase.com).
2. En **SQL Editor** ejecuta, **en este orden**, el contenido de `db/001_crear_solicitudes.sql` y
   `db/002_crear_perfiles.sql`. Debe aparecer *Success*.
3. Copia la plantilla de variables y llénala con los datos de tu proyecto:

   ```bash
   cp .env.example .env          # Windows (PowerShell): Copy-Item .env.example .env
   ```

   | Variable | Dónde se obtiene en Supabase |
   |---|---|
   | `SUPABASE_URL` | **Project Settings → Data API** → Project URL |
   | `SUPABASE_PUBLISHABLE_KEY` | **Project Settings → API Keys** → llave *publishable* (o *anon*). **Nunca** la *secret / service_role* |
   | `DATABASE_URL` | Botón **Connect** → **Session pooler** (funciona en redes IPv4). Reemplaza `[YOUR-PASSWORD]` por la contraseña de la base |

4. Para la demo, en **Authentication → Sign In / Providers → Email** desactiva **Confirm email**. Si lo dejas
   activo, cada usuario debe confirmar su correo antes de ingresar, y Supabase limita cuántos correos envía por hora.

El archivo `.env` está en `.gitignore`: **nunca se sube a GitHub**.

| Variables presentes en `.env` | Solicitudes | Login |
|---|---|---|
| Ninguna | En memoria | No |
| `DATABASE_URL` | Tabla `solicitudes` de Supabase (PostgreSQL) | — |
| `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` | — | Sí: cada usuario ve solo sus solicitudes |

#### A3. Iniciar la API (terminal 1)

```bash
python -m uvicorn app.main:app --port 8001 --reload
```

Comprueba en el navegador **http://localhost:8001/health**. Debe responder
`{"status":"healthy", ..., "login": true}` (`login: false` si no configuraste Supabase).
La documentación interactiva está en **http://localhost:8001/docs**.

#### A4. Frontend (terminal 2)

```bash
cd frontend
cp .env.example .env.local     # Windows (PowerShell): Copy-Item .env.example .env.local
npm ci
npm run dev
```

`frontend/.env.local` solo contiene `API_URL=http://127.0.0.1:8001`, que indica dónde está la API. Next.js
reenvía `/api/*` y `/health` a esa dirección, así que el navegador no necesita CORS ni ve las llaves.

Abre **http://localhost:3000/**. También funciona desde otro dispositivo de la misma red con la URL *Network* que
muestra `npm run dev`, gracias a `allowedDevOrigins` en `frontend/next.config.ts`.

#### A5. Comprobar que todo funciona

1. **Crear cuenta:** nombre y apellido (solo letras), edad (16 a 100), semestre (1 a 12), correo y una
   contraseña de 8 a 72 caracteres con letras y números, sin espacios. El ojo del campo muestra u oculta la contraseña.
2. Al ingresar, el encabezado dice **"Hola, {tu nombre}"**. El círculo con tus iniciales abre el perfil, y desde ahí
   puedes **cerrar sesión**.
3. **Nueva solicitud:** escribe montos en pesos colombianos (por ejemplo `2.000.000`). Debe aprobarse si la edad está
   entre 18 y 65, el puntaje crediticio es de 600 o más y los ingresos son de $2.000.000 COP o más.
4. **Mis solicitudes** muestra lo que enviaste; **Resumen** muestra los totales.
5. Si usas Supabase, en **Table Editor** verás la fila nueva en `solicitudes` y tu perfil en `perfiles`.

Las validaciones del registro se hacen en el navegador y otra vez en la API (`app/api/esquemas.py`), que es la que
cuenta. Supabase Auth guarda y cifra las contraseñas. La sesión viaja en un token JWT dentro de una cookie
`HttpOnly` y `SameSite=Strict`, que el código de la página no puede leer. Endpoints de acceso:
`POST /api/v1/auth/registro`, `POST /api/v1/auth/ingreso`, `POST /api/v1/auth/salida` y `GET /api/v1/auth/yo`.

### Opción B — Entorno completo con Docker Compose (QA y staging)

Abre Docker Desktop y espera a que el motor esté en verde.

```bash
docker compose --profile qa up --build --exit-code-from test-runner   # LocalStack + IaC + API + test-runner (pruebas de contrato)
docker compose up -d --build frontend                                  # frontend + API + LocalStack para usar la app
docker compose ps                                                      # todos deben estar "healthy"
docker compose down -v                                                 # destruir todo
```

El primer comando termina con `exit code 0` si pasan todas las pruebas de contrato. Con el segundo, la web queda en
**http://localhost:3000/** y la API en **http://localhost:8000/docs**. Este modo no usa Supabase: no tiene login y
guarda las solicitudes en memoria.

### Ejecutar las pruebas

```bash
# Backend (desde la raíz, con el entorno virtual activo)
python -m pytest                       # 162 pruebas unitarias + Quality Gate de cobertura (≥ 80 %)
python -m pytest --cov-report=html     # reporte visual en htmlcov/index.html
python -m ruff check .                 # linter

# Frontend
cd frontend
npm run lint
npm run typecheck
npm test                               # 44 pruebas con Vitest
npm run build
```

### Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `[Errno 10048]` o *address already in use* al iniciar la API | El puerto está ocupado (Docker Desktop suele usar el 8000) | Usa `--port 8001` como en el paso A3, o cierra el proceso que lo ocupa |
| La web dice **"Sin conexión"** | La API no está corriendo, o `API_URL` apunta a otro puerto | Inicia la API (A3) y revisa `frontend/.env.local`; reinicia `npm run dev` |
| Se queda en **"Conectando con CrediUCC..."** al abrirla por IP | Next.js bloquea orígenes que no estén permitidos | La IP debe ser `192.168.x.x` (ya permitida); recarga con Ctrl + F5 |
| `failed to resolve host db.xxxx.supabase.co` | La conexión *Direct* de Supabase solo funciona por IPv6 | En `DATABASE_URL` usa la cadena del **Session pooler** |
| El ingreso responde **401** justo después de registrarte | *Confirm email* está activo | Confirma el correo, o desactívalo (paso A2.4) |
| *"Se enviaron demasiados correos"* | Límite de correos de Supabase | Desactiva *Confirm email* o espera una hora |
| `pytest` / `uvicorn` *no se reconoce como comando* | PATH de Windows | Usa `python -m pytest`, `python -m uvicorn` y activa el `.venv` |
| `docker: error during connect` | Docker Desktop está cerrado | Ábrelo y espera a que el motor arranque |

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

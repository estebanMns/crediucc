-- CrediUCC: esquema de la base de datos en Supabase (PostgreSQL).
-- Cómo aplicarlo: Supabase -> SQL Editor -> New query -> pegar este archivo -> Run.
-- Es idempotente: se puede ejecutar más de una vez sin error.

create table if not exists public.solicitudes (
    id            bigint generated always as identity primary key,
    -- Dueño de la solicitud (usuario de Supabase Auth). NULL = creada en modo sin login.
    usuario_id    uuid references auth.users (id) on delete cascade,
    nombre        text           not null check (char_length(nombre) between 1 and 120),
    email         text           not null check (char_length(email) between 3 and 254),
    edad          integer        not null check (edad between 0 and 120),
    score         integer        not null check (score between 300 and 850),
    ingresos      numeric(14, 2) not null check (ingresos >= 0),
    monto         numeric(14, 2) not null check (monto between 100000 and 5000000),
    es_estudiante boolean        not null default false,
    decision      text           not null check (decision in ('APROBADO', 'RECHAZADO')),
    motivo        text           not null check (motivo in ('CUMPLE_POLITICA', 'EDAD_FUERA_DE_RANGO',
                                                            'SCORE_INSUFICIENTE', 'INGRESOS_INSUFICIENTES')),
    tasa_mensual  numeric(5, 2),
    notificado    boolean        not null default false,
    creado_en     timestamptz    not null default now()
);

comment on table public.solicitudes is 'Solicitudes de microcrédito evaluadas por la API de CrediUCC';

-- "Mis solicitudes" filtra siempre por usuario y ordena por id.
create index if not exists solicitudes_usuario_id_idx on public.solicitudes (usuario_id, id);

-- Seguridad a nivel de fila (RLS): si alguien usa la API pública de Supabase con la llave
-- publishable, solo puede LEER sus propias solicitudes y no puede crear, editar ni borrar.
-- La API de CrediUCC escribe con la conexión del servidor (DATABASE_URL), que no pasa por RLS.
alter table public.solicitudes enable row level security;

drop policy if exists "Cada usuario ve solo sus solicitudes" on public.solicitudes;
create policy "Cada usuario ve solo sus solicitudes"
    on public.solicitudes
    for select
    to authenticated
    using ((select auth.uid()) = usuario_id);

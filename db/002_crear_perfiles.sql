-- CrediUCC: perfil de cada estudiante registrado (nombre completo, edad y semestre).
-- Cómo aplicarlo: Supabase -> SQL Editor -> New query -> pegar este archivo -> Run.
-- Es idempotente: se puede ejecutar más de una vez sin error.
--
-- La API envía el perfil a Supabase Auth al registrarse (user_metadata). Este trigger lo copia
-- a la tabla public.perfiles, para verlo y consultarlo como cualquier otra tabla.

create table if not exists public.perfiles (
    id              uuid primary key references auth.users (id) on delete cascade,
    email           text        not null,
    nombre_completo text        not null check (char_length(nombre_completo) between 5 and 120),
    edad            integer     not null check (edad between 16 and 100),
    semestre        integer     not null check (semestre between 1 and 12),
    creado_en       timestamptz not null default now()
);

comment on table public.perfiles is 'Perfil de los estudiantes registrados en CrediUCC';

-- RLS: con la API pública de Supabase cada usuario solo puede leer su propio perfil.
alter table public.perfiles enable row level security;

drop policy if exists "Cada usuario ve solo su perfil" on public.perfiles;
create policy "Cada usuario ve solo su perfil"
    on public.perfiles
    for select
    to authenticated
    using ((select auth.uid()) = id);

-- Copia el perfil al crear el usuario. Solo actúa si el registro trae los datos del perfil
-- (los usuarios creados a mano desde el panel de Supabase no se ven afectados).
create or replace function public.crear_perfil_de_usuario()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if new.raw_user_meta_data ? 'nombre_completo' then
        insert into public.perfiles (id, email, nombre_completo, edad, semestre)
        values (
            new.id,
            new.email,
            new.raw_user_meta_data ->> 'nombre_completo',
            (new.raw_user_meta_data ->> 'edad')::integer,
            (new.raw_user_meta_data ->> 'semestre')::integer
        )
        on conflict (id) do nothing;
    end if;
    return new;
end;
$$;

drop trigger if exists al_crear_usuario_crear_perfil on auth.users;
create trigger al_crear_usuario_crear_perfil
    after insert on auth.users
    for each row execute function public.crear_perfil_de_usuario();

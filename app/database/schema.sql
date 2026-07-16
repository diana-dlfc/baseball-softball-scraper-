-- ============================================================
-- Esquema de la tabla `businesses` (Supabase / PostgreSQL)
-- La tabla ya existe en Supabase; este archivo sirve como
-- documentación y para recrearla desde cero si hiciera falta.
-- ============================================================

create table if not exists businesses (
    id              uuid primary key default gen_random_uuid(),
    place_id        text not null unique,
    source_query    text,
    business_name   text not null,
    google_category text,
    google_maps_url text,
    address         text,
    city            text,
    state           text,
    country         text,
    latitude        float8,
    longitude       float8,
    phone           text,
    email           text,
    website         text,
    facebook        text,
    instagram       text,
    tiktok          text,
    youtube         text,
    category        text,
    indoor          boolean,
    outdoor         boolean,
    baseball        boolean,
    softball        boolean,
    rating          numeric,
    reviews         int4,
    owner           text,
    scraped         boolean,
    status          text,
    error           text,
    last_scraped    timestamptz,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- Índices para las consultas más frecuentes del pipeline
create index if not exists idx_businesses_scraped on businesses (scraped);
create index if not exists idx_businesses_status  on businesses (status);
create index if not exists idx_businesses_state   on businesses (state);

-- Seguridad: RLS activado sin políticas.
-- La anon key no puede leer ni escribir; el scraper usa la
-- service_role key, que ignora RLS.
alter table businesses enable row level security;

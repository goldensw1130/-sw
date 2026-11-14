begin;
create table if not exists public.oreummok_server_state (
 id text primary key check (id = 'main'),
 revision bigint not null default 1 check (revision > 0),
 payload jsonb not null default '{}'::jsonb,
 updated_at timestamptz not null default now()
);
alter table public.oreummok_server_state enable row level security;
revoke all on table public.oreummok_server_state from public, anon, authenticated;
grant select, insert, update on table public.oreummok_server_state to service_role;
commit;

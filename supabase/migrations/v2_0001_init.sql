create extension if not exists "pgcrypto";

create table if not exists org (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);


create table if not exists org_user (
  org_id uuid not null references org(id) on delete cascade,
  user_id uuid not null,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);


create table if not exists warehouse (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references org(id) on delete cascade,
  code text not null,
  name text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (org_id, code)
);


create table if not exists warehouse_location (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references org(id) on delete cascade,
  warehouse_id uuid not null references warehouse(id) on delete cascade,
  code text not null,
  name text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (warehouse_id, code)
);


create table if not exists item (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references org(id) on delete cascade,
  sku text not null,
  name text not null,
  item_type text not null, -- 'RM' | 'FG'
  uom text not null default 'PCS',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (org_id, sku)
);


create table if not exists stock_ledger (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references org(id) on delete cascade,
  item_id uuid not null references item(id),
  location_id uuid references warehouse_location(id),
  txn_type text not null, -- 'RECEIPT' | 'ISSUE' | 'ADJ_701' | 'ADJ_702'
  qty numeric(18,6) not null,
  uom text not null default 'PCS',
  ref_type text,
  ref_id uuid,
  note text,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);


create table if not exists inventory_adjustment (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references org(id) on delete cascade,
  adjustment_type text not null, -- '701' | '702'
  status text not null default 'DRAFT', -- DRAFT | APPROVED | VOID
  reason_code text,
  ref_doc text,
  note text,
  approved_by uuid,
  approved_at timestamptz,
  created_at timestamptz not null default now()
);


create table if not exists inventory_adjustment_line (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references org(id) on delete cascade,
  adjustment_id uuid not null references inventory_adjustment(id) on delete cascade,
  item_id uuid not null references item(id),
  location_id uuid references warehouse_location(id),
  qty numeric(18,6) not null,
  note text,
  created_at timestamptz not null default now()
);


alter table inventory_adjustment
  add constraint inventory_adjustment_status_chk
  check (status in ('DRAFT','APPROVED','VOID'));



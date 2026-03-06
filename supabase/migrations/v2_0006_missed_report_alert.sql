create table if not exists public.missed_report_alert (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  work_order_no text not null,
  stage_code text not null,          -- PRE/ASSY/PACK
  hour_start timestamptz not null,
  due_at timestamptz not null,       -- hour_start + 15 minutes
  status text not null default 'OPEN',   -- OPEN / ACK / CLOSED / SKIP
  ack_by text null,
  ack_note text null,
  created_at timestamptz not null default now()
);

create unique index if not exists missed_report_alert_uq
  on public.missed_report_alert (org_id, work_order_no, stage_code, hour_start);

create index if not exists missed_report_alert_org_status_idx
  on public.missed_report_alert (org_id, status, due_at desc);
create table if not exists public.hourly_output_log (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,

  work_order_id uuid null,
  work_order_no text null,

  line_code text null,

  stage_code text not null,               -- PRE / ASSY / PACK（你也可改中文，但建议英文）
  hour_start timestamptz not null,         -- 每小时起始时间（UTC）

  plan_qty numeric not null default 0,
  actual_qty numeric not null default 0,
  scrap_qty numeric not null default 0,
  rework_qty numeric not null default 0,

  -- 关键：解释“前置60，组装80”这种情况
  carry_in_wip_qty numeric not null default 0,  -- 本小时/本班次开始时，该工序可用的上游结转WIP

  reason_code text null,
  note text null,

  skip_escalation boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists hourly_output_log_org_hour_idx
  on public.hourly_output_log (org_id, hour_start desc);

create index if not exists hourly_output_log_org_wo_stage_idx
  on public.hourly_output_log (org_id, work_order_no, stage_code, hour_start desc);
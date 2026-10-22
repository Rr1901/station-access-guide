-- Rail Club Phase 2: visitor video reports.
-- Run once in Supabase (SQL Editor, or `supabase db push`). See docs/phase-2-setup.md.
--
-- Who can do what:
--   * anyone            → read published facts
--   * signed-in visitor → upload a video into their own folder, read their own reports
--   * everything else (deciding, publishing, reviewing) happens in Edge Functions
--     with the service role, never from the browser.

-- ---------- settings and admins ----------

create table public.settings (
  key   text primary key,
  value jsonb not null
);

insert into public.settings (key, value) values ('limits', '{
  "per_user_per_day": 3,
  "per_station_per_day": 20,
  "min_seconds": 15,
  "max_seconds": 60,
  "max_bytes": 12582912,
  "radius_m": 400,
  "radius_overrides_m": {
    "chhatrapati-shivaji-maharaj-terminus": 700, "dadar": 600, "lokmanya-tilak-terminus": 600,
    "thane": 600, "kalyan": 600, "pune": 600, "howrah": 700, "sealdah": 600,
    "ahmedabad": 600, "vadodara": 600, "surat": 600, "nagpur": 600
  },
  "max_accuracy_m": 100,
  "max_upload_age_min": 10,
  "trust_after_approved": 3,
  "distrust_after_rejected": 3,
  "confirmed_reports_needed": 2,
  "confirmed_within_days": 90,
  "pending_keep_days": 14,
  "monthly_gemini_calls": 300
}');

-- Reviewers. Add yours with:  insert into public.admins (email) values ('you@gmail.com');
create table public.admins (
  email text primary key check (email = lower(email))
);

-- ---------- contributors and reports ----------

create table public.contributors (
  user_id        uuid primary key references auth.users on delete cascade,
  approved_count int  not null default 0,
  rejected_count int  not null default 0,
  blocked        boolean not null default false,
  created_at     timestamptz not null default now()
);

create type public.report_status as enum ('rejected', 'not_needed', 'pending', 'published', 'expired');

create table public.reports (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references auth.users on delete cascade,
  station_id         text not null,
  claimed_features   text[] not null,
  lat                double precision,
  lon                double precision,
  accuracy_m         real,
  distance_m         real,
  duration_s         real,
  recorded_at        timestamptz,
  created_at         timestamptz not null default now(),
  consent_version    text not null,
  video_path         text,
  video_sha256       text,
  status             public.report_status not null,
  decided_by         text not null,                -- the gate that decided, 'rules' (after Gemini) or 'admin'
  reasons            text[] not null default '{}',
  gemini             jsonb,
  gemini_model       text,
  prompt_version     text,
  gemini_tokens      int,
  gemini_ms          int,
  suggested_features text[] not null default '{}', -- what Gemini confirmed, for the reviewer
  published_features text[] not null default '{}',
  reviewed_by        text,
  reviewed_at        timestamptz
);

create index reports_user_time    on public.reports (user_id, created_at desc);
create index reports_station_time on public.reports (station_id, created_at desc);
create index reports_status_time  on public.reports (status, created_at);
create unique index reports_video_sha256 on public.reports (video_sha256) where video_sha256 is not null;

-- ---------- published facts (what station pages show) ----------

create table public.facts (
  id         bigint generated always as identity primary key,
  station_id text not null,
  feature    text not null,
  note       text,
  seen_on    date not null,
  report_id  uuid not null references public.reports on delete cascade,
  created_at timestamptz not null default now(),
  unique (report_id, feature)
);

create index facts_station on public.facts (station_id, seen_on desc);

-- ---------- row level security ----------

alter table public.settings     enable row level security;
alter table public.admins       enable row level security;
alter table public.contributors enable row level security;
alter table public.reports      enable row level security;
alter table public.facts        enable row level security;

-- settings and admins: no policies, so only the service role (Edge Functions) can read them.

create policy "facts are public"
  on public.facts for select to anon, authenticated using (true);

create policy "visitors see their own reports"
  on public.reports for select to authenticated using (user_id = (select auth.uid()));

create policy "visitors see their own trust record"
  on public.contributors for select to authenticated using (user_id = (select auth.uid()));

-- ---------- private video bucket ----------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('report-videos', 'report-videos', false, 12582912, array['video/webm', 'video/mp4'])
on conflict (id) do nothing;

-- Visitors may only add files to their own folder (<user id>/<file>), and can't read,
-- overwrite or delete anything; the Edge Functions do that with the service role.
create policy "visitors upload into their own folder"
  on storage.objects for insert to authenticated
  with check (
    bucket_id = 'report-videos'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

-- ---------- helpers for the Edge Functions (service role only) ----------

create function public.bump_contributor(p_user uuid, p_approved int, p_rejected int)
returns void
language sql
security definer
set search_path = ''
as $$
  insert into public.contributors (user_id, approved_count, rejected_count)
  values (p_user, greatest(p_approved, 0), greatest(p_rejected, 0))
  on conflict (user_id) do update
    set approved_count = public.contributors.approved_count + p_approved,
        rejected_count = public.contributors.rejected_count + p_rejected;
$$;

-- Uploaded videos that never got a report (e.g. the visitor closed the page).
create function public.orphan_videos(p_older_than interval)
returns table (name text)
language sql
security definer
set search_path = ''
as $$
  select o.name
  from storage.objects o
  where o.bucket_id = 'report-videos'
    and o.created_at < now() - p_older_than
    and not exists (select 1 from public.reports r where r.video_path = o.name);
$$;

revoke all on function public.bump_contributor(uuid, int, int) from public, anon, authenticated;
revoke all on function public.orphan_videos(interval) from public, anon, authenticated;
grant execute on function public.bump_contributor(uuid, int, int) to service_role;
grant execute on function public.orphan_videos(interval) to service_role;

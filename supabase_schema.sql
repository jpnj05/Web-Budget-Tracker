-- Supabase table schema for Web Budget Tracker

create table users (
  email text primary key,
  budget numeric default 0,
  period text default 'month',
  period_start text,
  savings_goal numeric default 0
);

create table expenses (
  id uuid primary key default gen_random_uuid(),
  user_email text references users(email),
  name text,
  amount numeric,
  category text,
  date text
);

create table history (
  id uuid primary key default gen_random_uuid(),
  user_email text references users(email),
  period text,
  period_start text,
  label text,
  budget numeric,
  savings_goal numeric,
  expenses jsonb,
  archived_at text
);

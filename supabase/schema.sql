-- Fasting Bot — Supabase Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    timezone TEXT DEFAULT 'Europe/Vienna',
    is_premium BOOLEAN DEFAULT FALSE,
    premium_until TIMESTAMPTZ,
    is_admin BOOLEAN DEFAULT FALSE,
    settings JSONB DEFAULT '{}'::jsonb
);

-- ============================================================
-- FASTS
-- ============================================================
CREATE TABLE fasts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_minutes INTEGER,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fasts_user_id ON fasts(user_id);
CREATE INDEX idx_fasts_active ON fasts(user_id, ended_at) WHERE ended_at IS NULL;
CREATE INDEX idx_fasts_started_at ON fasts(started_at DESC);

-- ============================================================
-- DASHBOARD TOKENS (одноразовые ссылки на дашборд)
-- ============================================================
CREATE TABLE dashboard_tokens (
    token UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours'),
    used_at TIMESTAMPTZ
);

CREATE INDEX idx_dashboard_tokens_user ON dashboard_tokens(user_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE fasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_tokens ENABLE ROW LEVEL SECURITY;

-- Пользователи видят только свои фасты
CREATE POLICY fasts_user_select ON fasts
    FOR SELECT USING (user_id = current_setting('app.user_id')::bigint);

CREATE POLICY fasts_user_insert ON fasts
    FOR INSERT WITH CHECK (user_id = current_setting('app.user_id')::bigint);

CREATE POLICY fasts_user_update ON fasts
    FOR UPDATE USING (user_id = current_setting('app.user_id')::bigint);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Активный фаст пользователя (если есть)
CREATE OR REPLACE FUNCTION get_active_fast(p_telegram_id BIGINT)
RETURNS SETOF fasts AS $$
    SELECT * FROM fasts
    WHERE user_id = p_telegram_id AND ended_at IS NULL
    ORDER BY started_at DESC LIMIT 1;
$$ LANGUAGE sql STABLE;

-- Статистика пользователя
CREATE OR REPLACE FUNCTION get_user_stats(p_telegram_id BIGINT)
RETURNS TABLE(
    total_fasts BIGINT,
    total_duration_minutes NUMERIC,
    avg_duration_minutes NUMERIC,
    longest_duration_minutes INTEGER,
    current_streak_days INTEGER,
    current_fasting BOOLEAN,
    current_fasting_minutes INTEGER
) AS $$
DECLARE
    v_active_fast fasts;
BEGIN
    -- Активный фаст
    SELECT * INTO v_active_fast FROM fasts
    WHERE user_id = p_telegram_id AND ended_at IS NULL
    ORDER BY started_at DESC LIMIT 1;

    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT AS total_fasts,
        COALESCE(SUM(duration_minutes), 0)::NUMERIC AS total_duration_minutes,
        COALESCE(AVG(duration_minutes), 0)::NUMERIC(10,1) AS avg_duration_minutes,
        COALESCE(MAX(duration_minutes), 0)::INTEGER AS longest_duration_minutes,
        (SELECT COUNT(*) FROM (
            SELECT DATE(ended_at AT TIME ZONE 'UTC') AS fast_date
            FROM fasts
            WHERE user_id = p_telegram_id AND ended_at IS NOT NULL
            GROUP BY fast_date
            ORDER BY fast_date DESC
        ) AS d WHERE d.fast_date >= CURRENT_DATE - INTERVAL '30 days')::INTEGER AS current_streak_days,
        v_active_fast.id IS NOT NULL AS current_fasting,
        CASE WHEN v_active_fast.id IS NOT NULL
            THEN EXTRACT(EPOCH FROM (NOW() - v_active_fast.started_at)) / 60
            ELSE 0
        END::INTEGER AS current_fasting_minutes
    FROM fasts
    WHERE user_id = p_telegram_id AND ended_at IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

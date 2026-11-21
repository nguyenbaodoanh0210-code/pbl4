-- Base idempotent schema for initializing a fresh PostgreSQL database
-- before applying incremental migrations (20261102_* and later).
BEGIN;

CREATE TABLE IF NOT EXISTS public.users (
    user_id varchar(50) PRIMARY KEY,
    full_name text NOT NULL,
    phone_number text,
    email varchar(254),
    password_hash varchar(255),
    fcm_token text,
    role varchar(30) DEFAULT 'FARMER'
);

CREATE TABLE IF NOT EXISTS public.crops (
    crop_stage_id varchar(50) PRIMARY KEY,
    crop_name text NOT NULL,
    growth_stage text NOT NULL,
    min_temp double precision,
    max_temp double precision,
    min_humidity double precision,
    max_humidity double precision,
    min_soil_moisture double precision,
    optimum_ph double precision,
    target_n double precision,
    target_p double precision,
    target_k double precision
);

CREATE TABLE IF NOT EXISTS public.greenhouses (
    greenhouse_id varchar(50) PRIMARY KEY,
    user_id varchar(50) REFERENCES public.users(user_id) ON DELETE RESTRICT,
    crop_stage_id varchar(50) REFERENCES public.crops(crop_stage_id) ON DELETE SET NULL,
    name varchar(100) NOT NULL,
    area_sqm double precision,
    location varchar(255),
    created_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.devices (
    device_id varchar(50) PRIMARY KEY,
    greenhouse_id varchar(50) REFERENCES public.greenhouses(greenhouse_id) ON DELETE RESTRICT,
    device_type varchar(20) DEFAULT 'SENSOR_NODE',
    is_online boolean DEFAULT FALSE,
    battery_level integer,
    send_interval integer DEFAULT 5,
    last_updated timestamptz,
    status varchar(20) DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS public.sensor_logs (
    log_id varchar(50) PRIMARY KEY,
    device_id varchar(50) REFERENCES public.devices(device_id) ON DELETE CASCADE,
    timestamp timestamptz DEFAULT CURRENT_TIMESTAMP,
    temperature double precision,
    humidity double precision,
    soil_moisture double precision,
    soil_ph double precision,
    n double precision,
    p double precision,
    k double precision
);

CREATE TABLE IF NOT EXISTS public.recommendations (
    rec_id varchar(50) PRIMARY KEY,
    device_id varchar(50) REFERENCES public.devices(device_id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    condition_diagnosis varchar(100),
    fertilizer_action varchar(100),
    dosage double precision,
    action_note text,
    status varchar(20) DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS public.camera_logs (
    log_id varchar(50) PRIMARY KEY,
    device_id varchar(50) REFERENCES public.devices(device_id) ON DELETE SET NULL,
    greenhouse_id varchar(50) REFERENCES public.greenhouses(greenhouse_id) ON DELETE CASCADE,
    image_url text NOT NULL,
    timestamp timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ai_diagnosis text,
    confidence_score double precision,
    status varchar(30) DEFAULT 'NEW'
);

COMMIT;

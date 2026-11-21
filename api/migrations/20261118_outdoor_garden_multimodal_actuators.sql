-- Upgrade schema to 11 tables for Outdoor Garden (Chili & Lettuce),
-- NodeMCU v2.0.0 (DHT22 + LDR Light), ESP32-CAM Multimodal AI, and Pump/Fan Actuators.
BEGIN;

-- 1. users: audit timestamps, active flag, role check
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- 2. crops: outdoor environment presets, light thresholds, fungal-risk rules
ALTER TABLE public.crops
    ADD COLUMN IF NOT EXISTS environment_type varchar(30) NOT NULL DEFAULT 'OUTDOOR',
    ADD COLUMN IF NOT EXISTS min_light double precision,
    ADD COLUMN IF NOT EXISTS max_light double precision,
    ADD COLUMN IF NOT EXISTS fungal_humidity_threshold double precision NOT NULL DEFAULT 85.0,
    ADD COLUMN IF NOT EXISTS fungal_light_threshold double precision,
    ADD COLUMN IF NOT EXISTS fungal_duration_minutes integer NOT NULL DEFAULT 60;

-- 3. greenhouses (outdoor gardens): environment_type and updated_at
ALTER TABLE public.greenhouses
    ADD COLUMN IF NOT EXISTS environment_type varchar(30) NOT NULL DEFAULT 'OUTDOOR',
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- 4. greenhouse_areas (planting zones: Chili / Lettuce): composite unique + custom threshold overrides
ALTER TABLE public.greenhouse_areas
    ADD COLUMN IF NOT EXISTS custom_min_temp double precision,
    ADD COLUMN IF NOT EXISTS custom_max_temp double precision,
    ADD COLUMN IF NOT EXISTS custom_min_humidity double precision,
    ADD COLUMN IF NOT EXISTS custom_max_humidity double precision,
    ADD COLUMN IF NOT EXISTS custom_min_light double precision,
    ADD COLUMN IF NOT EXISTS custom_max_light double precision,
    ADD COLUMN IF NOT EXISTS custom_fungal_humidity_threshold double precision;

DO $mig$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_greenhouse_areas_id_greenhouse'
          AND conrelid = 'public.greenhouse_areas'::regclass
    ) THEN
        ALTER TABLE public.greenhouse_areas
            ADD CONSTRAINT uq_greenhouse_areas_id_greenhouse UNIQUE (area_id, greenhouse_id);
    END IF;
END
$mig$;

-- 5. devices: hardware model + soft-delete timestamp
ALTER TABLE public.devices
    ADD COLUMN IF NOT EXISTS hardware_model varchar(60),
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- 6. sensor_logs: LDR light sensor reading
ALTER TABLE public.sensor_logs
    ADD COLUMN IF NOT EXISTS light_level double precision;

-- 7. camera_logs: ESP32-CAM trigger type, CNN vs Multimodal outputs, env snapshot
ALTER TABLE public.camera_logs
    ADD COLUMN IF NOT EXISTS trigger_type varchar(20) NOT NULL DEFAULT 'MANUAL',
    ADD COLUMN IF NOT EXISTS cnn_diagnosis varchar(120),
    ADD COLUMN IF NOT EXISTS cnn_confidence double precision,
    ADD COLUMN IF NOT EXISTS cnn_scores jsonb,
    ADD COLUMN IF NOT EXISTS multimodal_reason text,
    ADD COLUMN IF NOT EXISTS recommended_action text,
    ADD COLUMN IF NOT EXISTS sensor_log_id varchar(50),
    ADD COLUMN IF NOT EXISTS temperature_at_capture double precision,
    ADD COLUMN IF NOT EXISTS humidity_at_capture double precision,
    ADD COLUMN IF NOT EXISTS light_at_capture double precision,
    ADD COLUMN IF NOT EXISTS env_window_summary jsonb,
    ADD COLUMN IF NOT EXISTS model_version varchar(50);

-- 8. actuator_states (Table #10): current state & control mode for Pump / Fan
CREATE TABLE IF NOT EXISTS public.actuator_states (
    actuator_id varchar(50) PRIMARY KEY,
    greenhouse_id varchar(50) NOT NULL REFERENCES public.greenhouses(greenhouse_id) ON DELETE CASCADE,
    area_id varchar(50) REFERENCES public.greenhouse_areas(area_id) ON DELETE SET NULL,
    device_id varchar(50) REFERENCES public.devices(device_id) ON DELETE SET NULL,
    actuator_type varchar(20) NOT NULL,
    control_mode varchar(20) NOT NULL DEFAULT 'AUTO',
    is_on boolean NOT NULL DEFAULT FALSE,
    auto_rules jsonb,
    last_changed_by varchar(30) NOT NULL DEFAULT 'AUTO_RULE',
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_actuator_states_type CHECK (actuator_type IN ('PUMP', 'FAN')),
    CONSTRAINT ck_actuator_states_mode CHECK (control_mode IN ('MANUAL', 'AUTO')),
    CONSTRAINT ck_actuator_states_changed_by CHECK (last_changed_by IN ('USER', 'AUTO_RULE', 'AI')),
    CONSTRAINT fk_actuator_states_area_greenhouse
        FOREIGN KEY (area_id, greenhouse_id)
        REFERENCES public.greenhouse_areas(area_id, greenhouse_id)
        ON DELETE NO ACTION
);

-- 9. actuator_logs (Table #11): audit trail for Pump / Fan commands
CREATE TABLE IF NOT EXISTS public.actuator_logs (
    log_id varchar(50) PRIMARY KEY,
    actuator_id varchar(50) NOT NULL REFERENCES public.actuator_states(actuator_id) ON DELETE CASCADE,
    user_id varchar(50) REFERENCES public.users(user_id) ON DELETE SET NULL,
    action varchar(20) NOT NULL,
    trigger_source varchar(20) NOT NULL,
    reason text,
    ack_status varchar(20) NOT NULL DEFAULT 'PENDING',
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_actuator_logs_action CHECK (action IN ('TURN_ON', 'TURN_OFF', 'MODE_CHANGE')),
    CONSTRAINT ck_actuator_logs_trigger_source CHECK (trigger_source IN ('MANUAL', 'AUTO_RULE', 'AI_ALERT')),
    CONSTRAINT ck_actuator_logs_ack_status CHECK (ack_status IN ('PENDING', 'ACK', 'FAILED'))
);

-- 10. recommendations: link to camera_logs & source type
ALTER TABLE public.recommendations
    ADD COLUMN IF NOT EXISTS camera_log_id varchar(50),
    ADD COLUMN IF NOT EXISTS source_type varchar(20) NOT NULL DEFAULT 'SENSOR_ONLY';

-- Widen recommendation text columns if needed for Vietnamese multimodal diagnoses
ALTER TABLE public.recommendations
    ALTER COLUMN condition_diagnosis TYPE varchar(255),
    ALTER COLUMN fertilizer_action TYPE text;

-- 11. Constraints & cross-table FKs (idempotent)
DO $mig$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role_values' AND conrelid = 'public.users'::regclass) THEN
        ALTER TABLE public.users ADD CONSTRAINT ck_users_role_values CHECK (role IS NULL OR role IN ('FARMER', 'ADMIN'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_crops_environment_type' AND conrelid = 'public.crops'::regclass) THEN
        ALTER TABLE public.crops ADD CONSTRAINT ck_crops_environment_type CHECK (environment_type IN ('OUTDOOR', 'GREENHOUSE'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_crops_temp_range' AND conrelid = 'public.crops'::regclass) THEN
        ALTER TABLE public.crops ADD CONSTRAINT ck_crops_temp_range CHECK (min_temp IS NULL OR max_temp IS NULL OR min_temp <= max_temp);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_crops_humidity_range' AND conrelid = 'public.crops'::regclass) THEN
        ALTER TABLE public.crops ADD CONSTRAINT ck_crops_humidity_range CHECK (min_humidity IS NULL OR max_humidity IS NULL OR min_humidity <= max_humidity);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_crops_light_range' AND conrelid = 'public.crops'::regclass) THEN
        ALTER TABLE public.crops ADD CONSTRAINT ck_crops_light_range CHECK ((min_light IS NULL OR min_light >= 0) AND (max_light IS NULL OR max_light >= 0) AND (min_light IS NULL OR max_light IS NULL OR min_light <= max_light));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_crops_fungal_humidity' AND conrelid = 'public.crops'::regclass) THEN
        ALTER TABLE public.crops ADD CONSTRAINT ck_crops_fungal_humidity CHECK (fungal_humidity_threshold BETWEEN 0 AND 100);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_crops_fungal_duration' AND conrelid = 'public.crops'::regclass) THEN
        ALTER TABLE public.crops ADD CONSTRAINT ck_crops_fungal_duration CHECK (fungal_duration_minutes > 0);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_greenhouses_environment_type' AND conrelid = 'public.greenhouses'::regclass) THEN
        ALTER TABLE public.greenhouses ADD CONSTRAINT ck_greenhouses_environment_type CHECK (environment_type IN ('OUTDOOR', 'GREENHOUSE'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_areas_custom_temp_range' AND conrelid = 'public.greenhouse_areas'::regclass) THEN
        ALTER TABLE public.greenhouse_areas ADD CONSTRAINT ck_areas_custom_temp_range CHECK (custom_min_temp IS NULL OR custom_max_temp IS NULL OR custom_min_temp <= custom_max_temp);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_areas_custom_humidity_range' AND conrelid = 'public.greenhouse_areas'::regclass) THEN
        ALTER TABLE public.greenhouse_areas ADD CONSTRAINT ck_areas_custom_humidity_range CHECK ((custom_min_humidity IS NULL OR custom_min_humidity BETWEEN 0 AND 100) AND (custom_max_humidity IS NULL OR custom_max_humidity BETWEEN 0 AND 100) AND (custom_min_humidity IS NULL OR custom_max_humidity IS NULL OR custom_min_humidity <= custom_max_humidity));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_areas_custom_light_range' AND conrelid = 'public.greenhouse_areas'::regclass) THEN
        ALTER TABLE public.greenhouse_areas ADD CONSTRAINT ck_areas_custom_light_range CHECK ((custom_min_light IS NULL OR custom_min_light >= 0) AND (custom_max_light IS NULL OR custom_max_light >= 0) AND (custom_min_light IS NULL OR custom_max_light IS NULL OR custom_min_light <= custom_max_light));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_areas_custom_fungal_humidity' AND conrelid = 'public.greenhouse_areas'::regclass) THEN
        ALTER TABLE public.greenhouse_areas ADD CONSTRAINT ck_areas_custom_fungal_humidity CHECK (custom_fungal_humidity_threshold IS NULL OR custom_fungal_humidity_threshold BETWEEN 0 AND 100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_devices_type_values' AND conrelid = 'public.devices'::regclass) THEN
        ALTER TABLE public.devices ADD CONSTRAINT ck_devices_type_values CHECK (device_type IN ('SENSOR_NODE', 'CAMERA_NODE', 'CAMERA', 'ACTUATOR'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_devices_status_values' AND conrelid = 'public.devices'::regclass) THEN
        ALTER TABLE public.devices ADD CONSTRAINT ck_devices_status_values CHECK (status IS NULL OR status IN ('ACTIVE', 'INACTIVE', 'ERROR', 'RETIRED'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_devices_area_greenhouse' AND conrelid = 'public.devices'::regclass) THEN
        ALTER TABLE public.devices ADD CONSTRAINT fk_devices_area_greenhouse FOREIGN KEY (area_id, greenhouse_id) REFERENCES public.greenhouse_areas(area_id, greenhouse_id) ON DELETE NO ACTION;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_sensor_light_range' AND conrelid = 'public.sensor_logs'::regclass) THEN
        ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_light_range CHECK (light_level IS NULL OR light_level >= 0);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_camera_logs_trigger_type' AND conrelid = 'public.camera_logs'::regclass) THEN
        ALTER TABLE public.camera_logs ADD CONSTRAINT ck_camera_logs_trigger_type CHECK (trigger_type IN ('MANUAL', 'SCHEDULED', 'ENV_ALERT'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_camera_logs_cnn_confidence' AND conrelid = 'public.camera_logs'::regclass) THEN
        ALTER TABLE public.camera_logs ADD CONSTRAINT ck_camera_logs_cnn_confidence CHECK (cnn_confidence IS NULL OR cnn_confidence BETWEEN 0 AND 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_camera_logs_confidence_score' AND conrelid = 'public.camera_logs'::regclass) THEN
        ALTER TABLE public.camera_logs ADD CONSTRAINT ck_camera_logs_confidence_score CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_camera_logs_status' AND conrelid = 'public.camera_logs'::regclass) THEN
        ALTER TABLE public.camera_logs ADD CONSTRAINT ck_camera_logs_status CHECK (status IS NULL OR status IN ('NEW', 'REVIEWED', 'RESOLVED'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_camera_logs_sensor_log' AND conrelid = 'public.camera_logs'::regclass) THEN
        ALTER TABLE public.camera_logs ADD CONSTRAINT fk_camera_logs_sensor_log FOREIGN KEY (sensor_log_id) REFERENCES public.sensor_logs(log_id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_camera_logs_area_greenhouse' AND conrelid = 'public.camera_logs'::regclass) THEN
        ALTER TABLE public.camera_logs ADD CONSTRAINT fk_camera_logs_area_greenhouse FOREIGN KEY (area_id, greenhouse_id) REFERENCES public.greenhouse_areas(area_id, greenhouse_id) ON DELETE NO ACTION;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_recommendations_camera_log' AND conrelid = 'public.recommendations'::regclass) THEN
        ALTER TABLE public.recommendations ADD CONSTRAINT fk_recommendations_camera_log FOREIGN KEY (camera_log_id) REFERENCES public.camera_logs(log_id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_recommendations_source_type' AND conrelid = 'public.recommendations'::regclass) THEN
        ALTER TABLE public.recommendations ADD CONSTRAINT ck_recommendations_source_type CHECK (source_type IN ('SENSOR_ONLY', 'CAMERA_CNN', 'MULTIMODAL'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_notifications_category' AND conrelid = 'public.notifications'::regclass) THEN
        ALTER TABLE public.notifications ADD CONSTRAINT ck_notifications_category CHECK (category IN ('ENV_ALERT', 'DISEASE_ALERT', 'DEVICE_OFFLINE', 'ACTUATOR_EVENT', 'RECOMMENDATION', 'DEMO_ENVIRONMENT'));
    END IF;
END
$mig$;

-- 12. Performance & Uniqueness Indexes
CREATE INDEX IF NOT EXISTS ix_sensor_logs_device_ts_desc
    ON public.sensor_logs (device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_devices_active_greenhouse
    ON public.devices (greenhouse_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_camera_logs_device_ts_desc
    ON public.camera_logs (device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_camera_logs_status_ts_desc
    ON public.camera_logs (status, timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_recommendations_camera_log
    ON public.recommendations (camera_log_id);

CREATE INDEX IF NOT EXISTS ix_notifications_greenhouse_created
    ON public.notifications (greenhouse_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_actuator_states_greenhouse
    ON public.actuator_states (greenhouse_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_actuator_states_gh_type_no_area
    ON public.actuator_states (greenhouse_id, actuator_type)
    WHERE area_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_actuator_states_area_type
    ON public.actuator_states (area_id, actuator_type)
    WHERE area_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_actuator_logs_actuator_created
    ON public.actuator_logs (actuator_id, created_at DESC);

COMMIT;

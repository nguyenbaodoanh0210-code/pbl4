BEGIN;
CREATE TABLE IF NOT EXISTS public.greenhouse_areas (
 area_id varchar(50) PRIMARY KEY,
 greenhouse_id varchar(50) NOT NULL REFERENCES public.greenhouses(greenhouse_id) ON DELETE RESTRICT,
 crop_stage_id varchar(50) REFERENCES public.crops(crop_stage_id) ON DELETE SET NULL,
 name varchar(100) NOT NULL,
 area_sqm double precision NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_greenhouse_areas_name UNIQUE (greenhouse_id, name),
 CONSTRAINT ck_greenhouse_areas_area_positive CHECK (area_sqm > 0)
);
ALTER TABLE public.devices ADD COLUMN IF NOT EXISTS area_id varchar(50);
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS area_id varchar(50);
ALTER TABLE public.camera_logs ADD COLUMN IF NOT EXISTS area_id varchar(50);
CREATE TABLE IF NOT EXISTS public.notifications (
 notification_id varchar(50) PRIMARY KEY,
 user_id varchar(50) REFERENCES public.users(user_id) ON DELETE SET NULL,
 greenhouse_id varchar(50) REFERENCES public.greenhouses(greenhouse_id) ON DELETE SET NULL,
 area_id varchar(50) REFERENCES public.greenhouse_areas(area_id) ON DELETE SET NULL,
 device_id varchar(50) REFERENCES public.devices(device_id) ON DELETE SET NULL,
 recommendation_id varchar(50) REFERENCES public.recommendations(rec_id) ON DELETE SET NULL,
 camera_log_id varchar(50) REFERENCES public.camera_logs(log_id) ON DELETE SET NULL,
 category varchar(30) NOT NULL,
 severity varchar(20) NOT NULL DEFAULT 'INFO',
 title varchar(160) NOT NULL,
 message text NOT NULL,
 status varchar(20) NOT NULL DEFAULT 'UNREAD',
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 read_at timestamptz,
 CONSTRAINT ck_notifications_severity CHECK (severity IN ('INFO','WARNING','CRITICAL')),
 CONSTRAINT ck_notifications_status CHECK (status IN ('UNREAD','READ','RESOLVED'))
);
DO $pbl4$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_devices_area' AND conrelid='public.devices'::regclass) THEN ALTER TABLE public.devices ADD CONSTRAINT fk_devices_area FOREIGN KEY (area_id) REFERENCES public.greenhouse_areas(area_id) ON DELETE SET NULL; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_recommendations_area' AND conrelid='public.recommendations'::regclass) THEN ALTER TABLE public.recommendations ADD CONSTRAINT fk_recommendations_area FOREIGN KEY (area_id) REFERENCES public.greenhouse_areas(area_id) ON DELETE SET NULL; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_camera_logs_area' AND conrelid='public.camera_logs'::regclass) THEN ALTER TABLE public.camera_logs ADD CONSTRAINT fk_camera_logs_area FOREIGN KEY (area_id) REFERENCES public.greenhouse_areas(area_id) ON DELETE SET NULL; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_greenhouses_area_positive' AND conrelid='public.greenhouses'::regclass) THEN ALTER TABLE public.greenhouses ADD CONSTRAINT ck_greenhouses_area_positive CHECK (area_sqm IS NULL OR area_sqm > 0); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_devices_battery_range' AND conrelid='public.devices'::regclass) THEN ALTER TABLE public.devices ADD CONSTRAINT ck_devices_battery_range CHECK (battery_level IS NULL OR battery_level BETWEEN 0 AND 100); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_devices_send_interval_positive' AND conrelid='public.devices'::regclass) THEN ALTER TABLE public.devices ADD CONSTRAINT ck_devices_send_interval_positive CHECK (send_interval IS NULL OR send_interval > 0); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_temperature_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_temperature_range CHECK (temperature IS NULL OR temperature BETWEEN -40 AND 85); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_humidity_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_humidity_range CHECK (humidity IS NULL OR humidity BETWEEN 0 AND 100); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_moisture_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_moisture_range CHECK (soil_moisture IS NULL OR soil_moisture BETWEEN 0 AND 100); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_ph_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_ph_range CHECK (soil_ph IS NULL OR soil_ph BETWEEN 0 AND 14); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_n_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_n_range CHECK (n IS NULL OR n BETWEEN 0 AND 5000); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_p_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_p_range CHECK (p IS NULL OR p BETWEEN 0 AND 5000); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_sensor_k_range' AND conrelid='public.sensor_logs'::regclass) THEN ALTER TABLE public.sensor_logs ADD CONSTRAINT ck_sensor_k_range CHECK (k IS NULL OR k BETWEEN 0 AND 5000); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_recommendations_dosage_nonnegative' AND conrelid='public.recommendations'::regclass) THEN ALTER TABLE public.recommendations ADD CONSTRAINT ck_recommendations_dosage_nonnegative CHECK (dosage IS NULL OR dosage >= 0); END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_recommendations_status_values' AND conrelid='public.recommendations'::regclass) THEN ALTER TABLE public.recommendations ADD CONSTRAINT ck_recommendations_status_values CHECK (status IS NULL OR status IN ('PENDING','APPLIED','IGNORED')); END IF;
END
$pbl4$;
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_ci ON public.users (lower(btrim(email))) WHERE email IS NOT NULL AND btrim(email) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_sensor_logs_device_timestamp ON public.sensor_logs (device_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_devices_greenhouse_id ON public.devices (greenhouse_id);
CREATE INDEX IF NOT EXISTS ix_devices_area_id ON public.devices (area_id);
CREATE INDEX IF NOT EXISTS ix_greenhouse_areas_crop_stage_id ON public.greenhouse_areas (crop_stage_id);
CREATE INDEX IF NOT EXISTS ix_recommendations_device_created ON public.recommendations (device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_recommendations_area_created ON public.recommendations (area_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_camera_logs_greenhouse_created ON public.camera_logs (greenhouse_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_camera_logs_area_created ON public.camera_logs (area_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON public.notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_status_created ON public.notifications (status, created_at DESC);
COMMIT;
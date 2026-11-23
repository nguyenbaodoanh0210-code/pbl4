-- Run after 20261118_outdoor_garden_multimodal_actuators.sql.
BEGIN;
ALTER TABLE public.actuator_states ADD COLUMN IF NOT EXISTS reported_on boolean;
ALTER TABLE public.actuator_states ADD COLUMN IF NOT EXISTS reported_at timestamptz;
ALTER TABLE public.actuator_logs ADD COLUMN IF NOT EXISTS acknowledged_at timestamptz;
ALTER TABLE public.actuator_logs ADD COLUMN IF NOT EXISTS duration_seconds integer;
ALTER TABLE public.actuator_states ALTER COLUMN control_mode SET DEFAULT 'MANUAL';
CREATE INDEX IF NOT EXISTS ix_actuator_logs_actuator_time ON public.actuator_logs(actuator_id, created_at);
COMMIT;

-- Demo-only FARMER account; password is stored as a PBKDF2-HMAC-SHA256 verifier.
-- Apply migrations/20261102_authentication_and_greenhouse_ownership.sql first.
-- This seed never updates an existing account.
BEGIN;
INSERT INTO public.users (user_id, full_name, email, password_hash, role)
VALUES ('demo-farmer-0001', 'Demo Farmer', 'demo@smartgreenhouse.local', 'pbkdf2_sha256$600000$Xatb6i_fd2ZIRiTevi0WFw$B_RaPZ2VHdeEnvJIAeSdtYdZXRu_puJeQ9EDBh90f2E', 'FARMER')
ON CONFLICT DO NOTHING;
COMMIT;

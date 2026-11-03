-- Additive migration for account login and greenhouse ownership.
-- Existing users and greenhouse rows are preserved; legacy greenhouses remain
-- unassigned until a database administrator maps them to an account.
BEGIN;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS password_hash varchar(255);

ALTER TABLE public.greenhouses
    ADD COLUMN IF NOT EXISTS user_id varchar(50);

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE contype = 'f'
          AND conrelid = 'public.greenhouses'::regclass
          AND confrelid = 'public.users'::regclass
          AND conkey = ARRAY[
              (SELECT attnum FROM pg_attribute
               WHERE attrelid = 'public.greenhouses'::regclass AND attname = 'user_id')
          ]
          AND confkey = ARRAY[
              (SELECT attnum FROM pg_attribute
               WHERE attrelid = 'public.users'::regclass AND attname = 'user_id')
          ]
          -- Reuse an existing NO ACTION / RESTRICT owner foreign key, even
          -- when the original schema used a different constraint name.
          AND confdeltype IN ('a', 'r')
    ) THEN
        ALTER TABLE public.greenhouses
            ADD CONSTRAINT fk_greenhouses_user_id
            FOREIGN KEY (user_id)
            REFERENCES public.users(user_id)
            ON DELETE RESTRICT;
    END IF;
END
$migration$;

DO $migration$
BEGIN
    IF EXISTS (
        SELECT lower(btrim(email))
        FROM public.users
        WHERE email IS NOT NULL AND btrim(email) <> ''
        GROUP BY lower(btrim(email))
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate user emails exist; resolve them before applying authentication migration';
    END IF;
END
$migration$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_ci
    ON public.users (lower(btrim(email)))
    WHERE email IS NOT NULL AND btrim(email) <> '';

CREATE INDEX IF NOT EXISTS ix_greenhouses_user_id
    ON public.greenhouses (user_id);

COMMIT;

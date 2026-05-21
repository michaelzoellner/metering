CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

SET search_path TO public;

CREATE TABLE IF NOT EXISTS units (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL UNIQUE,
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS residents (
    id          SERIAL PRIMARY KEY,
    surname     TEXT        NOT NULL,
    givenname   TEXT        NOT NULL,
    email       TEXT,
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS residencies (
    id          SERIAL PRIMARY KEY,
    resident_id INTEGER     NOT NULL REFERENCES residents(id),
    unit_id     INTEGER     NOT NULL REFERENCES units(id),
    start_date  TIMESTAMPTZ NOT NULL,
    end_date    TIMESTAMPTZ,
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT residency_no_overlap_check
        EXCLUDE USING gist (
            unit_id WITH =,
            tstzrange(start_date, end_date) WITH &&
        ) WHERE (active = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_residencies_unit_active
    ON residencies (unit_id, active)
    WHERE active = TRUE;

CREATE TABLE IF NOT EXISTS meter_types (
    id    SERIAL PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

INSERT INTO meter_types (name) VALUES
    ('electricity'),
    ('gas'),
    ('water'),
    ('heat')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS meters (
    id          TEXT        PRIMARY KEY,
    type_id     INTEGER     NOT NULL REFERENCES meter_types(id),
    unit_id     INTEGER     REFERENCES units(id),
    label       TEXT,
    start_date  TIMESTAMPTZ NOT NULL,
    end_date    TIMESTAMPTZ,
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT meter_end_requires_inactive
        CHECK (
            (end_date IS NULL AND active = TRUE)
            OR (end_date IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_meters_unit_active
    ON meters (unit_id, active)
    WHERE active = TRUE;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DO $$ DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['units','residents','residencies','meters'] LOOP
        EXECUTE format('
            CREATE TRIGGER trg_%s_updated_at
            BEFORE UPDATE ON %s
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        ', t, t);
    END LOOP;
END $$;

CREATE OR REPLACE VIEW v_active_residencies AS
SELECT
    r.id            AS residency_id,
    u.id            AS unit_id,
    u.name          AS unit_name,
    res.id          AS resident_id,
    res.surname,
    res.givenname,
    r.start_date,
    r.end_date
FROM residencies r
JOIN units u       ON u.id   = r.unit_id
JOIN residents res ON res.id = r.resident_id
WHERE r.active = TRUE
  AND r.end_date IS NULL;
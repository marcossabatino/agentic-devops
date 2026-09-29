-- Operator-selected default for new UI sessions; existing runs remain immutable.
CREATE TABLE IF NOT EXISTS lab_settings (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    scenario text NOT NULL DEFAULT 'healthy'
);
INSERT INTO lab_settings (singleton) VALUES (true) ON CONFLICT DO NOTHING;
REVOKE ALL ON lab_settings FROM PUBLIC;
GRANT SELECT, UPDATE ON lab_settings TO lab_api;

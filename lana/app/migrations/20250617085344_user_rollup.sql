CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    authentication_id UUID UNIQUE DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ NULL,
    last_sequence INT NOT NULL
);

CREATE OR REPLACE FUNCTION fn_project_user_initialized (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)
    RETURNS VOID
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO users (
        id,
        created_at,
        updated_at,
        last_sequence,
        email)
    VALUES (
        entity_id,
        recorded_at_timestamp,
        recorded_at_timestamp,
        event_sequence,
        event ->> 'email');
    RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION fn_trigger_user_initialized ()
    RETURNS TRIGGER
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF (NEW.event ->> 'type') = 'initialized' THEN
        PERFORM fn_project_user_initialized (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);
    END IF;
    RETURN new;
END;
$$;

CREATE TRIGGER event_insert_user_initialized
    AFTER INSERT ON core_user_events
    FOR EACH ROW
    EXECUTE PROCEDURE fn_trigger_user_initialized ();


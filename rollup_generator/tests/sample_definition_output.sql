CREATE TABLE core_users (
    email VARCHAR NOT NULL UNIQUE,
    authentication_id UUID NULL UNIQUE DEFAULT NULL,
    role_id UUID NULL DEFAULT NULL,
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ NULL,
    last_sequence INTEGER NOT NULL
);

CREATE OR REPLACE FUNCTION fn_project_core_user_initialized (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)
    RETURNS VOID
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO core_users (
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
        CAST(event ->> 'email' AS VARCHAR));
    RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION fn_project_core_user_authentication_id_updated (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)
    RETURNS VOID
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE
        core_users
    SET
        authentication_id = CAST(event ->> 'authentication_id' AS UUID),
        updated_at = recorded_at_timestamp,
        last_sequence = event_sequence
    WHERE id = entity_id;
    RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION fn_project_core_user_role_granted (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)
    RETURNS VOID
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE
        core_users
    SET
        role_id = CAST(event ->> 'id' AS UUID),
        updated_at = recorded_at_timestamp,
        last_sequence = event_sequence
    WHERE id = entity_id;
    RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION fn_project_core_user_role_revoked (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)
    RETURNS VOID
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE
        core_users
    SET
        role_id = NULL,
        updated_at = recorded_at_timestamp,
        last_sequence = event_sequence
    WHERE id = entity_id;
    RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION fn_trigger_core_user_event ()
    RETURNS TRIGGER
    SECURITY DEFINER
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF (NEW.event ->> 'type') = 'initialized' THEN
        PERFORM fn_project_core_user_initialized (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);
        RETURN NEW;
    END IF;
    IF (NEW.event ->> 'type') = 'authentication_id_updated' THEN
        PERFORM fn_project_core_user_authentication_id_updated (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);
        RETURN NEW;
    END IF;
    IF (NEW.event ->> 'type') = 'role_granted' THEN
        PERFORM fn_project_core_user_role_granted (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);
        RETURN NEW;
    END IF;
    IF (NEW.event ->> 'type') = 'role_revoked' THEN
        PERFORM fn_project_core_user_role_revoked (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_rollup_core_user_event
    AFTER INSERT ON core_user_events
    FOR EACH ROW
    EXECUTE PROCEDURE fn_trigger_core_user_event ();


from rollup_generator.definition_parser import (
    parse_json_into_target_table_definition,
    parse_json_into_event_definition,
)
from rollup_generator.definitions import EventDefinition, EntityDefinition


def generate_entity_migration_from_definition(json_content: dict) -> str:
    entity_name = json_content["entity_name"]
    target_table = parse_json_into_target_table_definition(json_content["target_table"])
    events = json_content["events"]

    # Build CREATE TABLE SQL
    create_table_statement = target_table.render().sql_string

    # Deserialize event definitions
    event_definitions = [
        parse_json_into_event_definition(json_content=event_def)
        for event_def in events.values()
    ]

    # Use the refactored render method
    event_sql_fns = [
        event_def.render(entity_name, target_table)
        for event_def in event_definitions
        if event_def.effect is not None
    ]

    # Compose trigger function
    trig_lines = [
        f"CREATE OR REPLACE FUNCTION fn_trigger_{entity_name}_event ()",
        "    RETURNS TRIGGER",
        "    SECURITY DEFINER",
        "    LANGUAGE plpgsql",
        "    AS $$",
        "BEGIN",
    ]
    for event_def in event_definitions:
        trig_lines.append(
            f"    IF (NEW.event ->> 'type') = '{event_def.event_type}' THEN"
        )
        trig_lines.append(
            f"        PERFORM fn_project_{entity_name}_{event_def.event_type} (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);"
        )
        trig_lines.append("        RETURN NEW;")
        trig_lines.append("    END IF;")
    trig_lines.append("    RETURN NEW;")
    trig_lines.append("END;")
    trig_lines.append("$$;")

    trigger_stmt = f"""CREATE TRIGGER trg_rollup_{entity_name}_event
    AFTER INSERT ON {entity_name}_events
    FOR EACH ROW
    EXECUTE PROCEDURE fn_trigger_{entity_name}_event ();"""

    return "\n\n".join(
        [
            create_table_statement,
            *event_sql_fns,
            "\n".join(trig_lines),
            trigger_stmt,
        ]
    )

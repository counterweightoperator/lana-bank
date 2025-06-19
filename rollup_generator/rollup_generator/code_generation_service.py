from rollup_generator.definition_parser import (
    parse_json_into_target_table_definition,
)


def generate_entity_migration_from_definition(json_content: dict) -> str:
    entity_name = json_content["entity_name"]
    target_table = json_content["target_table"]
    fields = target_table["fields"]
    events = json_content["events"]

    # Simple pluralization by adding 's'
    table_name = target_table["table_name"]
    table_name_plural = table_name + "s"

    # Build CREATE TABLE
    table_definition = parse_json_into_target_table_definition(
        json_content["target_table"]
    )

    create_table_statement = table_definition.render().sql_string

    def map_type(field_def):
        typ = field_def["type"].upper()
        return {
            "VARCHAR": "VARCHAR",
            "UUID": "UUID",
            "INT": "INT",
            "INTEGER": "INT",
            "BOOLEAN": "BOOLEAN",
            "TIMESTAMPTZ": "TIMESTAMPTZ",
        }.get(typ, typ)

    def cast_for_update(col, prop):
        # Cast event property according to column type
        ctype = map_type(fields.get(col, {"type": "VARCHAR"}))
        if ctype == "UUID":
            return f"CAST(event ->> '{prop}' AS UUID)"
        return f"event ->> '{prop}'"

    def gen_event_function(event_name, event_def):
        effect = event_def.get("effect")
        if not effect:
            return ""

        dml = effect.get("dml", "").upper()
        mapping = effect.get("mapping", {})

        lines = [
            f"CREATE OR REPLACE FUNCTION fn_project_{entity_name}_{event_name} (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)",
            "    RETURNS VOID",
            "    SECURITY DEFINER",
            "    LANGUAGE plpgsql",
            "    AS $$",
            "BEGIN",
        ]

        if dml == "INSERT":
            cols = ["id", "created_at", "updated_at", "last_sequence"]
            vals = [
                "entity_id",
                "recorded_at_timestamp",
                "recorded_at_timestamp",
                "event_sequence",
            ]

            for col, mdef in mapping.items():
                if col == "id":
                    continue
                if mdef["type"] == "event_property":
                    cols.append(col)
                    vals.append(f"event ->> '{mdef['property']}'")
                elif mdef["type"] == "raw_sql":
                    cols.append(col)
                    vals.append(mdef["property"])
                else:
                    raise ValueError(f"Unsupported mapping type: {mdef['type']}")

            lines.append(f"    INSERT INTO {table_name_plural} (")
            lines.append("        " + ",\n        ".join(cols) + ")")
            lines.append("    VALUES (")
            lines.append("        " + ",\n        ".join(vals) + ");")
            lines.append("    RETURN;")

        elif dml == "UPDATE":
            lines.append(f"    UPDATE")
            lines.append(f"        {table_name_plural}")
            lines.append(f"    SET")
            sets = []
            for col, mdef in mapping.items():
                if mdef["type"] == "event_property":
                    sets.append(
                        f"        {col} = {cast_for_update(col, mdef['property'])}"
                    )
                elif mdef["type"] == "raw_sql":
                    sets.append(f"        {col} = {mdef['property']}")
                else:
                    raise ValueError(f"Unsupported mapping type: {mdef['type']}")

            # Add audit fields
            sets.append("        updated_at = recorded_at_timestamp")
            sets.append("        last_sequence = event_sequence")

            lines.append(",\n".join(sets))
            lines.append(f"    WHERE id = entity_id;")
            lines.append("    RETURN;")

        else:
            raise ValueError(f"Unsupported DML: {dml}")

        lines.append("END;")
        lines.append("$$;")
        return "\n".join(lines)

    event_functions = [
        gen_event_function(name, defn)
        for name, defn in events.items()
        if "effect" in defn
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
    for event_name in events.keys():
        trig_lines.append(f"    IF (NEW.event ->> 'type') = '{event_name}' THEN")
        trig_lines.append(
            f"        PERFORM fn_project_{entity_name}_{event_name} (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);"
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
            *event_functions,
            "\n".join(trig_lines),
            trigger_stmt,
        ]
    )

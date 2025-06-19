def generate_entity_migration_from_definition(json_content: dict) -> str:
    entity_name = json_content["entity_name"]
    target_table = json_content["target_table"]
    fields = target_table["fields"]
    events = json_content["events"]

    # Simple pluralization by adding 's'
    table_name = target_table["table_name"]
    table_name_plural = table_name + "s"

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

    def find_primary_key():
        # Look for explicit PK
        for fname, fdef in fields.items():
            if fdef.get("is_pk"):
                return fname
        # Fallback: infer from first INSERT event mapping 'id'
        for ev in events.values():
            if ev.get("effect", {}).get("dml", "").upper() == "INSERT":
                for col, mapping in ev["effect"]["mapping"].items():
                    if col == "id":
                        # Ensure 'id' in fields
                        if "id" not in fields:
                            fields["id"] = {
                                "type": "UUID",
                                "is_pk": True,
                                "is_nullable": False,
                            }
                        return "id"
        raise ValueError("Primary key column not found")

    def render_column(name, defn, is_pk):
        col_type = map_type(defn)
        parts = [name, col_type]
        if is_pk:
            parts.append("PRIMARY KEY")
        else:
            parts.append("NOT NULL" if not defn.get("is_nullable", False) else "NULL")
        if defn.get("is_unique") and not is_pk:
            parts.append("UNIQUE")
        default = defn.get("default")
        if default is not None:
            if isinstance(default, str) and default.upper() == "NULL":
                parts.append("DEFAULT NULL")
            elif isinstance(default, str):
                parts.append(f"DEFAULT '{default}'")
            else:
                parts.append(f"DEFAULT {default}")
        return " ".join(parts)

    def cast_for_update(col, prop):
        # Cast event property according to column type
        ctype = map_type(fields.get(col, {"type": "VARCHAR"}))
        if ctype == "UUID":
            return f"CAST(event ->> '{prop}' AS UUID)"
        return f"event ->> '{prop}'"

    # Build CREATE TABLE
    pk = find_primary_key()
    columns = [render_column(name, defn, name == pk) for name, defn in fields.items()]

    # Add standard audit columns
    columns.extend(
        [
            "created_at TIMESTAMPTZ NOT NULL",
            "updated_at TIMESTAMPTZ NOT NULL",
            "deleted_at TIMESTAMPTZ NULL",
            "last_sequence INT NOT NULL",
        ]
    )

    create_table = (
        f"CREATE TABLE {table_name_plural} (\n    " + ",\n    ".join(columns) + "\n);"
    )

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
            create_table,
            *event_functions,
            "\n".join(trig_lines),
            trigger_stmt,
        ]
    )

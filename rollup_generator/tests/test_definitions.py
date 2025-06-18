import pytest
from rollup_generator.definition_parser import parse_json_into_entity_definition


def test_validate_happy_path():
    json_content = {
        "entity_name": "core_user",
        "target_table": {
            "table_name": "core_user",
            "fields": {
                "email": {"type": "VARCHAR", "is_nullable": False, "is_unique": True},
                "authentication_id": {"type": "UUID", "is_nullable": True},
                "role_id": {"type": "UUID", "is_nullable": True},
            },
        },
        "events": {
            "initialized": {
                "properties": {
                    "email": {"type": "string"},
                    "id": {"type": "string", "format": "uuid"},
                    "type": {"type": "string", "enum": ["initialized"]},
                },
                "required": ["email", "id", "type"],
                "type": "object",
                "effect": {
                    "dml": "INSERT",
                    "mapping": {
                        "email": {"type": "event_property", "property": "email"},
                        "id": {"type": "event_property", "property": "id"},
                    },
                },
            },
            "authentication_id_updated": {
                "properties": {
                    "authentication_id": {"type": "string", "format": "uuid"},
                    "type": {"type": "string", "enum": ["authentication_id_updated"]},
                },
                "required": ["authentication_id", "type"],
                "type": "object",
                "effect": {
                    "dml": "UPDATE",
                    "mapping": {
                        "authentication_id": {
                            "type": "event_property",
                            "property": "authentication_id",
                        }
                    },
                },
            },
        },
    }

    entity = parse_json_into_entity_definition(json_content)

    entity.validate()
    assert True


def test_validate_raises_when_no_insert_event():
    json_content = {
        "entity_name": "core_user",
        "target_table": {
            "table_name": "core_user",
            "fields": {
                "email": {"type": "VARCHAR", "is_nullable": False},
            },
        },
        "events": {
            "email_updated": {
                "properties": {
                    "email": {"type": "string"},
                    "type": {"type": "string", "enum": ["email_updated"]},
                },
                "required": ["email", "type"],
                "type": "object",
                "effect": {
                    "dml": "UPDATE",
                    "mapping": {
                        "email": {"type": "event_property", "property": "email"}
                    },
                },
            }
        },
    }

    entity = parse_json_into_entity_definition(json_content)

    with pytest.raises(ValueError) as excinfo:
        entity.validate()

    assert "no INSERT event defined" in str(excinfo.value)


def test_validate_raises_when_mapping_column_not_in_target_table():
    json_content = {
        "entity_name": "core_user",
        "target_table": {
            "table_name": "core_user",
            "fields": {
                "email": {"type": "VARCHAR", "is_nullable": False},
            },
        },
        "events": {
            "initialized": {
                "properties": {
                    "email": {"type": "string"},
                    "id": {"type": "string", "format": "uuid"},
                    "type": {"type": "string", "enum": ["initialized"]},
                },
                "required": ["email", "id", "type"],
                "type": "object",
                "effect": {
                    "dml": "INSERT",
                    "mapping": {
                        "nonexistent_column": {
                            "type": "event_property",
                            "property": "foo",
                        },
                    },
                },
            }
        },
    }

    entity = parse_json_into_entity_definition(json_content)

    with pytest.raises(ValueError) as excinfo:
        entity.validate()

    assert "is not defined in target table" in str(excinfo.value)


def test_validate_raises_when_init_event_missing_non_nullable_cols():
    json_content = {
        "entity_name": "core_user",
        "target_table": {
            "table_name": "core_user",
            "fields": {
                "email": {"type": "VARCHAR", "is_nullable": False},
                "role_id": {"type": "UUID", "is_nullable": False},
            },
        },
        "events": {
            "initialized": {
                "properties": {
                    "email": {"type": "string"},
                    "type": {"type": "string", "enum": ["initialized"]},
                },
                "required": ["email", "type"],
                "type": "object",
                "effect": {
                    "dml": "INSERT",
                    "mapping": {
                        "email": {"type": "event_property", "property": "email"},
                    },
                },
            }
        },
    }

    entity = parse_json_into_entity_definition(json_content)

    with pytest.raises(ValueError) as excinfo:
        entity.validate()

    assert "does not map required non-nullable columns" in str(excinfo.value)

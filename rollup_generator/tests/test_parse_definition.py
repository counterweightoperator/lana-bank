import json

from rollup_generator.definition_parser import (
    parse_json_into_target_table_definition,
    parse_json_into_event_definition,
    parse_json_into_effect_definition,
    parse_json_into_entity_definition,
)
from rollup_generator.definitions import (
    TargetTableDefinition,
    EventDefinition,
    EventEffectDefinition,
    DMLOperation,
    EventToColMappingDefinition,
    RawSQLToColMappingDefinition,
    EntityDefinition,
)


def test_parse_target_table_definition_creates_target_table():
    json_content = json.loads(
        """
        {
            "table_name": "core_user",
            "fields": {
                "email": {
                    "type": "VARCHAR",
                    "is_nullable": false,
                    "is_unique": true
                },
                "authentication_id": {
                    "type": "UUID",
                    "is_nullable": true,
                    "is_unique": true,
                    "default": "NULL"
                },
                "role_id": {
                    "type": "UUID",
                    "is_nullable": true,
                    "default": "NULL"
                }
            }
        }
        """
    )

    table_definition = parse_json_into_target_table_definition(
        json_content=json_content
    )

    is_right_class = isinstance(table_definition, TargetTableDefinition)
    has_expected_name = table_definition.table_name == "core_user"
    has_expected_number_of_cols = len(table_definition.domain_column_definitions) + len(
        table_definition.metadata_column_definitions
    )
    assert is_right_class
    assert has_expected_name
    assert has_expected_number_of_cols


def test_parse_event_definition_creates_event():
    json_content = json.loads(
        """
        {
            "properties": {
                "email": {
                    "type": "string"
                },
                "id": {
                    "format": "uuid",
                    "type": "string"
                },
                "type": {
                    "enum": ["initialized"],
                    "type": "string"
                }
            },
            "required": ["email", "id", "type"],
            "type": "object",
            "effect": {
                "dml": "INSERT",
                "mapping": {
                    "id": {
                        "type": "event_property",
                        "property": "id"
                    },
                    "email": {
                        "type": "event_property",
                        "property": "email"
                    }
                }
            }
        }
        """
    )

    event = parse_json_into_event_definition(json_content)

    is_right_class = isinstance(event, EventDefinition)
    has_expected_type = event.event_type == "initialized"
    has_expected_field_count = len(event.schema.fields) == 2  # 'type' is ignored
    effect = event.effect
    has_expected_effect_type = isinstance(effect, EventEffectDefinition)
    has_expected_dml = effect.dml_operation == DMLOperation.INSERT
    has_expected_mapping_count = len(effect.mappings) == 2
    all_mappings_event_props = all(
        isinstance(m, EventToColMappingDefinition) for m in effect.mappings
    )

    assert is_right_class
    assert has_expected_type
    assert has_expected_field_count
    assert has_expected_effect_type
    assert has_expected_dml
    assert has_expected_mapping_count
    assert all_mappings_event_props


def test_parse_event_effect_definition_creates_event_effect():
    json_content = json.loads(
        """
        {
            "dml": "UPDATE",
            "mapping": {
                "role_id": {
                    "type": "raw_sql",
                    "property": "NULL"
                }
            }
        }
        """
    )

    effect = parse_json_into_effect_definition(json_content)

    is_right_class = isinstance(effect, EventEffectDefinition)
    has_expected_dml = effect.dml_operation == DMLOperation.UPDATE
    has_expected_mapping_count = len(effect.mappings) == 1
    mapping = effect.mappings[0]
    is_raw_sql_mapping = isinstance(mapping, RawSQLToColMappingDefinition)
    has_expected_column = mapping.target_table_column_name == "role_id"
    has_expected_sql = mapping.raw_sql == "NULL"

    assert is_right_class
    assert has_expected_dml
    assert has_expected_mapping_count
    assert is_raw_sql_mapping
    assert has_expected_column
    assert has_expected_sql


def test_parse_entity_definition_creates_entity():
    json_content = json.loads(
        """
        {
            "entity_name": "core_user",
            "target_table": {
                "table_name": "core_user",
                "fields": {
                    "email": {
                        "type": "VARCHAR",
                        "is_nullable": false,
                        "is_unique": true
                    },
                    "authentication_id": {
                        "type": "UUID",
                        "is_nullable": true,
                        "is_unique": true,
                        "default": "NULL"
                    },
                    "role_id": {
                        "type": "UUID",
                        "is_nullable": true,
                        "default": "NULL"
                    }
                }
            },
            "events": {
                "initialized": {
                    "properties": {
                        "email": { "type": "string" },
                        "id": { "type": "string", "format": "uuid" },
                        "type": { "type": "string", "enum": ["initialized"] }
                    },
                    "required": ["email", "id", "type"],
                    "type": "object",
                    "effect": {
                        "dml": "INSERT",
                        "mapping": {
                            "id": {
                                "type": "event_property",
                                "property": "id"
                            },
                            "email": {
                                "type": "event_property",
                                "property": "email"
                            }
                        }
                    }
                }
            }
        }
        """
    )

    entity = parse_json_into_entity_definition(json_content)

    is_right_class = isinstance(entity, EntityDefinition)
    has_expected_name = entity.entity_name == "core_user"
    has_expected_table = entity.target_table.table_name == "core_user"
    has_expected_event_count = len(entity.events) == 1
    event = entity.events[0]
    has_expected_event_type = event.event_type == "initialized"

    assert is_right_class
    assert has_expected_name
    assert has_expected_table
    assert has_expected_event_count
    assert has_expected_event_type

import json

from rollup_generator.definition_parser import parse_json_into_target_table_definition
from rollup_generator.definitions import TargetTableDefinition


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
    assert 1 == 0


def test_parse_event_effect_definition_creates_event_effect():
    assert 1 == 0


def test_parse_full_entity_definition_creates_entity():
    assert 1 == 0

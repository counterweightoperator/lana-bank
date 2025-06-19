from rollup_generator.definition_parser import (
    parse_json_into_entity_definition,
)


def generate_entity_migration_from_definition(json_content: dict) -> str:
    entity_definition = parse_json_into_entity_definition(json_content)
    return entity_definition.render().sql_string

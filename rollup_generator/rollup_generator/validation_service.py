from rollup_generator.definition_parser import parse_json_into_entity_definition


def validate_entity_service(json_content: dict) -> None:
    entity = parse_json_into_entity_definition(json_content)
    entity.validate()

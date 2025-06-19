from typing import Tuple, Dict, Any, Collection
from rollup_generator.definitions import (
    PgColType,
    TargetTableDefinition,
    PostgresColumnDefinition,
    EventDefinition,
    EventSchemaDefinition,
    EventFieldDefinition,
    EventType,
    EventFormat,
    EventEffectDefinition,
    DMLOperation,
    EventToColMappingDefinition,
    RawSQLToColMappingDefinition,
    EventEffectType,
    EntityDefinition,
)


def parse_json_into_postgres_column_definitions(
    json_content: dict,
) -> Tuple[PostgresColumnDefinition]:

    cols = []
    for field_name, field_properties in json_content.items():
        new_column = PostgresColumnDefinition(
            column_name=field_name,
            column_type=PgColType(field_properties["type"]),
            is_pk=field_properties.get("is_pk", False),
            is_nullable=field_properties.get("is_nullable", False),
            is_unique=field_properties.get("is_unique", False),
            default_value=field_properties.get("default", None),
        )
        cols.append(new_column)

    return tuple(cols)


def parse_json_into_target_table_definition(
    json_content: dict,
) -> TargetTableDefinition:

    domain_cols = parse_json_into_postgres_column_definitions(json_content["fields"])

    table = TargetTableDefinition(
        table_name=json_content["table_name"], domain_column_definitions=domain_cols
    )

    return table


def parse_json_into_event_definition(
    json_content: dict,
) -> EventDefinition:

    event_type = json_content["properties"]["type"]["enum"][0]

    fields = []
    required_fields = set(json_content.get("required", []))

    for field_name, field_props in json_content["properties"].items():
        if field_name == "type":
            continue  # already handled

        field_type = EventType(field_props["type"])
        field_format = (
            EventFormat(field_props["format"]) if "format" in field_props else None
        )

        fields.append(
            EventFieldDefinition(
                name=field_name,
                type=field_type,
                format=field_format,
                is_required=field_name in required_fields,
            )
        )

    schema = EventSchemaDefinition(fields=tuple(fields))
    effect = parse_json_into_effect_definition(json_content["effect"])

    return EventDefinition(
        event_type=event_type,
        schema=schema,
        effect=effect,
    )


def parse_json_into_effect_definition(json_content: dict) -> EventEffectDefinition:
    dml = DMLOperation(json_content["dml"])
    mappings_json = json_content["mapping"]

    mappings = []

    for col_name, mapping_info in mappings_json.items():
        map_type = EventEffectType(mapping_info["type"])

        if map_type == EventEffectType.EVENT_PROPERTY:
            mappings.append(
                EventToColMappingDefinition(
                    target_table_column_name=col_name,
                    event_property_name=mapping_info["property"],
                )
            )
        elif map_type == EventEffectType.RAW_SQL:
            mappings.append(
                RawSQLToColMappingDefinition(
                    target_table_column_name=col_name,
                    raw_sql=mapping_info["property"],
                )
            )
        else:
            raise ValueError(f"Unsupported mapping type: {map_type}")

    return EventEffectDefinition(dml_operation=dml, mappings=mappings)


def parse_json_into_entity_definition(json_content: dict) -> EntityDefinition:
    entity_name = json_content["entity_name"]
    target_table = parse_json_into_target_table_definition(json_content["target_table"])
    event_definitions = []

    for event_type, event_json in json_content["events"].items():
        event_def = parse_json_into_event_definition(event_json)
        event_def.event_type = event_type  # override based on key
        event_definitions.append(event_def)

    return EntityDefinition(
        entity_name=entity_name, target_table=target_table, events=event_definitions
    )

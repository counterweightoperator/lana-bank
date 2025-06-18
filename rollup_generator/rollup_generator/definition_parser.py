from typing import Tuple

from rollup_generator.definitions import (
    PgColType,
    TargetTableDefinition,
    PostgresColumnDefinition,
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

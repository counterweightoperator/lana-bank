from enum import Enum
from typing import Collection


class PgColType(Enum):
    UUID = "UUID"
    VARCHAR = "VARCHAR"
    TIMESTAMPTZ = "TIMESTAMPTZ"
    INTEGER = "INTEGER"


class PostgresColumnDefinition:
    def __init__(
        self,
        column_name: str,
        column_type: PgColType,
        is_pk: bool = False,
        is_nullable: bool = False,
        is_unique: bool = False,
    ):
        self.column_name = column_name
        self.column_type = column_type
        self.is_pk = is_pk
        self.is_nullable = is_nullable
        self.is_unique = is_unique


class TargetTableDefinition:

    DEFAULT_METADATA_COLS = (
        PostgresColumnDefinition(
            column_name="id", column_type=PgColType.UUID, is_pk=True
        ),
        PostgresColumnDefinition(
            column_name="created_at",
            column_type=PgColType.TIMESTAMPTZ,
            is_nullable=False,
        ),
        PostgresColumnDefinition(
            column_name="updated_at",
            column_type=PgColType.TIMESTAMPTZ,
            is_nullable=False,
        ),
        PostgresColumnDefinition(
            column_name="deleted_at",
            column_type=PgColType.TIMESTAMPTZ,
            is_nullable=True,
        ),
        PostgresColumnDefinition(
            column_name="last_sequence",
            column_type=PgColType.INTEGER,
            is_nullable=False,
        ),
    )

    def __init__(
        self,
        table_name: str,
        domain_column_definitions: Collection[PostgresColumnDefinition],
    ):
        self.table_name = table_name
        self.domain_column_definitions = tuple(domain_column_definitions)
        self.metadata_column_definitions = TargetTableDefinition.DEFAULT_METADATA_COLS

from enum import Enum
from typing import Collection, Union


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


class EventType(Enum):
    STRING = "string"
    ENUM = "enum"


class EventFormat(Enum):
    UUID = "uuid"


class DMLOperation(Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"


class EventEffectType(Enum):
    EVENT_PROPERTY = "event_property"
    RAW_SQL = "raw_sql"


class EventFieldDefinition:
    def __init__(
        self,
        name: str,
        type: EventType,
        format: Union[EventFormat, None],
        is_required: bool = False,
    ):
        self.name = name
        self.type = type
        self.format = format
        self.is_required = is_required


class EventSchemaDefinition:

    def __init__(self, fields: Collection[EventFieldDefinition]):
        self.fields = fields


class BaseEventEffectMappingDefinition:
    def __init__(self, target_table_column_name: str, type: EventEffectType):
        self.target_table_column_name = target_table_column_name
        self.type = type


class EventToColMappingDefinition(BaseEventEffectMappingDefinition):
    def __init__(self, target_table_column_name: str, event_property_name: str):
        super().__init__(target_table_column_name, EventEffectType.EVENT_PROPERTY)
        self.event_property_name = event_property_name


class RawSQLToColMappingDefinition(BaseEventEffectMappingDefinition):
    def __init__(self, target_table_column_name: str, raw_sql: str):
        super().__init__(target_table_column_name, EventEffectType.RAW_SQL)
        self.raw_sql = raw_sql


class EventEffectDefinition:
    def __init__(
        self,
        dml_operation: DMLOperation,
        mappings: Collection[BaseEventEffectMappingDefinition],
    ):
        self.dml_operation = dml_operation
        self.mappings = tuple(mappings)


class EventDefinition:
    def __init__(
        self,
        event_type: str,
        schema: EventSchemaDefinition,
        effect: EventEffectDefinition,
    ):
        self.event_type = event_type
        self.schema = schema
        self.effect = effect


class EntityDefinition:
    def __init__(
        self,
        entity_name: str,
        target_table: TargetTableDefinition,
        events: Collection[EventDefinition],
    ):
        self.entity_name = entity_name
        self.target_table = target_table
        self.events = tuple(events)

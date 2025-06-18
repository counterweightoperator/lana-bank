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

    def validate(self):
        insert_events = self._get_insert_events()
        all_target_cols = self._get_all_target_columns()
        non_nullable_cols = self._get_non_nullable_domain_columns()

        self._validate_insert_event_exists(insert_events)
        self._validate_mappings_reference_target_columns(all_target_cols)
        self._validate_init_event_maps_required_non_nullable_columns(
            insert_events, non_nullable_cols
        )

    def _get_insert_events(self):
        return [
            event
            for event in self.events
            if event.effect.dml_operation == DMLOperation.INSERT
        ]

    def _get_all_target_columns(self):
        return {
            col.column_name for col in self.target_table.domain_column_definitions
        }.union(
            {col.column_name for col in self.target_table.metadata_column_definitions}
        )

    def _get_non_nullable_domain_columns(self):
        return {
            col.column_name
            for col in self.target_table.domain_column_definitions
            if not col.is_nullable
        }

    def _validate_insert_event_exists(self, insert_events):
        if not insert_events:
            raise ValueError(
                f"Entity '{self.entity_name}' has no INSERT event defined."
            )

    def _validate_mappings_reference_target_columns(self, all_target_cols):
        for event in self.events:
            for mapping in event.effect.mappings:
                if mapping.target_table_column_name not in all_target_cols:
                    raise ValueError(
                        f"Column '{mapping.target_table_column_name}' in event '{event.event_type}' "
                        f"is not defined in target table '{self.target_table.table_name}'."
                    )

    def _validate_init_event_maps_required_non_nullable_columns(
        self, insert_events, non_nullable_cols
    ):
        initializing_event = insert_events[0]
        mapped_cols = {
            m.target_table_column_name for m in initializing_event.effect.mappings
        }
        missing_required_cols = non_nullable_cols - mapped_cols
        if missing_required_cols:
            raise ValueError(
                f"Initializing event '{initializing_event.event_type}' does not map required "
                f"non-nullable columns: {sorted(missing_required_cols)}"
            )

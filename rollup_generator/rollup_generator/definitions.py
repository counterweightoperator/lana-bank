from enum import Enum
from typing import Collection, Union, List, Set


class SyntacticallyValidSQL:

    def __init__(self, sql_string: str):
        if not SyntacticallyValidSQL._is_valid_pgsql_string(sql_string):
            raise ValueError(f"Invalid SQL: {sql_string}")
        self.sql_string = sql_string

    @staticmethod
    def _is_valid_pgsql_string(sql_string: str) -> bool:
        # Pending
        return True


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
        default_value: str = None,
    ):
        self.column_name = column_name
        self.column_type = column_type
        self.is_pk = is_pk
        self.is_nullable = is_nullable
        self.is_unique = is_unique
        self.default_value = default_value

    def render(self) -> str:

        parts = [self.column_name, self.column_type.value]
        if self.is_pk:
            parts.append("PRIMARY KEY")
            return " ".join(parts)

        parts.append("NULL" if self.is_nullable else "NOT NULL")
        if self.is_unique:
            parts.append("UNIQUE")
        if self.default_value is not None:
            parts.append(f"DEFAULT {self.default_value}")

        return " ".join(parts)


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

    def render(self, pluralise: bool = True) -> SyntacticallyValidSQL:

        table_name = self.table_name
        if pluralise:
            table_name = table_name + "s"

        domain_column_renders = [col.render() for col in self.domain_column_definitions]
        metadata_column_renders = [
            col.render() for col in self.metadata_column_definitions
        ]
        all_column_renders = domain_column_renders + metadata_column_renders

        create_table_statement = (
            f"CREATE TABLE {table_name} (\n    "
            + ",\n    ".join(all_column_renders)
            + "\n);"
        )

        return SyntacticallyValidSQL(create_table_statement)


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

    def render(self, entity_name: str, target_table: TargetTableDefinition) -> str:
        table_name = target_table.table_name + "s"

        def cast_for_update(col, prop):
            col_type = next(
                (
                    c.column_type
                    for c in (
                        list(target_table.domain_column_definitions)
                        + list(target_table.metadata_column_definitions)
                    )
                    if c.column_name == col
                ),
                PgColType.VARCHAR,  # Default fallback
            )

            if col_type == PgColType.UUID:
                return f"CAST(event ->> '{prop}' AS UUID)"
            return f"event ->> '{prop}'"

        effect = self.effect
        dml = effect.dml_operation.value.upper()
        mappings = effect.mappings

        lines = [
            f"CREATE OR REPLACE FUNCTION fn_project_{entity_name}_{self.event_type} (entity_id UUID, event_sequence INTEGER, recorded_at_timestamp TIMESTAMPTZ, event JSONB)",
            "    RETURNS VOID",
            "    SECURITY DEFINER",
            "    LANGUAGE plpgsql",
            "    AS $$",
            "BEGIN",
        ]

        if dml == "INSERT":
            cols = ["id", "created_at", "updated_at", "last_sequence"]
            vals = [
                "entity_id",
                "recorded_at_timestamp",
                "recorded_at_timestamp",
                "event_sequence",
            ]

            for mapping in mappings:
                if mapping.target_table_column_name == "id":
                    continue

                if isinstance(mapping, EventToColMappingDefinition):
                    cols.append(mapping.target_table_column_name)
                    vals.append(f"event ->> '{mapping.event_property_name}'")
                elif isinstance(mapping, RawSQLToColMappingDefinition):
                    cols.append(mapping.target_table_column_name)
                    vals.append(mapping.raw_sql)
                else:
                    raise ValueError(f"Unsupported mapping type: {type(mapping)}")

            lines += [
                f"    INSERT INTO {table_name} (",
                "        " + ",\n        ".join(cols) + ")",
                "    VALUES (",
                "        " + ",\n        ".join(vals) + ");",
                "    RETURN;",
            ]

        elif dml == "UPDATE":
            lines.append(f"    UPDATE")
            lines.append(f"        {table_name}")
            lines.append(f"    SET")

            sets = []
            for mapping in mappings:
                if isinstance(mapping, EventToColMappingDefinition):
                    sets.append(
                        f"        {mapping.target_table_column_name} = {cast_for_update(mapping.target_table_column_name, mapping.event_property_name)}"
                    )
                elif isinstance(mapping, RawSQLToColMappingDefinition):
                    sets.append(
                        f"        {mapping.target_table_column_name} = {mapping.raw_sql}"
                    )
                else:
                    raise ValueError(f"Unsupported mapping type: {type(mapping)}")

            # Audit fields
            sets += [
                "        updated_at = recorded_at_timestamp",
                "        last_sequence = event_sequence",
            ]

            lines.append(",\n".join(sets))
            lines.append(f"    WHERE id = entity_id;")
            lines.append("    RETURN;")
        else:
            raise ValueError(f"Unsupported DML: {dml}")

        lines += ["END;", "$$;"]

        return "\n".join(lines)


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

    def validate(self) -> None:
        insert_events = self._get_insert_events()
        all_target_cols = self._get_all_target_columns()
        non_nullable_cols = self._get_non_nullable_domain_columns()

        self._validate_insert_event_exists(insert_events)
        self._validate_mappings_reference_target_columns(all_target_cols)
        self._validate_init_event_maps_required_non_nullable_columns(
            insert_events, non_nullable_cols
        )

    def _get_insert_events(self) -> List[EventDefinition]:
        return [
            event
            for event in self.events
            if event.effect.dml_operation == DMLOperation.INSERT
        ]

    def _get_all_target_columns(self) -> Set[str]:
        return {
            col.column_name for col in self.target_table.domain_column_definitions
        }.union(
            {col.column_name for col in self.target_table.metadata_column_definitions}
        )

    def _get_non_nullable_domain_columns(self) -> Set[str]:
        return {
            col.column_name
            for col in self.target_table.domain_column_definitions
            if not col.is_nullable
        }

    def _validate_insert_event_exists(
        self, insert_events: List[EventDefinition]
    ) -> None:
        if not insert_events:
            raise ValueError(
                f"Entity '{self.entity_name}' has no INSERT event defined."
            )

    def _validate_mappings_reference_target_columns(
        self, all_target_cols: Set[str]
    ) -> None:
        for event in self.events:
            for mapping in event.effect.mappings:
                if mapping.target_table_column_name not in all_target_cols:
                    raise ValueError(
                        f"Column '{mapping.target_table_column_name}' in event '{event.event_type}' "
                        f"is not defined in target table '{self.target_table.table_name}'."
                    )

    def _validate_init_event_maps_required_non_nullable_columns(
        self, insert_events: List[EventDefinition], non_nullable_cols: Set[str]
    ) -> None:
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

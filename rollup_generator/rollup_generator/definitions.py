from enum import Enum
from typing import Collection, Union, List, Set

import pglast


class SyntacticallyValidSQL:

    def __init__(self, sql_string: str):
        if not SyntacticallyValidSQL._is_valid_pgsql_string(sql_string):
            raise ValueError(f"Invalid SQL: {sql_string}")
        self.sql_string = sql_string

    @staticmethod
    def _is_valid_pgsql_string(sql_string: str) -> bool:
        try:
            pglast.parse_sql(sql_string)
        except pglast.parser.ParseError:
            return False

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

    ID_COL = PostgresColumnDefinition(
        column_name="id", column_type=PgColType.UUID, is_pk=True
    )
    CREATED_AT_COL = PostgresColumnDefinition(
        column_name="created_at",
        column_type=PgColType.TIMESTAMPTZ,
        is_nullable=False,
    )
    UPDATED_AT_COL = PostgresColumnDefinition(
        column_name="updated_at",
        column_type=PgColType.TIMESTAMPTZ,
        is_nullable=False,
    )
    DELETED_AT_COL = PostgresColumnDefinition(
        column_name="deleted_at",
        column_type=PgColType.TIMESTAMPTZ,
        is_nullable=True,
    )
    LAST_SEQUENCE_COL = PostgresColumnDefinition(
        column_name="last_sequence",
        column_type=PgColType.INTEGER,
        is_nullable=False,
    )

    DEFAULT_METADATA_COLS = (
        ID_COL,
        CREATED_AT_COL,
        UPDATED_AT_COL,
        DELETED_AT_COL,
        LAST_SEQUENCE_COL,
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

    DEFAULT_METADATA_COL_NAMES = [
        TargetTableDefinition.ID_COL.column_name,
        TargetTableDefinition.CREATED_AT_COL.column_name,
        TargetTableDefinition.UPDATED_AT_COL.column_name,
        TargetTableDefinition.LAST_SEQUENCE_COL.column_name,
    ]

    DEFAULT_ENTITY_ID_NAME = "entity_id"
    DEFAULT_RECORDED_AT_TIMESTAMP_NAME = "recorded_at_timestamp"
    DEFAULT_EVENT_SEQUENCE_NAME = "event_sequence"
    DEFAULT_EVENT_NAME = "event"

    DEFAULT_METADATA_INSERT_VALS = [
        DEFAULT_ENTITY_ID_NAME,
        DEFAULT_RECORDED_AT_TIMESTAMP_NAME,
        DEFAULT_RECORDED_AT_TIMESTAMP_NAME,
        DEFAULT_EVENT_SEQUENCE_NAME,
    ]

    def __init__(
        self,
        event_type: str,
        schema: EventSchemaDefinition,
        effect: EventEffectDefinition,
    ):
        self.event_type = event_type
        self.schema = schema
        self.effect = effect

    def render(self, target_table: TargetTableDefinition) -> SyntacticallyValidSQL:
        table_name = target_table.table_name + "s"
        dml = self.effect.dml_operation
        all_columns = {
            col.column_name: col.column_type
            for col in list(target_table.domain_column_definitions)
            + list(target_table.metadata_column_definitions)
        }

        lines = [
            f"CREATE OR REPLACE FUNCTION fn_project_{target_table.table_name}_{self.event_type} ({EventDefinition.DEFAULT_ENTITY_ID_NAME} UUID, {EventDefinition.DEFAULT_EVENT_SEQUENCE_NAME} INTEGER, {EventDefinition.DEFAULT_RECORDED_AT_TIMESTAMP_NAME} TIMESTAMPTZ, {EventDefinition.DEFAULT_EVENT_NAME} JSONB)",
            "    RETURNS VOID",
            "    SECURITY DEFINER",
            "    LANGUAGE plpgsql",
            "    AS $$",
            "BEGIN",
        ]

        if dml == DMLOperation.INSERT:
            lines += self._render_insert(self.effect, table_name, all_columns)
        if dml == DMLOperation.UPDATE:
            lines += self._render_update(self.effect, table_name, all_columns)

        lines += ["END;", "$$;"]

        event_projection_function = SyntacticallyValidSQL("\n".join(lines))

        return event_projection_function

    @staticmethod
    def _render_insert(
        effect: EventEffectDefinition, table_name: str, all_columns: dict
    ) -> list[str]:
        cols = list(EventDefinition.DEFAULT_METADATA_COL_NAMES)
        vals = list(EventDefinition.DEFAULT_METADATA_INSERT_VALS)

        for mapping in effect.mappings:
            if (
                mapping.target_table_column_name
                == TargetTableDefinition.ID_COL.column_name
            ):
                continue
            if isinstance(mapping, EventToColMappingDefinition):
                cols.append(mapping.target_table_column_name)
                vals.append(
                    EventDefinition._cast_expr(
                        mapping.event_property_name,
                        mapping.target_table_column_name,
                        all_columns,
                    )
                )
            if isinstance(mapping, RawSQLToColMappingDefinition):
                cols.append(mapping.target_table_column_name)
                vals.append(mapping.raw_sql)

        return [
            f"    INSERT INTO {table_name} (",
            "        " + ",\n        ".join(cols) + ")",
            "    VALUES (",
            "        " + ",\n        ".join(vals) + ");",
            "    RETURN;",
        ]

    @staticmethod
    def _render_update(
        effect: EventEffectDefinition, table_name: str, all_columns: dict
    ) -> list[str]:
        sets = []

        for mapping in effect.mappings:
            if isinstance(mapping, EventToColMappingDefinition):
                sets.append(
                    f"        {mapping.target_table_column_name} = "
                    f"{EventDefinition._cast_expr(mapping.event_property_name, mapping.target_table_column_name, all_columns)}"
                )
            if isinstance(mapping, RawSQLToColMappingDefinition):
                sets.append(
                    f"        {mapping.target_table_column_name} = {mapping.raw_sql}"
                )

        sets += [
            f"        {TargetTableDefinition.UPDATED_AT_COL.column_name} = {EventDefinition.DEFAULT_RECORDED_AT_TIMESTAMP_NAME}",
            f"        {TargetTableDefinition.LAST_SEQUENCE_COL.column_name} = {EventDefinition.DEFAULT_EVENT_SEQUENCE_NAME}",
        ]

        lines = [
            "    UPDATE",
            f"        {table_name}",
            "    SET",
            ",\n".join(sets),
            f"    WHERE {TargetTableDefinition.ID_COL.column_name} = {EventDefinition.DEFAULT_ENTITY_ID_NAME};",
            "    RETURN;",
        ]
        return lines

    @staticmethod
    def _cast_expr(event_prop: str, column_name: str, all_columns: dict) -> str:
        col_type = all_columns.get(column_name, PgColType.VARCHAR)
        pg_type = col_type.value
        return f"CAST({EventDefinition.DEFAULT_EVENT_NAME} ->> '{event_prop}' AS {pg_type})"


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

    def render(self) -> SyntacticallyValidSQL:
        entity_name = self.entity_name
        target_table = self.target_table
        events = self.events

        create_table_statement = target_table.render().sql_string
        event_projection_functions = [
            event.render(target_table).sql_string for event in events
        ]

        trig_lines = [
            f"CREATE OR REPLACE FUNCTION fn_trigger_{entity_name}_event ()",
            "    RETURNS TRIGGER",
            "    SECURITY DEFINER",
            "    LANGUAGE plpgsql",
            "    AS $$",
            "BEGIN",
        ]
        for event in events:
            trig_lines.append(
                f"    IF (NEW.event ->> 'type') = '{event.event_type}' THEN"
            )
            trig_lines.append(
                f"        PERFORM fn_project_{entity_name}_{event.event_type} (NEW.id, NEW.sequence, NEW.recorded_at, NEW.event);"
            )
            trig_lines.append("        RETURN NEW;")
            trig_lines.append("    END IF;")
        trig_lines.append("    RETURN NEW;")
        trig_lines.append("END;")
        trig_lines.append("$$;")

        trigger_stmt = "\n".join(
            [
                f"CREATE TRIGGER trg_rollup_{entity_name}_event",
                f"    AFTER INSERT ON {entity_name}_events",
                "    FOR EACH ROW",
                f"    EXECUTE PROCEDURE fn_trigger_{entity_name}_event ();",
            ]
        )

        final_sql = SyntacticallyValidSQL(
            "\n\n".join(
                [
                    create_table_statement,
                    *event_projection_functions,
                    "\n".join(trig_lines),
                    trigger_stmt,
                ]
            )
        )
        return final_sql

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

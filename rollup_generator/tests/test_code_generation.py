import pytest
from click.testing import CliRunner
from pathlib import Path


from rollup_generator.cli import (
    generate_entity_migration,
)


@pytest.fixture
def input_json_file_path(tmp_path: Path) -> Path:
    return Path("tests", "sample_definition.json")


def test_generate_entity_migration_matches_expected(input_json_file_path: Path):
    runner = CliRunner()

    result = runner.invoke(generate_entity_migration, [str(input_json_file_path)])

    assert result.exit_code == 0
    actual_sql_output = result.output.strip()

    expected_sql_file = Path(__file__).parent / "sample_definition_output.sql"
    expected_sql = expected_sql_file.read_text().strip()

    assert actual_sql_output == expected_sql

from click.testing import CliRunner

from rollup_generator.cli import smoke_test


def test_smoke_test_outputs_message():
    runner = CliRunner()
    result = runner.invoke(smoke_test)
    assert result.exit_code == 0
    assert "Run running, running" in result.output

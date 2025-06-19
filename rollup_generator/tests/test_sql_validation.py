from rollup_generator.definitions import SyntacticallyValidSQL


def test_valid_sql_is_valid():
    is_valid = SyntacticallyValidSQL._is_valid_pgsql_string("SELECT 1;")
    assert is_valid


def test_valid_sql_is_valid():
    is_valid = SyntacticallyValidSQL._is_valid_pgsql_string("gibberish")
    assert not is_valid

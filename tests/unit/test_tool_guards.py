import pytest

from orchestrator.tools.db_query import query_database
from orchestrator.tools.file_io import _resolve_in_workspace, read_file, write_file


def test_file_io_blocks_path_traversal():
    with pytest.raises(ValueError):
        _resolve_in_workspace("../../etc/passwd")


def test_file_io_round_trip_within_workspace():
    write_file("unit_test_scratch.txt", "hello")
    assert read_file("unit_test_scratch.txt") == "hello"


def test_file_io_missing_file_reports_error_not_exception():
    assert "does not exist" in read_file("does_not_exist_12345.txt")


def test_db_query_rejects_non_select_statements():
    assert "only SELECT/WITH" in query_database("DELETE FROM tasks")
    assert "only SELECT/WITH" in query_database("DROP TABLE tasks")


def test_db_query_rejects_disallowed_keyword_smuggled_in_select():
    assert "disallowed keyword" in query_database("SELECT 1; INSERT INTO tasks VALUES (1)")


def test_db_query_allows_plain_select():
    result = query_database("SELECT 1 AS one")
    assert "one" in result
    assert "1" in result

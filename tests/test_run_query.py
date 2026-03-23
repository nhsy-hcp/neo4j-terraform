import pytest
from unittest.mock import MagicMock, patch, mock_open
from scripts.run_query import run_queries


def test_run_queries_not_found():
    with patch("os.path.exists", return_value=False):
        with pytest.raises(SystemExit) as excinfo:
            run_queries("nonexistent.cql")
        assert excinfo.value.code == 1


def test_run_queries_success():
    mock_cql = "// Get Providers\nMATCH (p:TF_Provider) RETURN p.name;"

    # Mock file reading
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_cql)),
        patch("scripts.run_query.GraphDatabase.driver") as mock_driver,
    ):
        session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = session

        # Mocking the result
        result = MagicMock()
        result.keys.return_value = ["p.name"]
        result.__iter__.return_value = [{"p.name": "aws"}]
        session.run.return_value = result

        # We need to list-ify it in the script, so let's mock the list behavior
        with patch("scripts.run_query.list", return_value=[{"p.name": "aws"}]):
            run_queries("test.cql")

        assert session.run.called
        mock_driver.return_value.close.called


def test_run_queries_exception():
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="MATCH (n) RETURN n;")),
        patch("scripts.run_query.GraphDatabase.driver") as mock_driver,
    ):
        mock_driver.return_value.session.side_effect = Exception("Neo4j error")

        with pytest.raises(SystemExit) as excinfo:
            run_queries("test.cql")
        assert excinfo.value.code == 1

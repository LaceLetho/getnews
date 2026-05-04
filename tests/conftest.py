"""Shared pytest configuration for integration test safety."""

import os
from typing import Callable
from urllib.parse import unquote, urlparse

import pytest
from _pytest.config import Config
from _pytest.nodes import Item

REAL_POSTGRES_MARKER = "real_postgres"


def assert_safe_test_database_url(database_url: str) -> None:
    """Refuse TEST_DATABASE_URL values that do not clearly target test databases."""
    parsed = urlparse(database_url)
    database_name = unquote(parsed.path.rsplit("/", maxsplit=1)[-1]).lower()
    if "test" not in database_name and "ci" not in database_name:
        raise RuntimeError(
            "Refusing to run real Postgres integration tests: TEST_DATABASE_URL database "
            + f"name '{database_name or '<empty>'}' must contain 'test' or 'ci'."
        )


def pytest_configure(config: Config) -> None:
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line(
        "markers",
        "real_postgres: requires TEST_DATABASE_URL pointing at a test/ci PostgreSQL database",
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    _ = config
    real_postgres_items = [
        item
        for item in items
        if item.get_closest_marker(REAL_POSTGRES_MARKER) is not None
        or ("test_real_postgres" in item.name and "safety_guard" not in item.name)
    ]
    if not real_postgres_items:
        return

    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        skip_reason = (
            "TEST_DATABASE_URL environment variable not set; set TEST_DATABASE_URL "
            + "to run real Postgres integration tests"
        )
        skip_real_postgres = pytest.mark.skip(reason=skip_reason)
        for item in real_postgres_items:
            item.add_marker(skip_real_postgres)
        return

    assert_safe_test_database_url(database_url)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Return a safety-checked TEST_DATABASE_URL or skip real Postgres tests."""
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TEST_DATABASE_URL environment variable not set; set TEST_DATABASE_URL "
            + "to run real Postgres integration tests"
        )
    assert_safe_test_database_url(database_url)
    return database_url


@pytest.fixture(scope="session")
def safe_test_database_url_guard() -> Callable[[str], None]:
    return assert_safe_test_database_url

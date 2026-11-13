"""Tests for JS parsing/cleaning. These never hit the live server."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(filename):
    return (FIXTURES / filename).read_text()

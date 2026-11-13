"""Tests for JS parsing/cleaning. These never hit the live server."""

from pathlib import Path

import pandas as pd
import pytest

from tennisage import data

FIXTURES = Path(__file__).parent / "fixtures"
SERENA_DOB = pd.Timestamp("1981-09-26")
NADAL_DOB = pd.Timestamp("1986-06-03")


def read_fixture(filename):
    return (FIXTURES / filename).read_text()


def build_matches(filename, birth_date):
    rows = data._parse_matches(read_fixture(filename))
    return data._add_ages(data._rows_to_frame(rows), birth_date)


# --- _normalize_name -------------------------------------------------------

@pytest.mark.parametrize("raw_name", [
    "serena williams", "Serena Williams", "SerenaWilliams",
    "  serena   williams ", "serenaWilliams",
])
def test_normalize_name_formats(raw_name):
    assert data._normalize_name(raw_name) == "SerenaWilliams"


def test_normalize_name_keeps_inner_capitals():
    assert data._normalize_name("john mcEnroe") == "JohnMcEnroe"


def test_normalize_name_hyphens_and_accents():
    assert data._normalize_name("Jo-Wilfried Tsonga") == "JoWilfriedTsonga"
    assert data._normalize_name("Gaël Monfils") == "GaelMonfils"


@pytest.mark.parametrize("bad_name", ["", "   ", "123"])
def test_normalize_name_rejects_empty(bad_name):
    with pytest.raises(ValueError):
        data._normalize_name(bad_name)


def test_normalize_name_rejects_non_string():
    with pytest.raises(TypeError):
        data._normalize_name(None)


# --- _fetch_text (network is mocked) ---------------------------------------

class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_text_returns_none_on_404(monkeypatch):
    monkeypatch.setattr(data.requests, "get",
                        lambda url, timeout: FakeResponse(404))
    assert data._fetch_text("https://example.com/missing.js") is None


def test_fetch_text_returns_body(monkeypatch):
    monkeypatch.setattr(data.requests, "get",
                        lambda url, timeout: FakeResponse(200, "var x = 1;"))
    assert data._fetch_text("https://example.com/x.js") == "var x = 1;"


# --- _parse_matches / _parse_birth_date ------------------------------------

@pytest.mark.parametrize("filename, row_length", [
    ("FemalePlayerCareer.js", 27), ("MalePlayerCareer.js", 47),
])
def test_parse_matches(filename, row_length):
    rows = data._parse_matches(read_fixture(filename))
    assert len(rows) == 3
    assert all(len(row) == row_length for row in rows)


def test_parse_matches_rejects_bad_text():
    with pytest.raises(ValueError):
        data._parse_matches("<html>Not Found</html>")


def test_parse_birth_date():
    js_text = "var fullname = 'Rafael Nadal';\n    dob=19860603;\n"
    assert data._parse_birth_date(js_text) == NADAL_DOB


def test_parse_birth_date_missing():
    with pytest.raises(ValueError):
        data._parse_birth_date("var fullname = 'Nobody';")


# --- ages / final data frame -----------------------------------------------

def test_female_opponent_ages_from_birth_dates():
    matches = build_matches("FemalePlayerCareer.js", SERENA_DOB)
    # Anne Miller: born 1977-01-19, match on 1995-10-30
    expected = (pd.Timestamp("1995-10-30") - pd.Timestamp("1977-01-19")).days
    assert matches.loc[0, "opponent_age"] == pytest.approx(expected / 365.25)
    assert matches["opponent_age"].between(17, 28).all()


def test_male_opponent_ages_passed_through():
    matches = build_matches("MalePlayerCareer.js", NADAL_DOB)
    assert matches["opponent_age"].tolist() == pytest.approx(
        [22.264202601, 24.2902121834, 18.7597535934])


@pytest.mark.parametrize("filename, birth_date", [
    ("FemalePlayerCareer.js", SERENA_DOB), ("MalePlayerCareer.js", NADAL_DOB),
])
def test_final_frame_structure(filename, birth_date):
    matches = build_matches(filename, birth_date)
    assert list(matches.columns) == ["date", "opponent", "result",
                                     "player_age", "opponent_age", "age_diff"]
    assert len(matches) == 3
    assert set(matches["result"]) <= {"W", "L"}
    assert matches["age_diff"].tolist() == pytest.approx(
        (matches["player_age"] - matches["opponent_age"]).tolist())


def test_player_age():
    matches = build_matches("MalePlayerCareer.js", NADAL_DOB)
    # Nadal (born 1986-06-03) on 2001-09-10 was 15
    assert 15 < matches.loc[0, "player_age"] < 16


def test_rows_missing_opponent_age_are_dropped():
    rows = data._parse_matches(read_fixture("MalePlayerCareer.js"))
    rows[1][data.OPPONENT_AGE_COL] = ""
    matches = data._add_ages(data._rows_to_frame(rows), NADAL_DOB)
    assert len(matches) == 2
    assert "Stefano Galvani" not in matches["opponent"].tolist()

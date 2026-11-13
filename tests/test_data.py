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


def test_parse_matches_missing_variable_returns_empty():
    assert data._parse_matches("<html>Not Found</html>") == []
    assert data._parse_matches("") == []


def test_parse_matches_picks_requested_variable():
    js_text = ('var matchmx = [["20240101", "A"]];\n'
               'var morematchmx = [["20200101", "B"]];')
    assert data._parse_matches(js_text, "matchmx") == [["20240101", "A"]]
    assert data._parse_matches(js_text) == [["20200101", "B"]]


def test_parse_full_name():
    assert data._parse_full_name("var fullname = 'Rafael Nadal';",
                                 "RafaelNadal") == "Rafael Nadal"
    assert data._parse_full_name("no name here", "RafaelNadal") == "RafaelNadal"


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
    assert {"date", "tournament", "surface", "round", "result", "score",
            "opponent", "opponent_rank", "player_age", "opponent_age",
            "age_difference"} <= set(matches.columns)
    assert "opponent_info" not in matches.columns
    assert len(matches) == 3
    assert set(matches["result"]) <= {"W", "L"}
    assert matches["age_difference"].tolist() == pytest.approx(
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


# --- get_player_matches (network is mocked with the fixture files) ---------

FAKE_PROFILE = """
    var fullname = 'Rafael Nadal';
    dob=19860603;
    var matchmx = [["20170102", "Brisbane", "Hard", "A", "W", "", "", "1", "R16", "6-3 6-3", "3", "Mischa Zverev", "50", "", "", "L", "29.4", "", "GER"]];
"""


def fake_site(files):
    """Stand-in for _fetch_text: return files[filename], or None (404)."""
    return lambda url: files.get(url.rsplit("/", 1)[-1])


def test_get_player_matches_combines_career_and_recent(monkeypatch):
    monkeypatch.setattr(data, "_fetch_text", fake_site({
        "RafaelNadal.js": FAKE_PROFILE,
        "RafaelNadalCareer.js": read_fixture("MalePlayerCareer.js"),
    }))
    matches = data.get_player_matches("rafael nadal")
    assert list(matches.columns) == data.COLUMNS
    assert len(matches) == 4
    assert matches["year"].tolist() == [2001, 2001, 2001, 2017]
    assert matches["opponent_rank"].iloc[0] == 731
    assert (matches["player"] == "Rafael Nadal").all()
    assert matches["date"].is_monotonic_increasing
    assert matches["opponent"].iloc[-1] == "Mischa Zverev"


def test_get_player_matches_without_career_file(monkeypatch):
    monkeypatch.setattr(data, "_fetch_text",
                        fake_site({"RafaelNadal.js": FAKE_PROFILE}))
    assert len(data.get_player_matches("Rafael Nadal")) == 1


def test_get_player_matches_drops_duplicate_matches(monkeypatch):
    career = read_fixture("MalePlayerCareer.js")
    profile = FAKE_PROFILE + career.replace("morematchmx", "matchmx", 1)
    profile = profile.replace("var matchmx", "var unused", 1)
    monkeypatch.setattr(data, "_fetch_text", fake_site({
        "RafaelNadal.js": profile, "RafaelNadalCareer.js": career}))
    assert len(data.get_player_matches("RafaelNadal")) == 3


@pytest.mark.parametrize("bad_name", ["Gaston Sanchez", "GastonSanchez"])
def test_get_player_matches_unknown_player(monkeypatch, bad_name):
    monkeypatch.setattr(data, "_fetch_text", fake_site({}))
    with pytest.raises(ValueError, match="not found on tennisabstract.com"):
        data.get_player_matches(bad_name)

"""Retrieve and clean a player's career matches from tennisabstract.com."""

import json
import re
import unicodedata

import pandas as pd
import requests

BASE_URL = "https://www.tennisabstract.com/jsmatches/"
DAYS_PER_YEAR = 365.25

# Column positions in each row of a career JS file
DATE_COL, RESULT_COL, OPPONENT_COL, OPPONENT_AGE_COL = 0, 4, 11, 16


def get_player_matches(player_name):
    """Return a clean DataFrame of a player's career matches.

    Parameters
    ----------
    player_name : str
        e.g. "serena williams", "Serena Williams", or "SerenaWilliams".
    """
    raise NotImplementedError


def _normalize_name(player_name):
    """Convert 'serena williams' or 'Serena Williams' to 'SerenaWilliams'."""
    if not isinstance(player_name, str):
        raise TypeError("player_name must be a string, e.g. 'Serena Williams'")
    # strip accents (e.g. 'Gaël' -> 'Gael'), then split on non-letters
    ascii_name = unicodedata.normalize("NFKD", player_name)
    ascii_name = ascii_name.encode("ascii", "ignore").decode()
    words = re.split(r"[^A-Za-z]+", ascii_name)
    name = "".join(word[0].upper() + word[1:] for word in words if word)
    if not name:
        raise ValueError(f"Invalid player name: {player_name!r}")
    return name


def _fetch_text(url):
    """Download a text file; return None if it does not exist (HTTP 404)."""
    response = requests.get(url, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


def _parse_matches(js_text):
    """Turn the text 'var morematchmx = [[...], ...];' into a list of rows."""
    start, end = js_text.find("["), js_text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No match data found in career JS text")
    return json.loads(js_text[start:end + 1])


def _parse_birth_date(js_text):
    """Extract the player's birth date from the text 'dob=YYYYMMDD'."""
    match = re.search(r"dob\s*=\s*(\d{8})", js_text)
    if match is None:
        raise ValueError("No birth date (dob) found in player JS text")
    return pd.to_datetime(match.group(1), format="%Y%m%d")


def _years_between(start_dates, end_dates):
    """Age in (fractional) years from start_dates to end_dates."""
    return (end_dates - start_dates).dt.days / DAYS_PER_YEAR


def _opponent_ages(opponent_info, match_dates):
    """Opponent ages: female files give a birth date, male files an age."""
    is_birth_date = opponent_info.str.fullmatch(r"\d{8}")
    birth_dates = pd.to_datetime(opponent_info.where(is_birth_date),
                                 format="%Y%m%d", errors="coerce")
    ages_from_dob = _years_between(birth_dates, match_dates)
    given_ages = pd.to_numeric(opponent_info, errors="coerce")
    return ages_from_dob.where(is_birth_date, given_ages)


def _rows_to_frame(rows):
    """Keep only the columns needed for plotting from the raw rows."""
    return pd.DataFrame({
        "date": pd.to_datetime([row[DATE_COL] for row in rows],
                               format="%Y%m%d"),
        "opponent": [row[OPPONENT_COL] for row in rows],
        "result": [row[RESULT_COL] for row in rows],
        "opponent_info": [row[OPPONENT_AGE_COL] for row in rows],
    })


def _add_ages(matches, player_birth_date):
    """Add player_age, opponent_age, and age_diff; drop rows missing ages."""
    matches = matches.copy()
    matches["player_age"] = _years_between(player_birth_date, matches["date"])
    matches["opponent_age"] = _opponent_ages(matches["opponent_info"],
                                             matches["date"])
    matches["age_diff"] = matches["player_age"] - matches["opponent_age"]
    matches = matches.dropna(subset=["opponent_age"])
    return matches.drop(columns="opponent_info").reset_index(drop=True)

"""Retrieve and clean a player's career matches from tennisabstract.com."""

import json
import re
import unicodedata

import pandas as pd
import requests

BASE_URL = "https://www.tennisabstract.com/jsmatches/"
DAYS_PER_YEAR = 365.25

# Positions of the fields we need within each match array. Field 16 is the
# opponent's birth date (female players) or age (male players).
FIELDS = {
    "date": 0, "tournament": 1, "surface": 2, "level": 3, "result": 4,
    "round": 8, "score": 9, "opponent": 11, "opponent_rank": 12,
    "opponent_info": 16, "opponent_country": 18,
}
OPPONENT_AGE_COL = FIELDS["opponent_info"]
MATCH_KEY = ["date", "tournament", "round", "opponent"]
COLUMNS = [
    "player", "date", "year", "tournament", "surface", "level", "round",
    "result", "score", "opponent", "opponent_country", "opponent_rank",
    "player_age", "opponent_age", "age_difference",
]


def get_player_matches(player_name):
    """Return a clean DataFrame of a player's career matches.

    Older matches come from ``{Name}Career.js`` and recent ones from the
    ``matchmx`` array in ``{Name}.js`` (which also holds the birth date).

    Parameters
    ----------
    player_name : str
        e.g. "serena williams", "Serena Williams", or "SerenaWilliams".

    Returns
    -------
    pandas.DataFrame
        One row per match, sorted by date, with columns: player, date, year,
        tournament, surface, level, round, result ("W"/"L"), score,
        opponent, opponent_country, opponent_rank, player_age, opponent_age,
        and age_difference (player_age - opponent_age), ages in years.

    Raises
    ------
    ValueError
        If the player is not found on tennisabstract.com.
    """
    url_name = _normalize_name(player_name)
    profile_text = _fetch_text(f"{BASE_URL}{url_name}.js")
    if profile_text is None:
        raise ValueError(_not_found_message(player_name, url_name))
    career_text = _fetch_text(f"{BASE_URL}{url_name}Career.js") or ""
    rows = (_parse_matches(career_text, "morematchmx")
            + _parse_matches(profile_text, "matchmx"))
    if not rows:
        raise ValueError(f"No matches found for {player_name!r}")
    matches = _rows_to_frame(rows).drop_duplicates(subset=MATCH_KEY)
    matches = _add_ages(matches, _parse_birth_date(profile_text))
    matches["player"] = _parse_full_name(profile_text, url_name)
    matches["year"] = matches["date"].dt.year
    matches = matches.sort_values("date", kind="stable")
    return matches[COLUMNS].reset_index(drop=True)


def _not_found_message(player_name, url_name):
    """Explain that a player could not be found on tennisabstract.com."""
    return (f"Player {player_name!r} not found on tennisabstract.com "
            f"(looked for '{url_name}'). Check the spelling, e.g. "
            "'Serena Williams'. Some players are listed under their full "
            "name, e.g. 'Carlos Alcaraz Garfia'.")


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


def _parse_matches(js_text, var_name="morematchmx"):
    """Turn the text 'var <var_name> = [[...], ...];' into a list of rows.

    Returns an empty list if the variable is not in the text.
    """
    found = re.search(rf"\bvar\s+{var_name}\s*=", js_text)
    if found is None:
        return []
    # the array runs until the next 'var' statement (or the end of the text)
    array_text = re.split(r"\n\s*var\s", js_text[found.end():], maxsplit=1)[0]
    start, end = array_text.find("["), array_text.rfind("]")
    return json.loads(array_text[start:end + 1])


def _parse_birth_date(js_text):
    """Extract the player's birth date from the text 'dob=YYYYMMDD'."""
    match = re.search(r"dob\s*=\s*(\d{8})", js_text)
    if match is None:
        raise ValueError("No birth date (dob) found in player JS text")
    return pd.to_datetime(match.group(1), format="%Y%m%d")


def _parse_full_name(js_text, default):
    """Extract the name from "var fullname = 'Rafael Nadal';" (or default)."""
    match = re.search(r"var\s+fullname\s*=\s*'([^']*)'", js_text)
    return match.group(1) if match else default


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
    """Keep only the FIELDS we need from the raw rows, with proper types."""
    matches = pd.DataFrame(
        [[row[i] if i < len(row) else "" for i in FIELDS.values()]
         for row in rows],
        columns=list(FIELDS))
    matches["date"] = pd.to_datetime(matches["date"], format="%Y%m%d")
    matches["opponent_rank"] = pd.to_numeric(
        matches["opponent_rank"], errors="coerce").astype("Int64")
    return matches


def _add_ages(matches, player_birth_date):
    """Add player_age, opponent_age, age_difference; drop rows missing ages."""
    matches = matches.copy()
    matches["player_age"] = _years_between(player_birth_date, matches["date"])
    matches["opponent_age"] = _opponent_ages(matches["opponent_info"],
                                             matches["date"])
    matches["age_difference"] = (matches["player_age"]
                                 - matches["opponent_age"])
    matches = matches.dropna(subset=["opponent_age"])
    return matches.drop(columns="opponent_info").reset_index(drop=True)

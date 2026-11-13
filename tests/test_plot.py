"""Tests for the scatter plot (built from fixture data; no network)."""

import matplotlib

matplotlib.use("Agg")  # draw without opening a window

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from tennisage import plot_age_difference  # noqa: E402
from tennisage.plot import _plot_title  # noqa: E402


@pytest.fixture
def matches():
    return pd.DataFrame({
        "player": ["Serena Williams"] * 3,
        "result": ["W", "L", "W"],
        "player_age": [14.1, 15.4, 15.9],
        "age_difference": [-4.6, -11.9, -3.5],
    })


def test_plot_draws_one_point_per_match(matches):
    ax = plot_age_difference(matches)
    wins, losses = ax.collections
    assert len(wins.get_offsets()) == 2
    assert len(losses.get_offsets()) == 1


def test_plot_labels_and_legend(matches):
    ax = plot_age_difference(matches)
    assert ax.get_title(loc="left") == \
        "Serena Williams's Professional Matches, Age 14 to 15"
    assert ax.get_xlabel() == "Serena Williams's age"
    legend = [text.get_text() for text in ax.get_legend().get_texts()]
    assert legend == ["Match won", "Match lost"]


def test_plot_uses_given_axes(matches):
    import matplotlib.pyplot as plt
    _, ax = plt.subplots()
    assert plot_age_difference(matches, ax=ax) is ax


def test_title_without_player_column(matches):
    assert _plot_title(matches.drop(columns="player")) == \
        "Player's Professional Matches, Age 14 to 15"


def test_title_with_no_matches(matches):
    assert _plot_title(matches.iloc[0:0]) == "Player's Professional Matches"

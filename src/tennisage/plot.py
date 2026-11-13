"""Scatter plot of player age vs. age difference with opponents (as in HW2)."""

import matplotlib.pyplot as plt

# Colorblind-safe pair (blue/orange), checked for contrast and CVD separation
RESULT_STYLES = {"W": ("Match won", "#2a78d6"), "L": ("Match lost", "#eb6834")}


def plot_age_difference(matches, ax=None):
    """Plot player age (x) vs. age difference (y), colored by win/loss.

    Parameters
    ----------
    matches : pandas.DataFrame
        Output of ``get_player_matches()``. Needs the columns player_age,
        age_difference, and result ("W"/"L"); a "player" column is used in
        the title and axis label.
    ax : matplotlib.axes.Axes, optional
        Axes to draw on. A new figure is created if omitted.

    Returns
    -------
    matplotlib.axes.Axes
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 6), facecolor="white")
    for result, (label, color) in RESULT_STYLES.items():
        subset = matches[matches["result"] == result]
        ax.scatter(subset["player_age"], subset["age_difference"], s=22,
                   color=color, alpha=0.7, edgecolors="none", label=label)
    ax.axhline(0, color="black", linewidth=0.8)
    _style_axes(ax, matches)
    return ax


def _player_name(matches):
    """The player's name from the "player" column, or "Player"."""
    if "player" in matches.columns and len(matches) > 0:
        return matches["player"].iloc[0]
    return "Player"


def _plot_title(matches):
    """Title like "Serena Williams's Professional Matches, Age 14 to 40"."""
    title = f"{_player_name(matches)}'s Professional Matches"
    if len(matches) > 0:
        ages = matches["player_age"]
        title += f", Age {int(ages.min())} to {int(ages.max())}"
    return title


def _style_axes(ax, matches):
    """Title, axis labels, y-grid, and legend; hide top/right/left spines."""
    ax.set_title(_plot_title(matches), loc="left", fontsize=14,
                 fontweight="bold")
    ax.set_xlabel(f"{_player_name(matches)}'s age")
    ax.set_ylabel("Age difference vs. opponent (years)")
    ax.grid(axis="y", color="lightgray", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper left", frameon=False)

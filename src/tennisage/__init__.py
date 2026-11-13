"""tennisage: career match data and age-difference plots from tennisabstract.com."""

from .data import get_player_matches
from .plot import plot_age_difference

__all__ = ["get_player_matches", "plot_age_difference"]

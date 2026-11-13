# tennisage

A Python package to retrieve the career matches of a tennis player from
[tennisabstract.com](https://www.tennisabstract.com) and plot the age
difference between the player and their opponents (like the NYT visualization
from HW2).

## Installation

```bash
pip install git+https://github.com/UCB-stat159-f26/hw03-2-reemarafifar72.git
```

## Usage

```python
from tennisage import get_player_matches, plot_age_difference

serena = get_player_matches("serena williams")
plot_age_difference(serena)

rafa = get_player_matches("Rafael Nadal")
plot_age_difference(rafa)

# raises a meaningful error
get_player_matches("GastonSanchez")
```

## Running tests

```bash
pip install -e ".[test]"
pytest
```

## Personal Reflections

_TODO_

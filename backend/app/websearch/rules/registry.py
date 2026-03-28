from __future__ import annotations

from .base import VerticalRule
from .generic import GenericRule
from .music import MusicEntityListRule, MusicLookupRule
from .sports import SportsRule
from .stock import StockRule
from .weather import WeatherRule

RULES: dict[str, VerticalRule] = {
    "music_entity_list": MusicEntityListRule(),
    "music_lookup": MusicLookupRule(),
    "weather": WeatherRule(),
    "stock": StockRule(),
    "sports": SportsRule(),
    "general": GenericRule(),
    "entity_list": GenericRule(),
    "news": GenericRule(),
}


def get_rule_for_intent(intent: str) -> VerticalRule:
    return RULES.get(intent, RULES["general"])

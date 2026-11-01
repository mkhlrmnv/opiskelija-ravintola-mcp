"""Domain models shared by all adapters and the MCP tool layer."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "fi"]
MacroBasis = Literal["portion", "100g", "unknown"]


class Macros(BaseModel):
    """Nutrition facts for one dish. Every field is optional: sites publish different subsets."""

    basis: MacroBasis = Field(
        "unknown", description="Whether values are per portion or per 100 g, as published."
    )
    portion_g: float | None = Field(None, description="Portion weight in grams, if published.")
    energy_kcal: float | None = None
    energy_kj: float | None = None
    protein_g: float | None = None
    carbohydrates_g: float | None = None
    sugars_g: float | None = None
    fat_g: float | None = None
    saturated_fat_g: float | None = None
    fibre_g: float | None = None
    salt_g: float | None = None

    def is_empty(self) -> bool:
        return all(
            v is None for k, v in self.model_dump().items() if k not in ("basis", "portion_g")
        )


class Dish(BaseModel):
    id: str = Field(description="Stable id within a restaurant+date menu; use it with get_macros.")
    name: str
    category: str | None = Field(None, description="Menu line / station, e.g. 'Vegan', 'Grill'.")
    description: str | None = None
    diets: list[str] = Field(
        default_factory=list, description="Diet codes as published (G, L, M, VEG...)."
    )
    allergens: list[str] = Field(default_factory=list)
    price: str | None = Field(None, description="Price text as published (student price if known).")
    macros: Macros | None = None


class Menu(BaseModel):
    restaurant_id: str
    restaurant_name: str
    date: dt.date
    lang: Lang
    dishes: list[Dish] = Field(default_factory=list)
    lunch_hours: str | None = None
    source_url: str | None = None
    notes: list[str] = Field(
        default_factory=list,
        description="Caveats, e.g. language fallback or 'closed'.",
    )
    error: str | None = Field(None, description="Set when fetching/parsing failed.")

    @property
    def macros_available(self) -> bool:
        return any(d.macros is not None for d in self.dishes)


class Restaurant(BaseModel):
    id: str = Field(description="Slug used in tool calls, e.g. 'a-bloc'.")
    name: str
    aliases: list[str] = Field(default_factory=list)
    campus: str
    provider: str = Field(description="Adapter key, e.g. 'compass', 'sodexo'.")
    url: str = Field(description="Public menu page.")
    config: dict[str, str] = Field(
        default_factory=dict, description="Provider-specific ids (cost number, restaurant id...)."
    )

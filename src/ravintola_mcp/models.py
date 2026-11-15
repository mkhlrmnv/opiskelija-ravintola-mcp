"""Domain models shared by all adapters and the MCP tool layer."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Lang = Literal["en", "fi"]
MacroBasis = Literal["portion", "100g", "unknown"]

KJ_PER_KCAL = 4.184


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

    @model_validator(mode="after")
    def _fill_missing_energy_unit(self) -> Macros:
        """Give both energy units when the site publishes only one of them."""
        if self.energy_kcal is None and self.energy_kj is not None:
            self.energy_kcal = round(self.energy_kj / KJ_PER_KCAL, 1)
        elif self.energy_kj is None and self.energy_kcal is not None:
            self.energy_kj = round(self.energy_kcal * KJ_PER_KCAL, 1)
        return self

    def is_empty(self) -> bool:
        return all(
            v is None for k, v in self.model_dump().items() if k not in ("basis", "portion_g")
        )


class DishComponent(BaseModel):
    """One part of a multi-component dish, with its own nutrition when the site publishes it."""

    name: str
    macros: Macros | None = None


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
    macros: Macros | None = Field(
        None, description="Nutrition of the dish as a whole; null for multi-component dishes."
    )
    components: list[DishComponent] = Field(
        default_factory=list,
        description="Parts of the dish with their own nutrition (per-100 g values cannot be "
        "summed into a dish total).",
    )


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
    source: str | None = Field(
        None, description="Who publishes this data, e.g. 'Source: Sodexo (sodexo.fi)'."
    )

    @property
    def macros_available(self) -> bool:
        return any(
            d.macros is not None or any(c.macros is not None for c in d.components)
            for d in self.dishes
        )


class Restaurant(BaseModel):
    id: str = Field(description="Slug used in tool calls, e.g. 'a-bloc'.")
    name: str
    aliases: list[str] = Field(default_factory=list)
    campus: str
    provider: str = Field(description="Adapter key, e.g. 'compass', 'sodexo'.")
    operator: str | None = Field(
        None, description="Who publishes the menu data; credited as the source in every menu."
    )
    url: str = Field(description="Public menu page.")
    config: dict[str, str] = Field(
        default_factory=dict, description="Provider-specific ids (cost number, restaurant id...)."
    )

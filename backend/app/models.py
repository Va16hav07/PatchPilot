"""API request/response models."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.nutrition.engine import OilLevel
from app.nutrition.measures import UserMeasures
from app.nutrition.targets import Profile, Targets

Meal = Literal["breakfast", "lunch", "snacks", "dinner"]
MEALS: tuple[Meal, ...] = ("breakfast", "lunch", "snacks", "dinner")


class GoogleLogin(BaseModel):
    credential: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    picture: str | None = None
    profile: Profile | None = None
    targets: Targets | None = None
    targets_custom: bool = False
    measures: UserMeasures


class Portion(BaseModel):
    quantity: float = Field(gt=0, le=100000)
    unit: str
    oil_level: OilLevel = "home"


class PortionOut(BaseModel):
    nutrients: dict[str, float]
    grams: float | None
    servings: float | None
    assumptions: list[str]


class LogCreate(Portion):
    date: dt.date
    meal: Meal
    food_id: str


class LogItem(Portion):
    food_id: str


class LogBatch(BaseModel):
    date: dt.date
    meal: Meal
    items: list[LogItem] = Field(min_length=1, max_length=30)


class CopyMeal(BaseModel):
    from_date: dt.date
    from_meal: Meal
    to_meal: Meal


class RecentFood(BaseModel):
    food_id: str
    food_name: str
    source: str
    quantity: float
    unit: str
    serving_unit: str | None
    oil_level: OilLevel
    energy_kcal: float


class LogEntryOut(BaseModel):
    id: str
    date: dt.date
    meal: Meal
    food_id: str
    food_name: str
    source: str
    quantity: float
    unit: str
    serving_unit: str | None = None  # dishes: what one "serving" is, e.g. "chapati"
    oil_level: OilLevel
    grams: float | None
    servings: float | None
    nutrients: dict[str, float]
    assumptions: list[str]


class DayOut(BaseModel):
    date: dt.date
    targets: Targets | None
    totals: dict[str, float]
    meals: dict[Meal, list[LogEntryOut]]


class DaySummary(BaseModel):
    date: dt.date
    totals: dict[str, float]
    entries: int


class FoodSummary(BaseModel):
    id: str
    name: str
    source: str
    kind: Literal["ingredient", "dish"]
    local_names: list[str]
    basis: str  # "100 g" or "1 <serving unit>"
    energy_kcal: float
    protein_g: float
    units: list[str]


class FoodDetail(FoodSummary):
    nutrients: dict[str, float]
    group: str | None = None
    serving_unit: str | None = None
    added_fat_g: float | None = None
    ingredients: list[dict] | None = None
    derived_from: str | None = None  # curated dishes: how they were made from an INDB recipe
    quality_flags: list[str]

"""Household measures: how Indian kitchens measure food, converted to ml.

Volumes are defaults; a user calibrates their own katori and glass in settings.
"""

from pydantic import BaseModel, Field

TSP_ML = 5.0
TBSP_ML = 15.0
CUP_ML = 240.0  # INDB's unit table: 1 C = 240 ml

# INDB recipes give serving sizes as named containers ("bowl", "plate", ...)
# without a volume. For container-type servings we assume these volumes, so a
# user's katori can be compared against them. This is an assumption the app
# surfaces to the user, not data from INDB.
CONTAINER_SERVING_ML: dict[str, float] = {
    "bowl": 150.0,
    "curry bowl": 150.0,
    "katori": 150.0,
    "small bowl": 100.0,
    "soup bowl": 200.0,
}


class UserMeasures(BaseModel):
    katori_ml: float = Field(150.0, ge=50, le=500)
    glass_ml: float = Field(250.0, ge=100, le=600)


def volume_ml(unit: str, measures: UserMeasures) -> float | None:
    """Volume of one household unit, or None if the unit is not a volume."""
    return {
        "tsp": TSP_ML,
        "tbsp": TBSP_ML,
        "cup": CUP_ML,
        "katori": measures.katori_ml,
        "glass": measures.glass_ml,
        "ml": 1.0,
    }.get(unit)

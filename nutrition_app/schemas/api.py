from typing import Literal

from pydantic import BaseModel, Field, PositiveFloat, field_validator, model_validator


class ProfileInput(BaseModel):
    sex: Literal["male", "female"] = "male"
    age: int = Field(default=28, ge=14, le=80)
    height_cm: PositiveFloat = Field(default=170, ge=120, le=240)
    weight_kg: PositiveFloat = Field(default=65, ge=30, le=250)
    activity_level: Literal["low", "moderate", "high"] = "moderate"
    goal: Literal["lose", "maintain", "gain"] = "maintain"


class MealEntryInput(BaseModel):
    entry_id: str | None = Field(default=None, max_length=120)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    source: str = Field(min_length=1, max_length=64)
    source_food_id: str = Field(min_length=1, max_length=1000)
    grams: PositiveFloat | None = Field(default=None, ge=1, le=2000)
    quantity: PositiveFloat | None = Field(default=None, ge=0.1, le=50)
    unit_key: str | None = Field(default=None, max_length=64)
    unit_label: str | None = Field(default=None, max_length=32)

    @field_validator("source_food_id")
    @classmethod
    def strip_food_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("unit_label")
    @classmethod
    def strip_unit_label(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def validate_amount_fields(self):
        if self.grams is None and self.quantity is None:
            raise ValueError("Either grams or quantity must be provided.")
        return self


class DaySummaryRequest(BaseModel):
    profile: ProfileInput
    entries: list[MealEntryInput] = Field(default_factory=list, max_length=200)


class BulkResolveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    default_meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = "breakfast"

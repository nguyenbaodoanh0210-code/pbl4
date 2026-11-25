from pydantic import BaseModel, Field


class FertilizerPredictionInput(BaseModel):
    Crop_Type: str = Field(min_length=1, max_length=50)
    Growth_Stage: str = Field(min_length=1, max_length=50)
    Temperature: float = Field(allow_inf_nan=False)
    Humidity: float = Field(allow_inf_nan=False)
    Soil_Moisture: float = Field(allow_inf_nan=False)
    Soil_pH: float = Field(allow_inf_nan=False)
    Nitrogen: float = Field(allow_inf_nan=False)
    Phosphorus: float = Field(allow_inf_nan=False)
    Potassium: float = Field(allow_inf_nan=False)


class FertilizerPredictionOutput(BaseModel):
    condition_diagnosis: str
    fertilizer_action: str
    model: str
    experimental: bool
    note: str


class DiseasePredictionOutput(BaseModel):
    class_name: str
    scores: dict[str, float]
    score_note: str
    experimental: bool

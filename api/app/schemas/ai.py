from pydantic import BaseModel


class DiseasePredictionOutput(BaseModel):
    class_name: str
    class_group: str | None = None
    model: str | None = None
    scores: dict[str, float]
    score_note: str
    experimental: bool

from pydantic import BaseModel, ConfigDict, Field


class ErroPadrao(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Companhia nao encontrada."}})
    detail: str = Field(description="Mensagem de erro em português.")

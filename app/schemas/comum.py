from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer, WithJsonSchema, model_validator

from app.services.normalizacao import (
    data_para_string_br,
    datetime_para_string_br,
    decimal_para_canonical_string,
)

CanonicalDecimal = Annotated[
    Decimal,
    PlainSerializer(decimal_para_canonical_string, return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^(?!^[-+.]*$)[+-]?\d+(?:\.\d+)?$",
        }
    ),
]


def _parse_brazilian_date(value: object) -> object:
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        texto = value.strip()
        if not texto:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                continue
    return value


def _parse_brazilian_datetime(value: object) -> object:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        texto = value.strip()
        if not texto:
            return None
        for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(texto, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(texto)
        except ValueError:
            return value
    return value

BrazilianDate = Annotated[
    date,
    BeforeValidator(_parse_brazilian_date),
    PlainSerializer(data_para_string_br, return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^\d{2}/\d{2}/\d{4}$",
            "examples": ["21/06/2026"],
        }
    ),
]

BrazilianDateTime = Annotated[
    datetime,
    BeforeValidator(_parse_brazilian_datetime),
    PlainSerializer(datetime_para_string_br, return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$",
            "examples": ["21/06/2026 14:30:00"],
        }
    ),
]


class Paginacao(BaseModel):
    pagina: int = Field(
        description="Pagina atual considerada na resposta.",
        examples=[1],
    )
    tamanho_pagina: int = Field(
        description="Tamanho da pagina aplicado na consulta.",
        examples=[100],
    )
    total: int = Field(
        description="Total de registros disponiveis para os filtros informados.",
        examples=[1250],
    )


class PeriodicModel(BaseModel):
    ano: int | None = None
    trimestre: int | None = None
    periodo_tipo: str | None = None
    periodo_label: str | None = None

    @model_validator(mode="after")
    def preencher_campos_periodo(self) -> "PeriodicModel":
        if hasattr(self, "data_referencia") and self.data_referencia:
            ref_date = self.data_referencia
            self.ano = ref_date.year
            self.trimestre = (ref_date.month - 1) // 3 + 1
            
            tf = getattr(self, "tipo_formulario", None)
            class_name = self.__class__.__name__
            
            if tf == "DFP" or "Dfp" in class_name or "Fre" in class_name or "Fca" in class_name or "Cgvn" in class_name:
                self.periodo_tipo = "ANUAL"
                self.periodo_label = f"{self.ano}"
            elif tf == "ITR" or "Itr" in class_name or "Vlmo" in class_name:
                self.periodo_tipo = "TRIMESTRAL"
                self.periodo_label = f"{self.ano}-{self.trimestre}T"
            elif "Ipe" in class_name:
                self.periodo_tipo = "EVENTUAL"
                self.periodo_label = f"{self.ano}-{self.trimestre}T"
            else:
                if ref_date.month == 12 and ref_date.day == 31:
                    self.periodo_tipo = "ANUAL"
                    self.periodo_label = f"{self.ano}"
                else:
                    self.periodo_tipo = "TRIMESTRAL"
                    self.periodo_label = f"{self.ano}-{self.trimestre}T"
        return self

from datetime import date
from pydantic import BaseModel, Field, model_validator


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


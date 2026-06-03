from pydantic import BaseModel, Field


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

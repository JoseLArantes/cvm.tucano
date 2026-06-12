from pydantic import BaseModel, Field


class FonteResposta(BaseModel):
    fonte: str = Field(description="Chave identificadora da fonte (ex: dfp, fre).")
    descricao: str = Field(description="Descrição da fonte.")
    tipo_distribuicao: str = Field(description="Tipo de distribuição (csv_unico ou zip_anual).")
    primeiro_ano: int | None = Field(None, description="Primeiro ano disponível.")
    ultimo_ano: int | None = Field(None, description="Último ano disponível.")
    status_suporte: str = Field(description="Status de suporte da fonte.")


class DatasetResposta(BaseModel):
    dataset: str = Field(description="Nome do dataset / tabela.")
    descricao: str = Field(description="Descrição do conteúdo do dataset.")
    obrigatorio: bool = Field(description="Se o dataset é de preenchimento obrigatório.")
    status_suporte: str = Field(description="Status de suporte do dataset.")
    exportavel: bool = Field(description="Se o dataset possui endpoint de exportação em lote disponível.")

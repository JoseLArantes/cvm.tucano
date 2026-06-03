from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


class PaginacaoQuery:
    def __init__(
        self,
        pagina: int = Query(
            default=1,
            ge=1,
            description="Numero da pagina (inicia em 1).",
            examples=[1, 2],
        ),
        tamanho_pagina: int = Query(
            default=100,
            ge=1,
            le=500,
            description="Quantidade maxima de itens por pagina (limite tecnico: 500).",
            examples=[50, 100, 250],
        ),
    ) -> None:
        self.pagina = pagina
        self.tamanho_pagina = tamanho_pagina
        self.offset = (pagina - 1) * tamanho_pagina

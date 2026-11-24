from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReferenciaIsin(Base):
    __tablename__ = "referencias_isin"

    codigo_isin: Mapped[str] = mapped_column(String(12), primary_key=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True, nullable=False)

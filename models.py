"""Modelo único, com exatamente os sete campos solicitados."""
from sqlalchemy import Column, Date, Numeric, String, Text
from database import Base


class Oportunidade(Base):
    __tablename__ = "oportunidades_2025"

    # A URL é a chave primária: dispensa coluna id e evita duplicação.
    link = Column(Text, primary_key=True)
    titulo = Column(Text, nullable=False)
    data_publicacao = Column(Date)
    regiao = Column(Text)  # Siglas de estados (ex.: SP, RJ) ou "Nacional".
    area_projeto = Column(Text)
    valor = Column(Numeric(20, 2))
    moeda = Column(String(3))  # BRL, USD ou EUR.

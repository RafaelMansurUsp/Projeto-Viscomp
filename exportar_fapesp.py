"""Exporta chamadas do PostgreSQL para CSV, sem alterar o banco.

Execute dentro da pasta do projeto que contém database.py e credenciais.txt.
"""
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from database import engine

SAIDA = Path("dados/chamadas_fapesp.csv")
SQL = """
SELECT titulo, link, data_publicacao, regiao, area_projeto, valor, moeda
FROM oportunidades_2025
ORDER BY data_publicacao NULLS LAST, titulo
"""


def main():
    with engine.connect() as conexao:
        df = pd.read_sql(text(SQL), conexao)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAIDA, index=False, encoding="utf-8")
    print(f"Exportadas {len(df)} chamadas para {SAIDA}")
    print("Valores ausentes por coluna:")
    print(df.isna().sum().to_string())


if __name__ == "__main__":
    main()

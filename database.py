"""Conexão com PostgreSQL usando as credenciais locais do projeto."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

CAMINHO_CREDENCIAIS = Path(__file__).with_name("credenciais.txt")
if not CAMINHO_CREDENCIAIS.is_file():
    raise RuntimeError(
        "Crie o arquivo credenciais.txt (veja credenciais.exemplo.txt) "
        "na mesma pasta de database.py."
    )

linhas = [linha.strip() for linha in CAMINHO_CREDENCIAIS.read_text(encoding="utf-8").splitlines()]
if len(linhas) != 5:
    raise RuntimeError("credenciais.txt precisa ter 5 linhas: usuário, senha, banco, host e porta.")

usuario, senha, banco, host, porta = linhas
url = URL.create(
    drivername="postgresql+psycopg2",
    username=usuario,
    password=senha,
    host=host,
    port=int(porta),
    database=banco,
)
engine = create_engine(url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

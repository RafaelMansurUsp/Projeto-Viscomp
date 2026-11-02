"""API FastAPI com uma tabela e rotas para chamadas históricas de 2020 a 2025."""
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import inspect
from sqlalchemy.orm import Session

import models
from database import Base, engine, get_db
from scraping import (
    buscar_chamadas_fapesp,
    buscar_detalhes_chamada_fapesp,
    extrair_area_projeto,
    extrair_moeda_e_valor,
    extrair_regiao,
)

Base.metadata.create_all(bind=engine)
# create_all não migra estruturas antigas: falhar com mensagem clara, sem apagar nada.
colunas = {coluna["name"] for coluna in inspect(engine).get_columns("oportunidades_2025")}
esperadas = {coluna.name for coluna in models.Oportunidade.__table__.columns}
if colunas != esperadas:
    raise RuntimeError(
        "A tabela oportunidades_2025 já existe com colunas diferentes. "
        "Salve os registros que desejar e execute manualmente "
        "DROP TABLE oportunidades_2025; antes de iniciar esta versão. "
        f"Existentes: {sorted(colunas)}; esperadas: {sorted(esperadas)}"
    )

app = FastAPI(title="Chamadas FAPESP 2020-2025 - banco mínimo", version="2.0")


@app.get("/")
def inicio():
    return {"projeto": "Chamadas FAPESP 2020-2025", "campos": sorted(esperadas)}


@app.post("/scraping/fapesp")
def executar_scraping(
    limite: int | None = Query(None, ge=1, description="Quantidade de editais para teste."),
    ano: int | None = Query(None, ge=2020, le=2025, description="Ano da listagem; sem informar, consulta 2020 a 2025."),
    db: Session = Depends(get_db),
):
    """Consulta a listagem e cada edital; insere ou atualiza usando a URL."""
    try:
        chamadas = buscar_chamadas_fapesp(ano=ano)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao ler o índice: {exc}") from exc
    if limite is not None:
        chamadas = chamadas[:limite]

    adicionadas = atualizadas = 0
    falhas = []
    for chamada in chamadas:
        try:
            # Uma falha em um edital não interrompe os demais.
            with db.begin_nested():
                link = chamada["link"]
                registro = db.get(models.Oportunidade, link)
                nova = registro is None
                if nova:
                    registro = models.Oportunidade(link=link, titulo=chamada["titulo"])
                    db.add(registro)
                else:
                    registro.titulo = chamada["titulo"]

                texto_resumo = chamada.get("texto_listagem", "")
                valor_lista, moeda_lista = extrair_moeda_e_valor(texto_resumo)
                # Listagem pode trazer informação parcial: não apaga dado já salvo.
                campos = {
                    "regiao": extrair_regiao(texto_resumo),
                    "area_projeto": extrair_area_projeto(texto_resumo),
                    "valor": valor_lista,
                    "moeda": moeda_lista,
                }
                detalhes_ok = False
                try:
                    detalhes = buscar_detalhes_chamada_fapesp(link)
                    for nome in ("data_publicacao", "regiao", "area_projeto"):
                        if detalhes.get(nome) is not None:
                            campos[nome] = detalhes[nome]
                    if detalhes["valor"] is not None:
                        if campos["valor"] is None or detalhes["valor"] > campos["valor"]:
                            campos["valor"], campos["moeda"] = detalhes["valor"], detalhes["moeda"]
                    detalhes_ok = True
                except Exception as exc:
                    falhas.append({"link": link, "erro": str(exc)})

                # Se a listagem trouxe só um valor menor durante uma falha
                # do edital, preserve o maior montante coletado anteriormente.
                if (
                    registro.valor is not None
                    and (campos["valor"] is None or registro.valor > campos["valor"])
                ):
                    campos["valor"] = None
                    campos["moeda"] = None

                # Recalcula região/área para limpar erros de versões antigas,
                # inclusive quando o resultado correto for NULL. Se o edital
                # falhou e a listagem não trouxe dado novo, preserva o antigo.
                if detalhes_ok or campos["regiao"] is not None:
                    registro.regiao = campos["regiao"]
                if detalhes_ok or campos["area_projeto"] is not None:
                    registro.area_projeto = campos["area_projeto"]
                for nome in ("data_publicacao", "valor", "moeda"):
                    if campos.get(nome) is not None:
                        setattr(registro, nome, campos[nome])

                if nova:
                    adicionadas += 1
                else:
                    atualizadas += 1
        except Exception as exc:
            falhas.append({"link": chamada.get("link"), "erro_banco": str(exc)})

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no PostgreSQL: {exc}") from exc

    return {
        "ano": ano if ano is not None else "2020-2025",
        "encontradas": len(chamadas),
        "adicionadas": adicionadas,
        "atualizadas": atualizadas,
        "falhas": falhas,
    }


@app.get("/oportunidades")
def listar_oportunidades(db: Session = Depends(get_db)):
    return db.query(models.Oportunidade).order_by(models.Oportunidade.titulo).all()

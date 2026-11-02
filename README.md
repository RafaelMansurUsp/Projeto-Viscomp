# Scraping de Chamadas FAPESP

Projeto desenvolvido em Python para coletar, organizar e armazenar informações sobre chamadas de propostas de pesquisa publicadas pela **FAPESP**, entre 2020 e 2025.

O sistema utiliza *web scraping* para extrair informações das chamadas, uma API desenvolvida com FastAPI para executar a coleta e um banco PostgreSQL para armazenar os resultados.

## Tecnologias utilizadas

- **Python** — desenvolvimento do scraper.
- **BeautifulSoup e Requests** — extração de informações das páginas.
- **FastAPI** — disponibilização da API REST.
- **PostgreSQL** — armazenamento dos dados.
- **SQLAlchemy** — integração com o banco de dados.

## Dados coletados

Para cada chamada, são armazenados sete campos:

| Campo | Descrição |
|---|---|
| `titulo` | Título da chamada |
| `link` | URL da chamada |
| `data_publicacao` | Data de publicação |
| `regiao` | Estado(s) brasileiro(s) relacionado(s) à chamada |
| `area_projeto` | Área de conhecimento ou tema de pesquisa |
| `valor` | Maior valor monetário identificado |
| `moeda` | Moeda correspondente (BRL, USD ou EUR) |

A identificação das áreas utiliza palavras-chave, expressões e regras de contexto. Quando uma informação não pode ser identificada com segurança, o campo permanece `NULL`.

## Instalação

**1. Instale as dependências:**

```bash
pip install -r requirements.txt
```

**2. Configure o banco PostgreSQL.**

Crie um arquivo `credenciais.txt` na raiz do projeto com cinco linhas:

```text
usuario
senha
nome_do_banco
localhost
5432
```

**3. Inicie a API:**

```bash
uvicorn main:app --reload
```

A documentação interativa estará disponível em:

http://127.0.0.1:8000/docs

## Utilização

A API disponibiliza os seguintes endpoints:

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/` | Informações sobre a API |
| GET | `/oportunidades` | Lista as chamadas armazenadas |
| POST | `/scraping/fapesp` | Executa o scraping de todos os anos |
| POST | `/scraping/fapesp?ano=2023` | Executa o scraping de um ano específico |
| POST | `/scraping/fapesp?ano=2023&limite=3` | Coleta apenas três chamadas para teste |

As informações são inseridas ou atualizadas no PostgreSQL, utilizando o link de cada chamada como identificador único.

## Fontes de dados

As informações são coletadas das páginas oficiais de chamadas de propostas da FAPESP:

- [2020](https://fapesp.br/14746/chamadas-de-propostas-2020)
- [2021](https://fapesp.br/15281/chamadas-de-propostas-2021)
- [2022](https://fapesp.br/15851/chamadas-de-propostas-2022)
- [2023](https://fapesp.br/16576/chamadas-de-propostas-2023)
- [2024](https://fapesp.br/17333/chamadas-de-propostas-2024)
- [2025](https://fapesp.br/17955/chamadas-de-propostas-2025)

## Observações

- A extração utiliza regras heurísticas e pode apresentar limitações na identificação das áreas de conhecimento.
- O projeto mantém os dados em uma única tabela.
- O arquivo `credenciais.txt` contém informações sensíveis e não deve ser enviado ao repositório.
# Análise Visual de Chamadas de Propostas da FAPESP (2020–2025)

**SCC0252 / SCC5836 — Visualização Computacional — Entrega 1**

Este projeto coleta chamadas de propostas publicadas pela FAPESP, armazena os registros em PostgreSQL e produz visualizações interativas para explorar a distribuição temporal e temática das oportunidades de pesquisa.

## Questões investigadas

1. A quantidade de chamadas publicadas aumentou de 2020 a 2025? Há anos atípicos?
2. Entre as chamadas classificadas exclusivamente em **Exatas**, **Humanas** ou **Biológicas**, qual grande área aparece mais?
3. Em quais **meses do ano** houve mais publicações de chamadas, somando os anos de 2020 a 2025?

> **Definição importante:** a unidade de análise é a **chamada de propostas publicada**, não a bolsa concedida, o projeto aprovado ou a quantidade de editais simultaneamente abertos. A análise mensal usa a **data de publicação**.

## Estrutura esperada

```text
entrega1_fapesp/
├── dados/
│   └── chamadas_fapesp.csv        # Base exportada e entregue com o projeto
├── scraping.py                    # Coleta das páginas da FAPESP
├── database.py                    # Conexão com o PostgreSQL
├── models.py                      # Modelo da tabela
├── main.py                        # API FastAPI que executa o scraping
├── exportar_fapesp.py             # Exportação PostgreSQL → CSV
├── visualizar_fapesp.py           # Pré-processamento e visualizações
├── requirements.txt               # Dependências da coleta/API
├── README.md
├── credenciais.exemplo.txt        # Exemplo, sem credenciais reais (opcional)
└── resultados_entrega1/          # Criada ao gerar as visualizações
```

O arquivo `credenciais.txt` é necessário **somente para utilizar o banco e a API**. Por segurança, ele **não** deve estar no material entregue.

## 1. Requisitos e instalação

- **Python 3.10 ou superior**;
- Conexão à internet **apenas se optar por executar o scraping novamente**;
- **PostgreSQL**, **somente para recriar a coleta ou exportar novamente a base**.

Na pasta do projeto, crie e ative um ambiente virtual (exemplo para Linux/macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as bibliotecas:

```bash
python -m pip install -r requirements.txt
python -m pip install pandas plotly
```

O segundo comando instala as dependências específicas da análise visual, não presentes no `requirements.txt` original do scraping.

## 2. Execução rápida: reproduzir os gráficos sem PostgreSQL (recomendada)

**Esta é a maneira mais simples de avaliar a entrega.** A base `dados/chamadas_fapesp.csv` já acompanha os arquivos; não é necessário configurar PostgreSQL nem executar novamente a coleta.

Na raiz do projeto, execute:

```bash
python visualizar_fapesp.py --entrada dados/chamadas_fapesp.csv
```

O script realiza o pré-processamento, gera os resumos e salva os gráficos na pasta `resultados_entrega1/`. Para visualizar, abra os arquivos `.html` em um navegador (por exemplo, no Linux):

```bash
xdg-open resultados_entrega1/01_chamadas_por_ano.html
```

Os gráficos são arquivos HTML interativos e autônomos: não precisam da API em execução nem de acesso à internet para serem abertos. Também podem ser abertos por duplo clique no gerenciador de arquivos.

### Arquivos gerados

| Arquivo em `resultados_entrega1/` | Conteúdo |
|---|---|
| `01_chamadas_por_ano.html` | Gráfico de linhas: número de chamadas por ano |
| `02_chamadas_por_grande_area.html` | Barras: comparação de Exatas, Humanas e Biológicas |
| `03_chamadas_acumuladas_por_mes.html` | Barras: número de chamadas por mês, somando todos os anos |
| `04_mapa_calor_ano_mes.html` | Mapa de calor: número de chamadas para cada ano e mês |
| `chamadas_preprocessadas.csv` | Base com colunas derivadas, como ano, mês e grande área |
| `resumo_mensal.csv` | Quantidade e percentual de chamadas por mês |
| `resumo_ano_mes.csv` | Contagens mensais separadas por ano |
| `registros_para_revisao.csv` | Registros com campos ausentes ou datas fora do recorte |
| `resumo_diagnostico.txt` | Resumo da cobertura, quantidades e limitações |

Também é possível escolher outro diretório de saída:

```bash
python visualizar_fapesp.py --entrada dados/chamadas_fapesp.csv --saida resultados_teste
```

## 3. Execução completa: reproduzir o scraping e o banco (opcional)

Este procedimento demonstra como a base foi construída. **Não é necessário para visualizar os resultados da entrega**, pois o CSV já é disponibilizado. A coleta depende da disponibilidade e da estrutura atual das páginas oficiais; uma nova execução pode produzir resultados diferentes.

### 3.1. Criar o banco PostgreSQL

Inicie o serviço PostgreSQL e crie um banco de dados vazio, pelo pgAdmin ou pelo terminal. Exemplo com a ferramenta `createdb` (substitua os parâmetros):

```bash
createdb -h localhost -U SEU_USUARIO NOME_DO_BANCO
```

Crie o arquivo `credenciais.txt` **na mesma pasta de `database.py`**, contendo exatamente cinco linhas, nesta ordem:

```text
SEU_USUARIO
SUA_SENHA
NOME_DO_BANCO
localhost
5432
```

O arquivo é local e não deve ser incluído em repositórios ou na submissão. Se a instalação utilizar outro host ou porta, ajuste as duas últimas linhas.

### 3.2. Iniciar a API

Com o ambiente virtual ativo, execute na pasta do projeto:

```bash
uvicorn main:app --reload
```

Abra a documentação da API no navegador:

```text
http://127.0.0.1:8000/docs
```

Ao importar `main.py`, o SQLAlchemy cria a tabela `oportunidades_2025`, caso ela ainda não exista. **A inicialização não cria o banco de dados em si:** ele precisa existir previamente. Se a tabela já existir com outra estrutura, o aplicativo interrompe a inicialização para evitar alterações automáticas.

### 3.3. Executar a coleta

Na interface `/docs`, utilize **POST `/scraping/fapesp`**. Para testar com poucas chamadas:

```bash
curl -X POST 'http://127.0.0.1:8000/scraping/fapesp?ano=2025&limite=3'
```

Para coletar todos os anos configurados (2020–2025):

```bash
curl -X POST 'http://127.0.0.1:8000/scraping/fapesp'
```

A coleta pode levar algum tempo, pois acessa cada página de chamada. Os registros são inseridos ou atualizados usando a URL como chave primária, evitando duplicações por esse identificador.

A resposta da API informa `encontradas`, `adicionadas`, `atualizadas` e `falhas`. Para registrar a resposta completa da execução, execute, por exemplo:

```bash
curl -sS -X POST 'http://127.0.0.1:8000/scraping/fapesp?ano=2025&limite=3' -o resposta_scraping_teste.json
```

**Importante:** o campo `falhas` informa problemas de requisição ou processamento naquela execução. Esses eventos não são armazenados na tabela exportada para CSV.

Também é possível consultar os registros pelo endpoint **GET `/oportunidades`**.

### 3.4. Exportar e gerar os gráficos novamente

Com o PostgreSQL configurado e o banco populado, abra outro terminal, ative o mesmo ambiente e execute:

```bash
python exportar_fapesp.py
python visualizar_fapesp.py --entrada dados/chamadas_fapesp.csv
```

O primeiro comando atualiza o CSV `dados/chamadas_fapesp.csv` a partir da tabela do PostgreSQL. O segundo gera novamente as visualizações e os relatórios de diagnóstico.

> Se quiser manter exatamente a base original utilizada na entrega, **faça uma cópia do CSV fornecido antes de reexportar**: a exportação sobrescreve `dados/chamadas_fapesp.csv`.

## 4. Dados coletados e pré-processamento

O scraper lê as listagens históricas da FAPESP de **2020 a 2025** e as páginas individuais dos editais. Cada registro possui os seguintes campos:

| Campo | Descrição |
|---|---|
| `titulo` | Título da chamada |
| `link` | URL; chave primária no banco |
| `data_publicacao` | Data identificada na página |
| `regiao` | Abrangência territorial identificada |
| `area_projeto` | Área(s) ou tema(s) detectado(s) |
| `valor` | Maior montante monetário detectado no texto |
| `moeda` | Moeda correspondente, quando reconhecida |

O script de visualização remove registros duplicados por URL, interpreta as datas e deriva as variáveis `ano`, `mes`, `mes_nome` e `grande_area`.

A classificação das grandes áreas é uma **regra analítica do projeto**, não uma classificação oficial publicada pela FAPESP. O gráfico comparativo inclui apenas chamadas atribuídas exclusivamente a Exatas, Humanas ou Biológicas. Chamadas mistas, transversais ou abertas a todas as áreas são agrupadas como `Interdisciplinar` para essa análise; casos não identificáveis ficam em `Sem classificação`.

Para os gráficos anuais e mensais, entram somente registros com **data de publicação entre 2020 e 2025**. Registros sem data ou fora do recorte são preservados na base, mas não entram nessas contagens. O gráfico de áreas não exige data válida.

Os campos `valor` e `moeda` **permanecem no scraping, no banco e no CSV**, mas não participam das análises visuais desta entrega. O maior valor encontrado no texto de um edital não representa necessariamente o orçamento da chamada ou o limite de financiamento por projeto.

## 5. Limitações e qualidade da coleta

- Nem toda informação está presente de forma explícita nas páginas de origem; valores ausentes não são automaticamente falhas do programa.
- A extração de áreas e valores usa regras heurísticas, sujeitas a classificações incompletas ou incorretas.
- A análise temporal se refere à **publicação de chamadas**, não ao intervalo de inscrições abertas e nem ao número de bolsas efetivamente concedidas.
- Falhas de acesso e processamento podem aparecer na resposta da API, mesmo que não sejam visíveis no CSV.
- A ausência de data e a cobertura desigual dos anos podem afetar as conclusões sobre tendência e sazonalidade.

O projeto disponibiliza `registros_para_revisao.csv` e `resumo_diagnostico.txt` para tornar essas limitações verificáveis.

## 6. Solução rápida de problemas

| Sintoma | Verificação |
|---|---|
| `CSV não encontrado` | Confirme que o arquivo existe em `dados/chamadas_fapesp.csv` ou informe `--entrada` com o caminho correto. |
| `ModuleNotFoundError: pandas` ou `plotly` | Ative `.venv` e execute `python -m pip install pandas plotly`. |
| `ModuleNotFoundError: database` | Para exportar, mantenha `exportar_fapesp.py` na pasta de `database.py`. A visualização com CSV não utiliza esse módulo. |
| Erro em `credenciais.txt` | Necessário apenas para banco/API; confirme as cinco linhas e o nome do banco existente. |
| Banco aceita conexão, mas a API falha ao iniciar | Confira a existência do banco e se a tabela antiga possui as colunas esperadas. |

## Tecnologias utilizadas

**Python, Requests, BeautifulSoup, FastAPI, SQLAlchemy, PostgreSQL, Pandas e Plotly.**

---

**Fontes:** listagens históricas de chamadas de propostas da FAPESP (2020–2025), acessadas pelo módulo `scraping.py`.

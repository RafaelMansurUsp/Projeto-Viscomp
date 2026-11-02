"""Scraping de chamadas históricas da FAPESP (2020 a 2025).

Não confunde a data de publicação da listagem com a de cada chamada.
Somente dados explícitos são persistidos; campos incertos permanecem None.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Páginas históricas: para incluir mais um ano, adicione a URL aqui.
URLS_CHAMADAS_FAPESP = {
    2020: "https://fapesp.br/14746/chamadas-de-propostas-2020",
    2021: "https://fapesp.br/15281/chamadas-de-propostas-2021",
    2022: "https://fapesp.br/15851/chamadas-de-propostas-2022",
    2023: "https://fapesp.br/16576/chamadas-de-propostas-2023",
    2024: "https://fapesp.br/17333/chamadas-de-propostas-2024",
    2025: "https://fapesp.br/17955/chamadas-de-propostas-2025",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PesquisaAcademicaFAPESP/1.0)"}
# O ano é capturado do número da chamada. Há inclusive uma chamada
# marcada como 13/2022 dentro da lista de 2023; não ignorá-la.
PADRAO_NUMERO = re.compile(r"\bChamada\s+FAPESP\s*(\d{1,2})\s*/\s*(20\d{2})\b", re.I)
MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# Áreas gerais oficialmente utilizadas pela FAPESP, identificadas por menção
# explícita; não há classificação automática baseada em assunto/palavras-chave.
AREAS = (
    "Ciências Exatas e da Terra", "Ciências Sociais Aplicadas",
    "Linguística, Letras e Artes", "Ciências Biológicas", "Ciências Agrárias",
    "Ciências da Saúde", "Ciências Humanas", "Engenharias", "Interdisciplinar",
)

ESTADOS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM",
    "bahia": "BA", "ceara": "CE", "distrito federal": "DF",
    "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso do sul": "MS", "mato grosso": "MT", "minas gerais": "MG",
    "para": "PA", "paraiba": "PB", "parana": "PR", "pernambuco": "PE",
    "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}


def limpar(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def sem_acentos(texto):
    normalizado = unicodedata.normalize("NFD", limpar(texto))
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn").lower()


def requisitar_pagina_fapesp(url):
    """Segue redirecionamentos HTTP e meta refresh da FAPESP."""
    for _ in range(5):
        resposta = requests.get(url, headers=HEADERS, timeout=25)
        resposta.raise_for_status()
        if "html" not in resposta.headers.get("Content-Type", "text/html").lower():
            raise ValueError(f"Conteúdo não HTML: {resposta.url}")
        soup = BeautifulSoup(resposta.content, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)})
        if meta is None:
            return resposta
        match = re.search(r"url\s*=\s*['\"]?([^'\";]+)", meta.get("content", ""), re.I)
        if not match:
            return resposta
        seguinte = urljoin(resposta.url, match.group(1).strip())
        if seguinte == resposta.url:
            return resposta
        url = seguinte
    raise ValueError("Limite de redirecionamentos meta refresh excedido")


def conteudo_da_pagina(soup):
    return (
        soup.select_one("main.container.int-body div.page-body")
        or soup.select_one("main.container.int-body")
        or soup.select_one("main")
        or soup
    )


def linhas_do_html(elemento):
    return [limpar(linha) for linha in elemento.get_text("\n").splitlines() if limpar(linha)]


def interpretar_bloco(numero, ano_edital, titulo, link, linhas):
    """Extrai o resumo de uma chamada sem adicionar campos ao banco."""
    resumo = []
    for linha in linhas:
        normal = sem_acentos(linha)
        if normal.startswith("apoio:") or normal.startswith("resultado"):
            break
        resumo.append(linha)
    return {
        "numero": f"{int(numero):02d}/{ano_edital}",  # controle interno
        "titulo": titulo,
        "link": link,
        "texto_listagem": titulo + "\n" + " ".join(resumo),
    }


def _extrair_por_itens(conteudo, base):
    resultado = []
    for li in conteudo.find_all("li"):
        linhas = linhas_do_html(li)
        marcadores = [(i, m) for i, linha in enumerate(linhas)
                     if (m := PADRAO_NUMERO.search(linha))]
        if len(marcadores) != 1:
            continue
        indice, marcador = marcadores[0]
        numero, ano_edital = marcador.groups()
        links = [a for a in li.find_all("a", href=True)
                 if "resultado" not in sem_acentos(a.get_text(" ", strip=True))]
        if not links:
            continue
        titulo = limpar(links[0].get_text(" ", strip=True))
        link = urljoin(base, links[0]["href"])
        if titulo and urlparse(link).scheme in ("http", "https"):
            resultado.append(interpretar_bloco(numero, ano_edital, titulo, link, linhas[indice + 1:]))
    return resultado


def _extrair_por_texto(conteudo, base):
    """Fallback para versões das páginas sem <li> por chamada."""
    linhas = linhas_do_html(conteudo)
    links = {}
    for a in conteudo.find_all("a", href=True):
        nome = limpar(a.get_text(" ", strip=True))
        if nome:
            links.setdefault(sem_acentos(nome), (nome, urljoin(base, a["href"])))
    marcadores = []
    for pos, linha in enumerate(linhas):
        match = PADRAO_NUMERO.search(linha)
        if not match:
            continue
        for anterior in range(pos - 1, max(-1, pos - 12), -1):
            candidato = links.get(sem_acentos(linhas[anterior]))
            if candidato and "resultado" not in sem_acentos(candidato[0]):
                marcadores.append((pos, anterior, match.group(1), match.group(2), *candidato))
                break
    resultado = []
    for i, (pos, _, numero, ano_edital, titulo, link) in enumerate(marcadores):
        fim = marcadores[i + 1][1] if i + 1 < len(marcadores) else len(linhas)
        resultado.append(interpretar_bloco(numero, ano_edital, titulo, link, linhas[pos + 1:fim]))
    return resultado


def buscar_chamadas_fapesp(ano=None):
    """Busca as chamadas históricas de 2020 a 2025, ou só do ano informado.

    A URL é usada para evitar repetir uma chamada que conste em mais
    de uma listagem. Os sete campos persistidos não são modificados.
    """
    if ano is not None and ano not in URLS_CHAMADAS_FAPESP:
        raise ValueError(f"Ano inválido: {ano}. Use um dos anos: {sorted(URLS_CHAMADAS_FAPESP)}")

    anos = [ano] if ano is not None else sorted(URLS_CHAMADAS_FAPESP, reverse=True)
    todas = []
    urls_vistas = set()

    for ano_fonte in anos:
        resposta = requisitar_pagina_fapesp(URLS_CHAMADAS_FAPESP[ano_fonte])
        conteudo = conteudo_da_pagina(BeautifulSoup(resposta.content, "html.parser"))
        itens = _extrair_por_itens(conteudo, resposta.url)
        texto = _extrair_por_texto(conteudo, resposta.url)
        resultado = itens if len(itens) >= len(texto) else texto
        if not resultado:
            raise ValueError(f"Nenhuma chamada reconhecida na listagem de {ano_fonte}")

        # Ordena por número dentro da página de origem, sem exigir que
        # o ano do número seja idêntico ao ano da página histórica.
        resultado.sort(key=lambda chamada: int(chamada["numero"].split("/")[0]), reverse=True)
        for chamada in resultado:
            parsed = urlparse(chamada["link"])
            chave_url = (parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query)
            if chave_url not in urls_vistas:
                urls_vistas.add(chave_url)
                todas.append(chamada)

    return todas


def normalizar_data(texto):
    """Converte DD/MM/AAAA ou '7 de julho de 2025' para date."""
    if not texto:
        return None
    texto = sem_acentos(texto)
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", texto)
    if match:
        dia, mes, ano = map(int, match.groups())
    else:
        match = re.search(
            rf"\b(\d{{1,2}})\s+de\s+({'|'.join(MESES)})\s+de\s+(\d{{4}})\b", texto
        )
        if not match:
            return None
        dia, mes, ano = int(match[1]), MESES[match[2]], int(match[3])
    try:
        return datetime(ano, mes, dia).date()
    except ValueError:
        return None


def extrair_data_publicacao(texto_cabecalho):
    """Lê 'Publicada em ...' do cabeçalho da chamada, nunca da listagem."""
    match = re.search(
        r"\bPublicada\s+em\s+((?:\d{1,2}/\d{1,2}/\d{4})|"
        r"(?:\d{1,2}\s+de\s+\w+\s+de\s+\d{4}))\b",
        texto_cabecalho, re.I,
    )
    return normalizar_data(match.group(1)) if match else None


def _converter_numero(numero):
    numero = numero.strip().rstrip(".,")
    if "," in numero and "." in numero:
        numero = (numero.replace(".", "").replace(",", ".")
                  if numero.rfind(",") > numero.rfind(".") else numero.replace(",", ""))
    elif "," in numero:
        partes = numero.split(",")
        numero = numero.replace(",", "") if len(partes[-1]) == 3 else numero.replace(",", ".")
    elif "." in numero and all(len(x) == 3 for x in numero.split(".")[1:]):
        numero = numero.replace(".", "")
    return Decimal(numero)


_ESCALA = r"(?:bilh(?:ao|oes)|billions?|milh(?:ao|oes)|millions?|mil|thousand)"
_NUM = r"\d[\d.,]*"
_MOEDA = r"(?:R\s*\$|US\s*\$|€|\bBRL\b|\bUSD\b|\bEUR\b|\breais\b|\breal\b|\bdolares?\b|\bdollars?\b|\beuros?\b)"
# Depois de remover acentos, 'milhões' vira 'milhoes'.
_PADRAO_MONETARIO = re.compile(
    rf"(?P<moeda_antes>{_MOEDA})\s*(?P<numero_antes>{_NUM})\s*(?P<escala_antes>{_ESCALA})?"
    rf"|(?P<numero_depois>{_NUM})\s*(?P<escala_depois>{_ESCALA})?\s+(?:de\s+)?(?P<moeda_depois>{_MOEDA})",
    re.I,
)


def _codigo_moeda(texto):
    moeda = sem_acentos(texto).replace(" ", "")
    if moeda in {"r$", "brl", "real", "reais"}:
        return "BRL"
    if moeda in {"us$", "usd", "dolar", "dolares", "dollar", "dollars"}:
        return "USD"
    if moeda in {"€", "eur", "euro", "euros"}:
        return "EUR"
    return None


def extrair_moeda_e_valor(texto):
    """Retorna o maior valor numérico explícito com moeda BRL, USD ou EUR.

    Cada montante é convertido para sua unidade (p.ex. 2 milhões -> 2000000).
    Não faz conversão cambial: se houver moedas diferentes, vence o maior
    número absoluto, não necessariamente o maior poder de compra.
    """
    normal = sem_acentos(texto)
    valores = []
    for match in _PADRAO_MONETARIO.finditer(normal):
        numero = match.group("numero_antes") or match.group("numero_depois")
        escala = match.group("escala_antes") or match.group("escala_depois") or ""
        moeda = _codigo_moeda(match.group("moeda_antes") or match.group("moeda_depois"))
        if not moeda:
            continue
        try:
            valor = _converter_numero(numero)
            escala = sem_acentos(escala)
            if escala.startswith(("bilh", "bill")):
                valor *= 1_000_000_000
            elif escala.startswith(("milh", "mill")):
                valor *= 1_000_000
            elif escala in {"mil", "thousand"}:
                valor *= 1_000
            if valor.is_finite():
                valores.append((valor, moeda))
        except InvalidOperation:
            continue
    if not valores:
        return None, None
    maior, moeda = max(valores, key=lambda item: item[0])
    return maior, moeda


# Vocabulário revisado a partir de chamadas FAPESP de 2020 a 2025.
# Chave = área/tema exibido no banco. Valores = expressões equivalentes
# ENCONTRADAS NO TEXTO (não se deduz uma área só porque o assunto parece afim).
# Usar nomes específicos antes de categorias mais amplas é importante.
# Para ampliar o vocabulário, acrescente uma chave e suas variantes abaixo.
PALAVRAS_CHAVE_AREAS = {
    # Grandes áreas
    "Ciências Exatas e da Terra": ("ciencias exatas e da terra",),
    "Ciências Sociais Aplicadas": ("ciencias sociais aplicadas",),
    "Ciências Humanas e Sociais": ("ciencias humanas e sociais", "human and social sciences"),
    "Ciências Humanas": ("ciencias humanas",),
    "Ciências Biológicas": ("ciencias biologicas",),
    "Ciências Agrárias": ("ciencias agrarias",),
    "Ciências da Saúde": ("ciencias da saude",),
    "Ciências da Vida": ("ciencias da vida", "life sciences"),
    "Ciências Ambientais": ("ciencias ambientais", "environmental sciences"),
    "Ciências Sociais e Jurídicas": ("ciencias sociais e juridicas",),
    "Ciências Agrárias e Ambientais": ("ciencias agrarias e ambientais",),
    "Engenharias": ("engenharias",),
    "Engenharia": ("engenharia", "engineering"),
    "Engenharia e Arquitetura": ("engenharia e arquitetura",),
    "Linguística, Letras e Artes": ("linguistica, letras e artes",),
    "Linguagem, Comunicação e Artes": ("linguagem, comunicacoes e/ou artes", "linguagem, comunicacao e artes", "linguagem, comunicacoes e artes"),
    "Artes e Humanidades": ("artes e humanidades",),
    # Computação, matemática e física
    "Ciência da Computação": ("ciencia da computacao", "computer science"),
    "Inteligência Artificial": ("inteligencia artificial", "artificial intelligence", "ia generativa", "generative ai"),
    "Ciência de Dados": ("ciencia de dados", "data science"),
    "Matemática Aplicada": ("matematica aplicada", "applied mathematics"),
    "Matemática": ("matematica", "mathematics"),
    "Estatística": ("estatistica", "statistics"),
    "Tecnologias Quânticas": ("tecnologias quanticas", "tecnologia quantica", "quantum technologies", "quantum technology"),
    "Computação Quântica": ("computacao quantica", "quantum computing"),
    "Comunicações Quânticas": ("comunicacoes quanticas", "comunicacao quantica", "quantum communication"),
    "Sensoriamento Quântico": ("sensoriamento quantico", "quantum sensing"),
    "Física": ("fisica", "physics"),
    "Astrofísica": ("astrofisica", "astrophysics"),
    "Astronomia": ("astronomia", "astronomico", "astronomica", "astronomy"),
    "Geociências": ("geociencias", "geosciences"),
    "Ciências Espaciais": ("ciencias espaciais", "space science", "space sciences"),
    "Ciências Terrestres": ("ciencias terrestres", "earth sciences", "earth science"),
    "Ciências Polares": ("ciencias polares", "polar sciences", "polar research"),
    "Meteorologia": ("meteorologia", "ciencias atmosfericas", "atmosfericas", "atmospheric sciences", "meteorology"),
    "Ciência de Materiais e Engenharia": ("ciencia de materiais e engenharia", "ciencia dos materiais e engenharia", "materials science and engineering"),
    "Ciência de Materiais": ("ciencia de materiais", "ciencia dos materiais", "materials science"),
    "Materiais Avançados": ("materiais avancados", "advanced materials"),
    "Nanotecnologia": ("nanotecnologia", "nanotechnology"),
    "Telecomunicações": ("telecomunicacoes", "telecommunications", "tecnologia 5g", "redes 5g", "5g"),
    "Internet e Redes": ("pesquisa estrategica sobre a internet", "tecnologias viabilizadoras da internet", "aplicacoes avancadas da internet", "internet e redes", "internet das coisas"),
    "Segurança da Informação": ("seguranca da informacao", "cybersecurity", "ciberseguranca"),
    "Software Livre e Dados Abertos": ("software livre, dados abertos", "software livre", "dados abertos", "open source software"),
    # Vida, saúde e biologia
    "Saúde": ("saude", "health"),
    "Saúde Pública": ("saude publica", "public health", "sistemas de saude", "health systems"),
    "Saúde Global": ("saude global", "global health"),
    "Saúde Mental": ("saude mental", "mental health"),
    "Doenças Crônicas": ("doencas cronicas", "doencas nao transmissiveis", "chronic diseases", "noncommunicable diseases", "non-communicable diseases"),
    "Doenças Infecciosas": ("doencas infecciosas", "infectious diseases"),
    "Medicina Personalizada": ("medicina personalizada", "personalised medicine", "personalized medicine"),
    "Medicina Computacional": ("medicina computacional", "computational medicine"),
    "Biomedicina": ("biomedicina", "biomedicine"),
    "Biotecnologia": ("biotecnologia", "biotechnology"),
    "Bioinformática": ("bioinformatica", "bioinformatics"),
    "Genômica": ("genomica", "genomics", "sequenciamento genomico", "genomas"),
    "Genética": ("genetica", "genetics"),
    "Biologia Molecular": ("biologia molecular", "molecular biology"),
    "Neurociências": ("neurociencias", "neurosciences", "neuroscience"),
    "Microbiologia": ("microbiologia", "microbiology"),
    "Oncologia": ("oncologia", "oncology", "cancer research"),
    "Epidemiologia": ("epidemiologia", "epidemiology"),
    "Gripe Aviária": ("gripe aviaria", "avian influenza"),
    "Covid-19": ("covid-19", "sars-cov-2"),
    "Taxonomia Biológica": ("taxonomia biologica", "biological taxonomy"),
    # Ambiente, recursos naturais, clima
    "Biodiversidade": ("biodiversidade", "biodiversity"),
    "Ecologia": ("ecologia", "ecology", "ecologia de ecossistemas", "ecological research", "pesquisa ecologica de longa duracao"),
    "Conservação Ambiental": ("conservacao ambiental", "conservacao de biodiversidade", "conservacao da biodiversidade", "unidades de conservacao", "conservacao das unidades de conservacao"),
    "Serviços Ecossistêmicos": ("servicos ecossistemicos", "ecosystem services"),
    "Mudança de Uso da Terra": ("uso e ocupacao da terra", "mudancas no uso da terra", "land use change"),
    "Restauração de Ecossistemas": ("restauracao de ecossistemas", "restauracao de ecossistemas", "ecosystem restoration", "restoration of ecosystems"),
    "Restauração da Natureza": ("restauracao da natureza", "nature restoration"),
    "Mudanças Climáticas": ("mudancas climaticas", "mudanca do clima", "alteracoes climaticas", "climate change", "climate changes"),
    "Eventos Climáticos Extremos": ("eventos climaticos extremos", "eventos extremos de calor e agua", "extreme weather", "extreme heat events"),
    "Florestas Tropicais": ("florestas tropicais", "tropical forests"),
    "Desmatamento": ("desmatamento", "deforestation"),
    "Sustentabilidade": ("sustentabilidade", "sustainability"),
    "Bioeconomia": ("bioeconomia", "bioeconomy"),
    "Economia Circular": ("economia circular", "circular economy"),
    "Resíduos Sólidos": ("residuos solidos", "solid waste"),
    "Agropecuária": ("agropecuaria", "agricultura e pecuaria", "farming and livestock"),
    "Agricultura": ("agricultura", "agricultural research"),
    "Agricultura Familiar": ("agricultura familiar", "family farming"),
    "Segurança Alimentar": ("seguranca alimentar", "food security"),
    "Sistemas Alimentares Saudáveis": ("sistemas alimentares saudaveis", "healthy food systems"),
    "Recursos Hídricos": ("recursos hidricos", "qualidade da agua", "water resources", "water quality", "seguranca hidrica"),
    "Saneamento": ("saneamento", "sanitation"),
    "Ciências do Mar": ("ciencias do mar", "ciencias marinhas", "ciencias do oceano", "ciencia oceanica", "ciencias oceanicas", "marine sciences", "ocean sciences", "ocean science", "oceanografia fisica"),
    "Oceanografia": ("oceanografia", "oceanography"),
    "Tecnologia dos Oceanos": ("tecnologia dos oceanos", "ocean technology"),
    "Economia Azul Sustentável": ("economia azul sustentavel", "sustainable blue economy", "blue economy"),
    "Poluição Marinha": ("poluicao marinha", "marine pollution"),
    # Energia e engenharia aplicada
    "Energia": ("energia", "energy"),
    "Transição Energética": ("transicao energetica", "energy transition"),
    "Bioenergia": ("bioenergia", "bioenergy"),
    "Biocombustíveis": ("biocombustiveis", "biofuels"),
    "Energias Renováveis": ("energias renovaveis", "energia renovavel", "renewable energy"),
    "Hidrogênio Verde": ("hidrogenio verde", "green hydrogen"),
    "Petróleo e Gás": ("petroleo e gas", "oil and gas"),
    # Humanas, linguagem e políticas públicas
    "Educação Básica": ("educacao basica", "educacao publica", "basic education", "educacao escolar", "educacao basica publica"),
    "Educação Profissional": ("educacao profissional", "vocational education"),
    "Ensino e Aprendizagem": ("ensino e aprendizagem", "teaching and learning"),
    "Políticas Públicas": ("politicas publicas", "public policies", "public policy"),
    "Políticas Educacionais": ("politicas educacionais", "politicas publicas educacionais", "education policy"),
    "Democracia e Cidadania": ("democracia e cidadania", "democracy and citizenship"),
    "Desigualdades Sociais": ("desigualdades sociais", "social inequalities"),
    "Segurança Pública": ("seguranca publica", "public security", "policiamento"),
    "Conhecimentos Indígenas": ("conhecimento indigena", "conhecimentos indigenas", "indigenous knowledge"),
    "Economia": ("economia", "economics"),
    "Administração": ("administracao", "management sciences"),
    "Psicologia": ("psicologia", "psychology"),
    "Antropologia": ("antropologia", "anthropology"),
    "Ciência Política": ("ciencia politica", "political science"),
    "Sociologia": ("sociologia", "sociology"),
    "História": ("historia do brasil", "historia", "history"),
    "Arqueologia": ("arqueologia", "archaeology"),
    "Linguística": ("linguistica", "linguistics"),
    "Comunicação": ("comunicacao", "communication"),
    "Divulgação Científica": ("divulgacao cientifica", "comunicacao cientifica", "comunicar ciencia", "science communication"),
    "Migração Humana": ("migracao humana", "mobilidade humana", "human migration", "human mobility", "human migration/mobility"),
    "Democracia e Governança": ("democracy, governance and trust", "democracia e governanca", "democracy and governance"),
    "Artes": ("artes", "arts"),
    "Cultura Digital": ("cultura digital", "digital culture"),
    "Patrimônio Cultural": ("patrimonio cultural", "cultural heritage", "curadoria digital e patrimonio"),
    "Acervos Museológicos, Bibliográficos e Arquivísticos": ("acervos museologicos, bibliograficos e arquivisticos",),
    "Coleções Biológicas": ("colecoes biologicas",),
    "Urbanismo": ("urbanismo", "centros urbanos", "planejamento urbano", "urban planning", "urban transitions"),
    "Mobilidade Urbana": ("mobilidade urbana", "urban mobility"),
    "Turismo": ("turismo", "tourism"),
}

# Compilar uma única vez: o scraper visita centenas de páginas por execução.
_PADROES_CHAVES_AREAS = [
    (
        area,
        re.compile(r"(?<!\w)" + re.escape(sem_acentos(alias)).replace(r"\ ", r"\s+") + r"(?!\w)"),
    )
    for area, aliases in PALAVRAS_CHAVE_AREAS.items()
    for alias in aliases
]

# Algumas siglas identificam PROGRAMAS DE ESCOPO CONHECIDO, não uma área
# inferida a partir de uma mera menção em qualquer parte do texto. Elas só
# valem no TÍTULO da chamada, para evitar falsos positivos em anexos/rodapés.
# Não mapear PIPE, PITE, SPRINT, CEPID, FAPESP ou CNPq, pois não delimitam área.
PROGRAMAS_TEMATICOS = (
    (r"\bbiota\b|\bbiodiversa\+?\b", "Biodiversidade"),
    (r"\bm[\s-]?era[\s.]?net\b", "Ciência de Materiais e Engenharia"),
    (r"\bera[\s-]?permed\b", "Medicina Personalizada"),
    (r"\bproeduca\b", "Educação Básica"),
    (r"\bprotax\b", "Taxonomia Biológica"),
    (r"\bpeld\b", "Ecologia"),
    (r"\bqutia\b", "Tecnologias Quânticas"),
    (r"\bbioen\b", "Bioenergia"),
    (r"\bproasa\b", "Ciências do Mar"),
    (r"\bwater4all\b", "Recursos Hídricos"),
    (r"\bsbep\b", "Economia Azul Sustentável"),
    (r"\bgacd\b", "Doenças Crônicas"),
    (r"\blincar\b", "Linguagem, Comunicação e Artes"),
    (r"\bbocp\b", "Biodiversidade"),
    (r"\bnerc\b", "Ciências Ambientais"),
    (r"\blsst\b", "Astronomia"),
    (r"\bprograma de leitorado\b", "Linguística"),
    (r"\bglobal environment facility\b", "Ciências Ambientais"),
    (r"\bfulbright.{0,35}ruth cardoso\b|\bcat[eé]dra.{0,25}ruth cardoso\b", "Ciências Humanas e Sociais"),
)

# Evidência de escopo: título, seção de áreas ou parágrafo que delimita
# explicitamente o objeto da chamada. Jamais varrer o edital inteiro buscando
# palavras como "saúde" ou "energia": isso gera falsos positivos.
_ROTULO_AREA = re.compile(
    r"^(?:\d+(?:\.\d+)*[.)]?\s*)?"
    r"(?:"
    r"areas?(?:\s+(?:do|de|da)\s+(?:conhecimento|pesquisa|atuacao|interesse))?"
    r"(?:\s+(?:contempladas?|elegiveis|prioritarias?|na\s+chamada|no\s+edital))*"
    r"|areas?\s+tematicas?(?:\s+(?:elegiveis|prioritarias?|contempladas?|e\s+prioritarias?))*"
    r"|eixos?(?:\s+(?:tematicos?|estrategicos?|prioritarios?))+"
    r"|linhas?\s+(?:de\s+)?pesquisa(?:\s+prioritarias?)?"
    r"|temas?(?:\s+(?:de\s+pesquisa|das?\s+propostas|prioritarios?|elegiveis?|sugeridos))+"
    r"|escopo(?:\s+de\s+pesquisa|\s+tematico)?"
    r"|research\s+(?:areas?|topics?|themes?)"
    r"|priority\s+(?:areas?|topics?)"
    r")"
    r"(?:\s+(?:do|da|de|na)\s+(?:conhecimento|chamada|edital))?"
    r"(?:\s*:\s*.*)?$", re.I,
)

# Títulos administrativos indicam o fim da seção e não são áreas.
_SECAO_ADMIN = re.compile(
    r"^(?:\d+(?:\.\d+)*[.)]?\s*)?"
    r"(?:financiamento|fomento|recursos|duracao|apoio|modalidade|"
    r"criterios|elegibilidade|procedimentos|submissao|cronograma|"
    r"calendario|contato|avaliacao|propriedade intelectual|"
    r"documentacao|anexos|informacoes|despesas|resultados|"
    r"prazos?|funding|budget|preparacao da proposta|"
    r"introducao|objetivos?|justificativa|resumo|estrutura\s+da\s+proposta|"
    r"participacao|requisitos|condicoes\s+gerais|criterios\s+de\s+selecao)\b", re.I,
)

_TODAS_AREAS = re.compile(
    r"\b(?:todas\s+as\s+areas\s+do\s+conhecimento|"
    r"(?:em|de|a|para)\s+qualquer\s+(?:area\s+do\s+conhecimento|disciplina)|"
    r"(?:aberta|abertas|aberto|abertos)\s+(?:a|as|para)\s+todas\s+as\s+areas|"
    r"all\s+(?:scientific\s+)?(?:disciplines|fields\s+of\s+(?:research|science)))\b",
    re.I,
)
_INTERDISCIPLINAR = re.compile(r"\binterdisciplina(?:r|res)\b", re.I)

# Vocabulário pequeno demais poderia não identificar uma área; mas um
# vocabulário grande sem evidência de ESCOPO identificaria dezenas erradas.
def _termos_mencionados(texto):
    """Reconhece nomes de área explícitos, com limites de palavra e sem sobreposição."""
    normal = sem_acentos(texto)
    ocorrencias = []
    for area, padrao in _PADROES_CHAVES_AREAS:
        for m in padrao.finditer(normal):
            ocorrencias.append((m.start(), m.end(), area))
    # Ocorrências específicas ("educação básica") se sobrepõem às genéricas
    # ("educação"); manter somente a mais longa no mesmo ponto do texto.
    ocorrencias.sort(key=lambda o: (-(o[1] - o[0]), o[0]))
    escolhidas = []
    for inicio, fim, area in ocorrencias:
        if not any(inicio < e and fim > i for i, e, _ in escolhidas):
            escolhidas.append((inicio, fim, area))
    return list(dict.fromkeys(area for _, _, area in sorted(escolhidas)))


def _temas_por_programa(titulo):
    normal = sem_acentos(titulo)
    return list(dict.fromkeys(
        area for padrao, area in PROGRAMAS_TEMATICOS
        if re.search(padrao, normal, re.I)
    ))


def _itens_area(texto):
    """Encontra nomes conhecidos APENAS dentro de seções que declaram áreas."""
    linhas = [limpar(l) for l in (texto or "").splitlines() if limpar(l)]
    encontrados = []
    for i, linha in enumerate(linhas):
        normal = sem_acentos(linha)
        if not _ROTULO_AREA.match(normal):
            continue
        # Evita tratar parágrafos como se fossem títulos de seção.
        if len(linha) > 115 and ":" not in linha[:65]:
            continue
        trecho_inline = linha.split(":", 1)[1] if ":" in linha else ""
        bloco = [trecho_inline] if trecho_inline else []
        for prox in linhas[i + 1:i + 38]:
            ns = sem_acentos(prox)
            if _SECAO_ADMIN.match(ns) or _ROTULO_AREA.match(ns):
                break
            # Uma próxima seção numerada com título não deve contaminar a lista.
            if re.match(r"^\d+(?:\.\d+)+[.)]?\s+\S+", ns) and re.search(
                r"\b(?:elegibilidade|submissao|criterios|anexos|fomento|"
                r"modalidade|cronograma|resultados)\b", ns):
                break
            if ("http" in ns or "www." in ns or re.search(
                    r"(?:r\$|us\$|€|\b(?:brl|usd|eur)\b)", ns)):
                continue
            # Dentro de área explicitamente rotulada, frases de até 600 chars
            # são examinadas para localizar NOMES, nunca retornadas inteiras.
            if len(prox) <= 600:
                bloco.append(prox)
        for candidato in bloco:
            encontrados.extend(_termos_mencionados(candidato))
    return list(dict.fromkeys(encontrados))


def _escopo_todas_areas(texto):
    """Distingue chamada aberta a qualquer área de texto sobre pareceristas."""
    for linha in (texto or "").splitlines():
        normal = sem_acentos(linha)
        for match in _TODAS_AREAS.finditer(normal):
            antes = normal[max(0, match.start() - 160):match.start()]
            depois = normal[match.end():match.end() + 65]
            if re.match(r"\s*(?:relacionadas?|ligadas?|associadas?|voltadas?)\b", depois):
                continue
            if re.search(r"\b(?:painelistas?|pareceristas?|membros externos|"
                         r"assessoria cientifica|avaliadores?)\b", antes):
                continue
            if re.search(r"\b(?:chamada|edital|propostas?|pesquisas?|"
                         r"disciplinas?|escolas|areas?|projetos?|recebimento|"
                         r"contemplar?|elegiveis|aceit[ao]s?|abert[ao]s?|"
                         r"poderao|participar)\b", antes):
                return True
    return False


def _areas_no_escopo(texto):
    """Busca áreas em frases do OBJETIVO da chamada, sem varrer referências."""
    linhas = [limpar(l) for l in (texto or "").splitlines() if limpar(l)]
    relevantes = []
    # Tolerar sumários, menus e introduções curtas antes da descrição.
    for linha in linhas[:110]:
        normal = sem_acentos(linha)
        if len(normal) > 800 or len(normal) < 15:
            continue
        contexto = (
            r"\b(?:chamada|edital|programa|propostas?|projetos?|pesquisadores?|"
            r"pesquisas?|estudos|objetivo|finalidade|tema|foco|visam|visa|"
            r"contempla|apoia|apoiar|orientada|aborda|destina|priorizadas?|"
            r"prioritarios?|elegiveis)\b"
        )
        escopo = (
            r"\b(?:na[s]? area[s]?|no campo|tem[a-z]*|foco|sobre|voltad[a-z]*|"
            r"objetivo|finalidade|em pesquisa|em projetos|investiga|"
            r"para apoiar|priorizad[a-z]*|destinad[a-z]*)\b"
        )
        if re.search(contexto, normal) and re.search(escopo, normal):
            relevantes.extend(_termos_mencionados(linha))
    return list(dict.fromkeys(relevantes))


def extrair_area_projeto(texto, titulo=None):
    """Prioriza precisão: título > elegibilidade > seção temática > escopo.

    Termos são explícitos, mas reconhecidos com sinônimos PT/EN. A presença
    casual de palavras em anexos, regras ou referências não basta. Se o edital
    abranger várias áreas e mencionar 'interdisciplinar', segue a regra do
    projeto e utiliza 'Interdisciplinar'.
    """
    if not texto and not titulo:
        return None
    texto = texto or ""
    if titulo is None and texto:
        primeira = limpar(texto.splitlines()[0])
        if len(primeira) <= 240 and re.match(
                r"^(?:chamada|auxilio|programa|fapesp|cooperacao|edital|"
                r"selecao|sprint|international|centro|pesquisa|iniciativa|"
                r"projeto|fapesq)\b", sem_acentos(primeira)):
            titulo = primeira
    titulo = titulo or ""
    # Órgão financiador não é, por si só, a área de pesquisa financiada.
    # A Diretoria de Geociências da NSF é um exemplo recorrente.
    titulo_pesquisa = re.sub(r"\bdiretoria\s+de\s+geociencias\b", "", sem_acentos(titulo))
    areas_titulo = _termos_mencionados(titulo_pesquisa)
    if re.search(r"(?<![A-Za-z])IA(?![A-Za-z])", titulo) and "Inteligência Artificial" not in areas_titulo:
        areas_titulo.append("Inteligência Artificial")
    programas = _temas_por_programa(titulo)
    areas_rotuladas = _itens_area(texto)

    # Sempre que a área estiver no próprio título ou for escopo de programa
    # temático inequívoco, a menção a 'todas as áreas' no corpo não substitui.
    if areas_titulo:
        areas = list(dict.fromkeys(areas_titulo))
    elif _escopo_todas_areas(texto):
        # Escopo amplo prevalece sobre áreas apresentadas só como preferência.
        return "Todas as áreas"
    elif areas_rotuladas:
        areas = areas_rotuladas
    elif programas:
        areas = programas
    else:
        areas = _areas_no_escopo(texto)

    if not areas:
        return None
    if len(areas) > 1 and _INTERDISCIPLINAR.search(sem_acentos(texto)):
        return "Interdisciplinar"
    return "; ".join(areas[:10])


def extrair_regiao(texto):
    """Identifica UF(s) no contexto territorial sem confundir 'para' com Pará."""
    original = limpar(texto)
    normal = sem_acentos(original)
    if re.search(
        r"\b(?:abrangencia\s+nacional|todo\s+o\s+territorio\s+nacional|"
        r"em\s+todo\s+o\s+brasil|em\s+todo\s+o\s+pais|"
        r"de\s+qualquer\s+estado\s+brasileiro|todo\s+o\s+territorio\s+brasileiro)\b",
        normal,
    ):
        return "Nacional"

    padroes_contexto = (
        r"\b(?:estado|estados)\s+(?:de|do|da|dos|das)\s+.{0,130}",
        r"\b(?:pesquisadores|instituicoes|instituicao|universidades|empresas|projetos)\s+"
        r"(?:do|da|de|dos|das|sediad[oa]s?\s+em|localizad[oa]s?\s+em)\s+.{0,130}",
        r"\b(?:elegiveis|elegibilidade|abrangencia|sede)\s*:\s*.{0,130}",
    )
    trechos = []
    trechos_originais = []
    for padrao in padroes_contexto:
        for match in re.finditer(padrao, normal):
            trechos.append(match.group(0))
            # A normalização de acentos mantém o comprimento das letras
            # portuguesas mais comuns; permite verificar o acento original.
            trechos_originais.append(original[match.start():match.end()])
    contexto = " ".join(trechos)
    contexto_original = " ".join(trechos_originais)
    siglas = set()
    for nome, sigla in ESTADOS.items():
        if sigla == "PA":
            # 'para' sem acento é preposição: só aceitar o estado Pará
            # quando estiver escrito com acento em contexto territorial.
            if re.search(r"\bpará\b", contexto_original, re.I):
                siglas.add("PA")
        elif re.search(rf"\b{re.escape(nome)}\b", contexto):
            siglas.add(sigla)
    if re.search(r"\b(?:instituicoes|pesquisadores|empresas|universidades)\s+paulistas\b", normal):
        siglas.add("SP")
    return ", ".join(sorted(siglas)) or None


def buscar_detalhes_chamada_fapesp(url):
    """Coleta apenas data, estado, área e valores da página individual."""
    resposta = requisitar_pagina_fapesp(url)
    soup = BeautifulSoup(resposta.content, "html.parser")
    principal = soup.select_one("main.container.int-body") or soup.select_one("main")
    if principal is None:
        raise ValueError("Corpo principal da página não encontrado")
    corpo = principal.select_one("div.page-body") or principal
    cabecalho = limpar(principal.get_text(" ", strip=True))
    texto = corpo.get_text("\n", strip=True)
    if len(texto.strip()) < 40:
        raise ValueError("A página individual não contém HTML suficiente")
    valor, moeda = extrair_moeda_e_valor(texto)
    titulo_tag = principal.select_one("h2.b > span") or principal.select_one("h2")
    titulo = limpar(titulo_tag.get_text(" ", strip=True)) if titulo_tag else ""
    return {
        "data_publicacao": extrair_data_publicacao(cabecalho[:2000]),
        "regiao": extrair_regiao(texto),
        "area_projeto": extrair_area_projeto(texto, titulo=titulo),
        "valor": valor,
        "moeda": moeda,
    }

"""Casos controlados, sem rede externa."""
from decimal import Decimal
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scraping


class RespostaFake:
    def __init__(self, html, url=None):
        self.content = html.encode("utf-8")
        self.url = url or scraping.URL_CHAMADAS_FAPESP


def pagina_indice():
    itens = []
    for n in range(1, 61):
        itens.append(
            f'<li><a href="/{n}000">Chamada de Pesquisa {n}</a>'
            f'<br/>Chamada FAPESP {n:02d}/2025'
            f'<br/>Data limite para submissão: 01/04/2026'
            f'<br/>Apoio a pesquisas em 2025. Apoio: FAPESP</li>'
        )
    itens.append('<li><a href="/antiga">Edital antigo</a><br/>Chamada FAPESP 15/2024</li>')
    return '<main class="container int-body"><div class="page-body"><ul>' + ''.join(itens) + '</ul></div></main>'


def pagina_detalhe():
    return '''<main class="container int-body">
        <h2>Chamada de Pesquisa 53</h2>
        <p>Página atualizada em 12/07/2026 - Publicada em 31/10/2025</p>
        <div class="page-body">
          <p>Instituições de pesquisa sediadas no estado de São Paulo.</p>
          <p>Áreas: Ciências Exatas e da Terra e Engenharias</p>
          <p>Projetos interdisciplinares são aceitos.</p>
          <p>Orçamento: R$ 500 mil, além de R$ 200 milhões para a chamada.</p>
          <p>Outros valores: US$ 800.000,00 e € 90.000,00.</p>
        </div>
    </main>'''


def test_identifica_2025_sem_duplicar():
    with patch.object(scraping, 'requisitar_pagina_fapesp', return_value=RespostaFake(pagina_indice())):
        chamadas = scraping.buscar_chamadas_fapesp()
    assert len(chamadas) == 60
    assert chamadas[0]['numero'] == '60/2025'
    assert len({chamada['link'] for chamada in chamadas}) == 60


def test_detalhes_principais():
    with patch.object(scraping, 'requisitar_pagina_fapesp', return_value=RespostaFake(pagina_detalhe())):
        dados = scraping.buscar_detalhes_chamada_fapesp('https://fapesp.br/53000')
    assert dados['data_publicacao'].isoformat() == '2025-10-31'
    assert dados['regiao'] == 'SP'
    assert dados['area_projeto'] == 'Interdisciplinar'
    assert dados['valor'] == 200_000_000
    assert dados['moeda'] == 'BRL'


def test_area_sem_classificacao_inventada():
    assert scraping.extrair_area_projeto('Área de conhecimento: Física') == 'Física'
    assert scraping.extrair_area_projeto('Áreas: Física e Matemática\nProjetos interdisciplinares') == 'Interdisciplinar'
    assert scraping.extrair_area_projeto('Área: Astronomia') == 'Astronomia'
    assert scraping.extrair_area_projeto('Apoio a pesquisa em robótica.') is None
    assert scraping.extrair_area_projeto('Equipes multidisciplinares') is None


def test_estados_e_nacional():
    assert scraping.extrair_regiao('Projetos de âmbito nacional em todo o Brasil.') == 'Nacional'
    assert scraping.extrair_regiao('Pesquisadores dos estados de São Paulo e Rio de Janeiro.') == 'RJ, SP'
    assert scraping.extrair_regiao('Estudantes do Estado de Minas Gerais.') == 'MG'
    assert scraping.extrair_regiao('O edital é financiado pela FAPESP.') is None


def test_maior_valor_com_moeda_correspondente():
    assert scraping.extrair_moeda_e_valor('R$ 90 milhões e R$ 300 mil') == (Decimal('90000000'), 'BRL')
    assert scraping.extrair_moeda_e_valor('US$ 1,500.00, € 70.000,00') == (Decimal('70000.00'), 'EUR')
    assert scraping.extrair_moeda_e_valor('2 milhões de reais') == (Decimal('2000000'), 'BRL')
    assert scraping.extrair_moeda_e_valor('Sem valor informado') == (None, None)
    assert scraping.normalizar_data('7 de julho de 2025').isoformat() == '2025-07-07'

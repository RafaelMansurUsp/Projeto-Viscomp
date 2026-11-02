"""Teste da persistência, com SQLite em memória e sem PostgreSQL."""
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_api_salva_exatamente_7_colunas_e_atualiza(monkeypatch):
    banco = types.ModuleType('database')
    banco.Base = declarative_base()
    banco.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    sessao = sessionmaker(bind=banco.engine)

    def get_db():
        with sessao() as db:
            yield db

    banco.get_db = get_db
    monkeypatch.setitem(sys.modules, 'database', banco)
    sys.modules.pop('models', None)
    sys.modules.pop('main', None)
    api = importlib.import_module('main')
    assert [col.name for col in api.models.Oportunidade.__table__.columns] == [
        'link', 'titulo', 'data_publicacao', 'regiao', 'area_projeto', 'valor', 'moeda'
    ]
    chamadas = [{
        'numero': '53/2025',
        'titulo': 'Centros de Ciência',
        'link': 'https://fapesp.br/17876',
        'texto_listagem': 'Orçamento de R$ 500 mil',
    }]
    detalhes = {
        'data_publicacao': None,
        'regiao': 'SP',
        'area_projeto': 'Interdisciplinar',
        'valor': 200_000_000,
        'moeda': 'BRL',
    }
    from datetime import date
    detalhes['data_publicacao'] = date(2025, 10, 31)
    with TestClient(api.app) as cliente:
        with patch.object(api, 'buscar_chamadas_fapesp', return_value=chamadas), patch.object(api, 'buscar_detalhes_chamada_fapesp', return_value=detalhes):
            primeira = cliente.post('/scraping/fapesp?limite=1')
            assert primeira.status_code == 200, primeira.text
            assert primeira.json()['adicionadas'] == 1
            segunda = cliente.post('/scraping/fapesp')
            assert segunda.status_code == 200
            assert segunda.json()['atualizadas'] == 1
        dados = cliente.get('/oportunidades').json()
        assert len(dados) == 1
        assert set(dados[0]) == {'link', 'titulo', 'data_publicacao', 'regiao', 'area_projeto', 'valor', 'moeda'}
        assert dados[0]['data_publicacao'] == '2025-10-31'
        assert dados[0]['valor'] == 200_000_000
        assert dados[0]['area_projeto'] == 'Interdisciplinar'

        # Uma falha HTTP no detalhe não apaga dados já coletados.
        with patch.object(api, 'buscar_chamadas_fapesp', return_value=chamadas), patch.object(api, 'buscar_detalhes_chamada_fapesp', side_effect=ValueError('sem HTML')):
            falha = cliente.post('/scraping/fapesp')
            assert falha.status_code == 200
            assert len(falha.json()['falhas']) == 1
        assert cliente.get('/oportunidades').json()[0]['valor'] == 200_000_000

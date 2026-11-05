"""Visualizações interativas para SCC0252/SCC5836 (Entrega 1).

Uso:
    python visualizar_fapesp.py --entrada dados/chamadas_fapesp.csv

Saídas: HTMLs interativos, CSV pré-processado e relatório de diagnóstico.

IMPORTANTE: Os registros são CHAMADAS de propostas, não bolsas concedidas.
O campo 'valor' é preservado, mas NÃO faz parte das análises:
representa o maior montante citado, não necessariamente o orçamento da chamada.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import plotly.express as px

ANOS_ANALISADOS = list(range(2020, 2026))
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Classificação ANALÍTICA (não é uma taxonomia oficial da FAPESP).
# Categorias transversais permanecem fora da disputa entre os três grupos.
EXATAS = {
    "Ciências Exatas e da Terra", "Engenharias", "Engenharia",
    "Ciência da Computação", "Inteligência Artificial", "Ciência de Dados",
    "Matemática Aplicada", "Matemática", "Estatística",
    "Tecnologias Quânticas", "Computação Quântica", "Comunicações Quânticas",
    "Sensoriamento Quântico", "Física", "Astrofísica", "Astronomia",
    "Geociências", "Ciências Espaciais", "Ciências Terrestres",
    "Ciências Polares", "Meteorologia", "Ciência de Materiais e Engenharia",
    "Ciência de Materiais", "Materiais Avançados", "Nanotecnologia",
    "Telecomunicações", "Internet e Redes", "Segurança da Informação",
    "Software Livre e Dados Abertos", "Energia", "Transição Energética",
    "Energias Renováveis", "Hidrogênio Verde", "Petróleo e Gás",
    "Oceanografia", "Tecnologia dos Oceanos",
}

HUMANAS = {
    "Ciências Sociais Aplicadas", "Ciências Humanas e Sociais", "Ciências Humanas",
    "Ciências Sociais e Jurídicas", "Linguística, Letras e Artes",
    "Linguagem, Comunicação e Artes", "Artes e Humanidades",
    "Educação Básica", "Educação Profissional", "Ensino e Aprendizagem",
    "Políticas Públicas", "Políticas Educacionais", "Democracia e Cidadania",
    "Desigualdades Sociais", "Segurança Pública", "Conhecimentos Indígenas",
    "Economia", "Administração", "Psicologia", "Antropologia",
    "Ciência Política", "Sociologia", "História", "Arqueologia",
    "Linguística", "Comunicação", "Divulgação Científica", "Migração Humana",
    "Democracia e Governança", "Artes", "Cultura Digital",
    "Patrimônio Cultural", "Acervos Museológicos, Bibliográficos e Arquivísticos",
    "Urbanismo", "Mobilidade Urbana", "Turismo",
}

BIOLOGICAS = {
    "Ciências Biológicas", "Ciências Agrárias", "Ciências da Saúde",
    "Ciências da Vida", "Saúde", "Saúde Pública", "Saúde Global", "Saúde Mental",
    "Doenças Crônicas", "Doenças Infecciosas", "Medicina Personalizada",
    "Biomedicina", "Biotecnologia", "Bioinformática", "Genômica",
    "Genética", "Biologia Molecular", "Neurociências", "Microbiologia",
    "Oncologia", "Epidemiologia", "Gripe Aviária", "Covid-19",
    "Taxonomia Biológica", "Biodiversidade", "Ecologia",
    "Conservação Ambiental", "Serviços Ecossistêmicos",
    "Restauração de Ecossistemas", "Restauração da Natureza",
    "Florestas Tropicais", "Agropecuária", "Agricultura",
    "Agricultura Familiar", "Segurança Alimentar",
    "Sistemas Alimentares Saudáveis", "Bioenergia", "Biocombustíveis",
    "Coleções Biológicas",
}

TRANSVERSAIS = {
    "Ciências Ambientais", "Ciências Agrárias e Ambientais",
    "Engenharia e Arquitetura", "Medicina Computacional",
    "Mudança de Uso da Terra", "Mudanças Climáticas",
    "Eventos Climáticos Extremos", "Desmatamento", "Sustentabilidade",
    "Bioeconomia", "Economia Circular", "Resíduos Sólidos",
    "Recursos Hídricos", "Saneamento", "Ciências do Mar",
    "Economia Azul Sustentável", "Poluição Marinha",
    "Interdisciplinar", "Todas as áreas",
}

MAPPINGS = {
    **{x.casefold(): "Exatas" for x in EXATAS},
    **{x.casefold(): "Humanas" for x in HUMANAS},
    **{x.casefold(): "Biológicas" for x in BIOLOGICAS},
    **{x.casefold(): "Interdisciplinar" for x in TRANSVERSAIS},
}


def classificar_grande_area(valor: object) -> str:
    """Evita dupla contagem. Interdisciplinar agrupa também temas transversais e todas as áreas."""
    if pd.isna(valor) or not str(valor).strip():
        return "Sem classificação"
    tokens = [x.strip().casefold() for x in str(valor).split(";") if x.strip()]
    correspondencias = [MAPPINGS.get(x) for x in tokens]
    if not correspondencias or any(g is None for g in correspondencias):
        return "Sem classificação"
    grupos = set(correspondencias)
    if len(grupos) > 1 or "Interdisciplinar" in grupos:
        return "Interdisciplinar"
    return next(iter(grupos))





def preparar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    campos = {"titulo", "link", "data_publicacao", "regiao", "area_projeto", "valor", "moeda"}
    faltando = campos - set(df.columns)
    if faltando:
        raise ValueError(f"CSV sem colunas esperadas: {sorted(faltando)}")

    original = len(df)
    df = df.drop_duplicates(subset="link").copy()
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"], errors="coerce")
    df["ano"] = df["data_publicacao"].dt.year.astype("Int64")
    df["mes"] = df["data_publicacao"].dt.month.astype("Int64")
    df["mes_nome"] = df["mes"].map({i + 1: m for i, m in enumerate(MESES)})
    df["grande_area"] = df["area_projeto"].apply(classificar_grande_area)
    # Não modificamos as colunas originais valor e moeda. A coleta monetária
    # permanece no projeto, mesmo sem entrar nas visualizações da entrega.
    df["data_no_recorte"] = df["ano"].isin(ANOS_ANALISADOS)

    diagnostico = {
        "total_csv": original,
        "duplicadas_por_link": original - len(df),
        "total_distintas": len(df),
        "sem_data_publicacao": int(df["ano"].isna().sum()),
        "fora_intervalo_2020_2025": int((df["ano"].notna() & ~df["ano"].isin(ANOS_ANALISADOS)).sum()),
        "sem_area_projeto": int(df["area_projeto"].isna().sum()),
        "sem_regiao": int(df["regiao"].isna().sum()),
        "sem_valor": int(df["valor"].isna().sum()),
        "sem_moeda": int(df["moeda"].isna().sum()),
        "sem_grande_area_classificada": int((df["grande_area"] == "Sem classificação").sum()),
        "classificadas_mistas_ou_transversais": int((df["grande_area"] == "Interdisciplinar").sum()),
        "validas_para_analises_temporais": int(df["data_no_recorte"].sum()),
    }
    return df, diagnostico


def gerar_pendencias(df: pd.DataFrame, destino: Path) -> int:
    """Salva casos para revisão, sem confundir valor ausente com falha confirmada."""
    motivos = []
    for _, row in df.iterrows():
        problemas = []
        if pd.isna(row["data_publicacao"]):
            problemas.append("data_nao_identificada")
        elif not row["data_no_recorte"]:
            problemas.append("data_fora_do_recorte")
        if pd.isna(row["regiao"]):
            problemas.append("regiao_nao_identificada")
        if pd.isna(row["area_projeto"]):
            problemas.append("area_nao_identificada")
        if pd.isna(row["valor"]):
            problemas.append("valor_nao_identificado_ou_nao_informado")
        if pd.isna(row["moeda"]):
            problemas.append("moeda_nao_identificada_ou_nao_informada")
        motivos.append("; ".join(problemas))
    base = df.copy()
    base["motivos_para_revisao"] = motivos
    base = base.loc[base["motivos_para_revisao"].ne("")]
    base.to_csv(destino / "registros_para_revisao.csv", index=False)
    return len(base)

def salvar_html(fig, caminho: Path) -> None:
    fig.update_layout(
        template="plotly_white",
        font=dict(size=13),
        hovermode="closest",
        margin=dict(l=70, r=40, t=85, b=70),
    )
    # HTML autônomo (sem dependência de internet para abrir).
    fig.write_html(caminho, include_plotlyjs=True, full_html=True)
    print(f"Gráfico salvo: {caminho}")


def grafico_tempo(df: pd.DataFrame, destino: Path) -> pd.Series:
    base = df.loc[df["ano"].isin(ANOS_ANALISADOS)]
    contagem = base.groupby("ano").size().reindex(ANOS_ANALISADOS, fill_value=0)
    serie = pd.DataFrame({"Ano": ANOS_ANALISADOS, "Chamadas": contagem.values})
    fig = px.line(
        serie, x="Ano", y="Chamadas", markers=True,
        title="Chamadas da FAPESP por ano de publicação (2020–2025)",
        hover_data={"Ano": True, "Chamadas": True},
    )
    fig.add_hline(
        y=float(contagem.mean()), line_dash="dash",
        annotation_text="Média anual (no recorte)",
        annotation_position="top left",
    )
    fig.update_xaxes(dtick=1)
    fig.update_yaxes(rangemode="tozero")
    salvar_html(fig, destino / "01_chamadas_por_ano.html")
    return contagem


def grafico_areas(df: pd.DataFrame, destino: Path) -> pd.Series:
    ordem = ["Exatas", "Humanas", "Biológicas"]
    # Para a comparação de áreas, a data de publicação não é necessária:
    # excluir datas ausentes reduziria artificialmente a amostra.
    contagem = df["grande_area"].value_counts().reindex(ordem, fill_value=0)
    total = int(contagem.sum())
    tabela = pd.DataFrame({
        "Grande área": ordem,
        "Chamadas": contagem.values,
        "Percentual (entre classificadas)": [round(100 * x / total, 1) if total else 0 for x in contagem.values],
    })
    fig = px.bar(
        tabela, x="Grande área", y="Chamadas", text="Chamadas",
        title="Distribuição das chamadas por grande área",
        hover_data={"Percentual (entre classificadas)": ":.1f"},
    )
    fig.update_yaxes(rangemode="tozero")
    fig.add_annotation(
        x=0, y=-0.24, xref="paper", yref="paper", showarrow=False,
        text=("Exclui mistas, transversais, todas as áreas e não classificadas. "
              "Inclui registros sem data; cada chamada conta uma vez."),
        xanchor="left", font=dict(size=11),
    )
    salvar_html(fig, destino / "02_chamadas_por_grande_area.html")
    return contagem





def grafico_meses(df: pd.DataFrame, destino: Path) -> pd.Series:
    base = df.loc[df["data_no_recorte"]]
    contagem = base.groupby("mes").size().reindex(range(1, 13), fill_value=0)
    total = int(contagem.sum())
    media = float(contagem.mean())
    tabela = pd.DataFrame({
        "Mês": MESES,
        "Chamadas": contagem.values,
        "Participação no período (%)": [round(100 * n / total, 1) if total else 0 for n in contagem],
        "Faixa": ["Acima da média" if n > media else "Na média ou abaixo" for n in contagem],
    })
    fig = px.bar(
        tabela, x="Mês", y="Chamadas", text="Chamadas",
        color="Faixa",
        color_discrete_map={
            "Acima da média": "#087e8b",  # Turquesa para destacar meses acima da média
            "Na média ou abaixo": "#ef4444",  # vermelho para os demais
        },
        category_orders={"Mês": MESES, "Faixa": ["Acima da média", "Na média ou abaixo"]},
        title="Chamadas por mês — acumulado de 2020 a 2025",
        hover_data={"Participação no período (%)": ":.1f", "Faixa": True},
        labels={"Mês": "Mês de publicação", "Chamadas": "Número de chamadas", "Faixa": "Comparação com a média"},
    )
    fig.add_hline(
        y=media, line_dash="dash", line_color="#334155", line_width=1.5,
        annotation_text=f"Média mensal: {media:.1f}",
        annotation_position="top left",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(legend_title_text="Em relação à média dos 12 meses")
    fig.update_yaxes(rangemode="tozero")
    salvar_html(fig, destino / "03_chamadas_acumuladas_por_mes.html")
    tabela.to_csv(destino / "resumo_mensal.csv", index=False)
    return contagem


def grafico_mapa_calor(df: pd.DataFrame, destino: Path) -> pd.DataFrame:
    base = df.loc[df["data_no_recorte"]]
    matriz = (base.groupby(["ano", "mes"]).size()
              .unstack(fill_value=0)
              .reindex(index=ANOS_ANALISADOS, columns=range(1, 13), fill_value=0))
    fig = px.imshow(
        matriz.to_numpy(),
        x=MESES, y=[str(y) for y in ANOS_ANALISADOS],
        text_auto=True, aspect="auto", origin="upper",
        color_continuous_scale="Viridis",
        title="Chamadas por mês e ano de publicação (2020–2025)",
        labels={"x": "Mês", "y": "Ano", "color": "Chamadas"},
    )
    fig.update_traces(hovertemplate="Ano: %{y}<br>Mês: %{x}<br>Chamadas: %{z}<extra></extra>")
    fig.update_layout(coloraxis_colorbar_title="Chamadas")
    salvar_html(fig, destino / "04_mapa_calor_ano_mes.html")
    matriz.columns = MESES
    matriz.index.name = "Ano"
    matriz.to_csv(destino / "resumo_ano_mes.csv")
    return matriz


def escrever_relatorio(df, diag, tempo, areas, meses, matriz, pendencias, destino):
    linhas = [
        "DIAGNÓSTICO — ENTREGA 1 / CHAMADAS FAPESP (VERSÃO MENSAL)",
        "", "1. COBERTURA E QUALIDADE DOS DADOS",
    ]
    for nome, valor in diag.items():
        linhas.append(f"- {nome}: {valor}")
    linhas.append(f"- registros_para_revisao: {pendencias} (podem ter mais de um motivo)")
    linhas += [
        "", "2. QUANTIDADE DE CHAMADAS POR ANO (DATA DE PUBLICAÇÃO)",
    ]
    linhas += [f"- {ano}: {int(n)}" for ano, n in tempo.items()]
    linhas += [
        f"- media_anual: {tempo.mean():.2f}",
        "", "3. CHAMADAS POR GRANDE ÁREA (TODAS AS DATAS)",
    ]
    total = int(areas.sum())
    for area, n in areas.items():
        pct = 100 * int(n) / total if total else 0
        linhas.append(f"- {area}: {int(n)} ({pct:.1f}% das 3 categorias exclusivas)")
    linhas += [
        f"- Mistas/transversais/todas as áreas, agrupadas como 'Interdisciplinar': {diag['classificadas_mistas_ou_transversais']}",
        f"- Sem classificação: {diag['sem_grande_area_classificada']}",
        "", "4. CHAMADAS ACUMULADAS POR MÊS (APENAS DATAS EM 2020–2025)",
    ]
    linhas += [f"- {MESES[mes-1]}: {int(n)}" for mes, n in meses.items()]
    if int(meses.sum()):
        pico = meses[meses == meses.max()].index.tolist()
        minimo = meses[meses == meses.min()].index.tolist()
        linhas += [
            f"- total_analise_mensal: {int(meses.sum())}",
            f"- mes(es)_com_mais_chamadas: {', '.join(MESES[m-1] for m in pico)} ({int(meses.max())})",
            f"- mes(es)_com_menos_chamadas: {', '.join(MESES[m-1] for m in minimo)} ({int(meses.min())})",
            f"- media_por_mes_no_acumulado: {meses.mean():.2f}",
        ]
    linhas += [
        "", "5. CHAMADAS POR MÊS E ANO (VER RESUMO_ANO_MES.CSV)",
    ]
    for ano, linha in matriz.iterrows():
        linhas.append(f"- {ano}: " + ", ".join(f"{mes}={int(linha[mes])}" for mes in MESES))
    linhas += [
        "", "LIMITAÇÕES E POSSÍVEIS FALHAS DA COLETA",
        "- Chamadas publicadas NÃO são bolsas concedidas nem projetos aprovados.",
        "- Data de publicação NÃO mede o intervalo em que inscrições ficam abertas; sazonalidade é de PUBLICAÇÃO.",
        "- Contagens temporais excluem datas ausentes e datas fora de 2020–2025; não imputamos mês.",
        "- Uma ausência pode significar informação não divulgada ou não extraída; NÃO equivale automaticamente a bug.",
        "- 'Interdisciplinar' nesta classificação analítica inclui temas transversais, abrangência geral e múltiplas áreas.",
        "- Os dados de 2020 podem ter cobertura diferente; evitar alegações causais ou periodicidade garantida.",
        "- Valor/moeda permanecem no CSV e no scraping, mas NÃO entram nas visualizações.",
        "- O maior número monetário do edital pode não ser a verba disponível; não interpretar como orçamento.",
        "- As falhas de requisição/parse retornadas pelo endpoint de scraping não estão persistidas neste CSV.",
        "- Conferir amostras dos registros_para_revisao.csv e verificar se há lacunas na fonte.",
    ]
    caminho = destino / "resumo_diagnostico.txt"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"Resumo salvo: {caminho}")


def main():
    parser = argparse.ArgumentParser(description="Análise visual das chamadas FAPESP, sem valores monetários.")
    parser.add_argument("--entrada", type=Path, default=Path("dados/chamadas_fapesp.csv"))
    parser.add_argument("--saida", type=Path, default=Path("resultados_entrega1"))
    args = parser.parse_args()
    if not args.entrada.is_file():
        parser.error(f"CSV não encontrado: {args.entrada}. Execute exportar_fapesp.py primeiro.")
    args.saida.mkdir(parents=True, exist_ok=True)

    df, diag = preparar(pd.read_csv(args.entrada, dtype={"link": "string"}))
    df.to_csv(args.saida / "chamadas_preprocessadas.csv", index=False)
    pendencias = gerar_pendencias(df, args.saida)
    tempo = grafico_tempo(df, args.saida)
    areas = grafico_areas(df, args.saida)
    meses = grafico_meses(df, args.saida)
    matriz = grafico_mapa_calor(df, args.saida)
    escrever_relatorio(df, diag, tempo, areas, meses, matriz, pendencias, args.saida)
    print("\nPronto: quatro gráficos interativos, dados mensais e relatório de qualidade.")


if __name__ == "__main__":
    main()

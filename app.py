import os
from glob import glob

import numpy as np
import pandas as pd
import streamlit as st

# ==========================
# CONFIGURAÇÃO DA PÁGINA
# ==========================

st.set_page_config(
    page_title="Avicultura - Dashboard automático",
    layout="wide",
)

st.title("Avicultura · Dashboard automático a partir de CSV")
st.caption(
    "Os gráficos e indicadores são gerados automaticamente a partir dos arquivos CSV na pasta `dados/`."
)

# ==========================
# LEITURA AUTOMÁTICA DOS CSV
# ==========================

PASTA_DADOS = "dados"

if not os.path.isdir(PASTA_DADOS):
    st.error(f"Pasta '{PASTA_DADOS}' não encontrada. Crie a pasta e coloque seus arquivos .csv nela.")
    st.stop()

arquivos_csv = sorted(glob(os.path.join(PASTA_DADOS, "*.csv")))

with st.sidebar:
    st.header("Configurações")
    st.write(f"📂 Pasta de dados: `{PASTA_DADOS}/`")
    st.write(f"📄 Arquivos CSV encontrados: **{len(arquivos_csv)}**")
    if arquivos_csv:
        st.write("Arquivos:")
        for arq in arquivos_csv:
            st.text(f"- {os.path.basename(arq)}")
    else:
        st.warning("Nenhum arquivo CSV encontrado. Adicione pelo menos um arquivo na pasta.")
        st.stop()

# Lê e concatena todos os CSV
dfs = []
for caminho in arquivos_csv:
    try:
        df_tmp = pd.read_csv(caminho)
        df_tmp["__arquivo_origem"] = os.path.basename(caminho)
        dfs.append(df_tmp)
    except Exception as e:
        st.error(f"Erro ao ler `{caminho}`: {e}")

if not dfs:
    st.error("Não foi possível carregar nenhum CSV.")
    st.stop()

dados = pd.concat(dfs, ignore_index=True)

# ==========================
# PRÉ-PROCESSAMENTO
# ==========================

# Converte a coluna de data
if "data" not in dados.columns:
    st.error("Coluna obrigatória 'data' não encontrada nos CSV.")
    st.stop()

dados["data"] = pd.to_datetime(dados["data"], errors="coerce")
dados = dados.dropna(subset=["data"])

# Ordena por data
dados = dados.sort_values("data")

# Conversão de tipos numéricos (se existirem)
colunas_num = [
    "milho_pct",
    "farelo_soja_pct",
    "calcario_pct",
    "nucleo_pct",
    "consumo_g_ave_dia",
    "ovos_granja",
    "ovos_escola",
    "ovos_quebrados",
    "ovos_sem_casca",
    "ovos_deformados",
    "aves_doentes",
]

for col in colunas_num:
    if col in dados.columns:
        dados[col] = pd.to_numeric(dados[col], errors="coerce")

# Cria métricas derivadas, se as colunas existirem
if {"ovos_granja", "ovos_escola"}.issubset(dados.columns):
    dados["perda_ovos"] = dados["ovos_granja"] - dados["ovos_escola"]
else:
    dados["perda_ovos"] = np.nan

if {"ovos_quebrados", "ovos_sem_casca", "ovos_deformados", "ovos_granja"}.issubset(
    dados.columns
):
    dados["ovos_defeituosos"] = (
        dados["ovos_quebrados"]
        + dados["ovos_sem_casca"]
        + dados["ovos_deformados"]
    )
    dados["pct_defeituosos"] = 100 * dados["ovos_defeituosos"] / dados["ovos_granja"]
else:
    dados["ovos_defeituosos"] = np.nan
    dados["pct_defeituosos"] = np.nan

# ==========================
# FILTROS NO SIDEBAR
# ==========================

with st.sidebar:
    st.markdown("---")
    st.subheader("Filtro de período")

    data_min = dados["data"].min().date()
    data_max = dados["data"].max().date()

    periodo = st.date_input(
        "Selecione o intervalo",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
    )

    if isinstance(periodo, tuple):
        ini, fim = periodo
    else:
        ini = periodo
        fim = periodo

mask_data = (dados["data"].dt.date >= ini) & (dados["data"].dt.date <= fim)
dados_filtrados = dados[mask_data].copy()

if dados_filtrados.empty:
    st.warning("Nenhum dado dentro do período selecionado.")
    st.stop()

# ==========================
# INDICADORES GERAIS
# ==========================

# Referências (inspiradas no relatório)
CONSUMO_MIN = 105.0
CONSUMO_MAX = 115.0

col1, col2, col3, col4 = st.columns(4)

with col1:
    consumo_medio = dados_filtrados["consumo_g_ave_dia"].mean()
    if not np.isnan(consumo_medio):
        delta = consumo_medio - CONSUMO_MIN
        st.metric(
            "Consumo médio (g/ave/dia)",
            f"{consumo_medio:.1f}",
            f"{delta:+.1f} vs. limite mínimo 105",
        )
    else:
        st.metric("Consumo médio", "N/A")

with col2:
    if "ovos_granja" in dados_filtrados.columns:
        prod_media = dados_filtrados["ovos_granja"].mean()
        st.metric("Produção média (ovos/dia - granja)", f"{prod_media:.0f}")
    else:
        st.metric("Produção média", "N/A")

with col3:
    if "perda_ovos" in dados_filtrados.columns:
        perda_media = dados_filtrados["perda_ovos"].mean()
        st.metric("Perda média (granja → escola)", f"{perda_media:.1f} ovos/dia")
    else:
        st.metric("Perda média", "N/A")

with col4:
    if "pct_defeituosos" in dados_filtrados.columns:
        pct_medio_def = dados_filtrados["pct_defeituosos"].mean()
        if not np.isnan(pct_medio_def):
            st.metric("Ovos não conformes (média)", f"{pct_medio_def:.1f}%")
        else:
            st.metric("Ovos não conformes (média)", "N/A")
    else:
        st.metric("Ovos não conformes (média)", "N/A")

st.markdown("---")

# ==========================
# ABAS / SEÇÕES
# ==========================

tab_mistura, tab_consumo, tab_producao, tab_qualidade = st.tabs(
    ["Mistura da ração", "Consumo", "Produção e perdas", "Qualidade & sanidade"]
)

# ---- Aba 1: Mistura da ração ----
with tab_mistura:
    st.subheader("Mistura diária de milho, farelo de soja, calcário e núcleo")

    col_ref1, col_ref2 = st.columns(2)
    with col_ref1:
        st.markdown(
            """
            **Referência teórica (Nucleus 4%)**  
            - Milho: 62 %  
            - Farelo de soja: 24 %  
            - Calcário: 10 %  
            - Núcleo: 4 %
            """
        )
    with col_ref2:
        st.markdown(
            """
            **Situação diagnosticada no relatório**  
            Excesso de núcleo (~8 %) e déficit de farelo de soja (~20 %) e calcário (~8,5 %),  
            implicando em queda de desempenho e problemas de casca.
            """
        )

    col_m1, col_m2 = st.columns(2)

    if "milho_pct" in dados_filtrados.columns:
        with col_m1:
            st.line_chart(
                dados_filtrados.set_index("data")["milho_pct"],
                height=250,
            )

    if "farelo_soja_pct" in dados_filtrados.columns:
        with col_m2:
            st.line_chart(
                dados_filtrados.set_index("data")[["farelo_soja_pct", "calcario_pct", "nucleo_pct"]],
                height=250,
            )

    st.caption("Os gráficos acima usam a média diária registrada nos arquivos CSV.")

# ---- Aba 2: Consumo ----
with tab_consumo:
    st.subheader("Consumo de ração (g/ave/dia)")

    if "consumo_g_ave_dia" in dados_filtrados.columns:
        st.line_chart(
            dados_filtrados.set_index("data")[["consumo_g_ave_dia"]],
            height=300,
        )

        st.markdown(
            f"""
            - Faixa ideal: **{CONSUMO_MIN:.0f}–{CONSUMO_MAX:.0f} g/ave/dia**  
            - Consumo médio no período filtrado: **{consumo_medio:.1f} g/ave/dia**
            """
        )
    else:
        st.info("Coluna 'consumo_g_ave_dia' não encontrada nos dados.")

# ---- Aba 3: Produção e perdas ----
with tab_producao:
    st.subheader("Produção diária de ovos (granja vs. escola)")

    if {"ovos_granja", "ovos_escola"}.issubset(dados_filtrados.columns):
        st.line_chart(
            dados_filtrados.set_index("data")[["ovos_granja", "ovos_escola"]],
            height=300,
        )

        st.subheader("Perdas no trajeto (granja → escola)")
        st.bar_chart(
            dados_filtrados.set_index("data")[["perda_ovos"]],
            height=300,
        )

        total_granja = dados_filtrados["ovos_granja"].sum()
        total_escola = dados_filtrados["ovos_escola"].sum()
        total_perdas = dados_filtrados["perda_ovos"].sum()

        st.markdown(
            f"""
            - Total produzido na granja (período filtrado): **{total_granja:.0f} ovos**  
            - Total registrado na escola: **{total_escola:.0f} ovos**  
            - Diferença absoluta: **{total_perdas:.0f} ovos**
            """
        )
    else:
        st.info("Colunas 'ovos_granja' e 'ovos_escola' não encontradas nos dados.")

# ---- Aba 4: Qualidade & sanidade ----
with tab_qualidade:
    st.subheader("Qualidade dos ovos")

    if {"pct_defeituosos"}.issubset(dados_filtrados.columns):
        st.line_chart(
            dados_filtrados.set_index("data")[["pct_defeituosos"]],
            height=300,
        )

    col_q1, col_q2 = st.columns(2)
    with col_q1:
        if "ovos_defeituosos" in dados_filtrados.columns:
            total_def = dados_filtrados["ovos_defeituosos"].sum()
            st.metric("Total de ovos não conformes (período)", f"{total_def:.0f}")
    with col_q2:
        if "aves_doentes" in dados_filtrados.columns:
            total_doentes = dados_filtrados["aves_doentes"].sum()
            st.metric("Soma de aves doentes observadas", f"{total_doentes:.0f}")

    st.subheader("Tabela detalhada (dados filtrados)")
    st.dataframe(
        dados_filtrados[
            [
                "data",
                "milho_pct",
                "farelo_soja_pct",
                "calcario_pct",
                "nucleo_pct",
                "consumo_g_ave_dia",
                "ovos_granja",
                "ovos_escola",
                "perda_ovos",
                "ovos_quebrados",
                "ovos_sem_casca",
                "ovos_deformados",
                "ovos_defeituosos",
                "pct_defeituosos",
                "aves_doentes",
                "__arquivo_origem",
            ]
            if "__arquivo_origem" in dados_filtrados.columns
            else dados_filtrados.columns
        ],
        use_container_width=True,
    )

st.markdown("---")
st.caption(
    "Para atualizar o dashboard, basta adicionar novos arquivos .csv na pasta `dados/` "
    "seguindo o mesmo padrão de colunas. Ao recarregar a página, os gráficos são atualizados automaticamente."
)

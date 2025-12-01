# =============================================================================
# PARTE 1 – IMPORTS E CONFIGURAÇÃO BÁSICA
# =============================================================================
import os
from glob import glob

import numpy as np
import pandas as pd
import streamlit as st
#import matplotlib.pyplot as plt
#import matplotlib.dates as mdates
import altair as alt
from datetime import timedelta
import streamlit.components.v1 as components



# Configuração da página do Streamlit
st.set_page_config(
    page_title="Avicultura - Dashboard automático",
    layout="wide",
)

# Âncora de topo para navegação
#st.markdown("<div id='topo'></div>", unsafe_allow_html=True)
st.markdown("<div id='topo' style='position: relative; top: -30px;'></div>",unsafe_allow_html=True,)

st.title("Avicultura · Dashboard automático a partir de CSV")
st.caption(
    "Os gráficos e indicadores são gerados automaticamente a partir dos arquivos CSV na pasta `dados/`."
)


# =============================================================================
# PARTE 2 – LEITURA GLOBAL DOS ARQUIVOS CSV E PRÉ-PROCESSAMENTO
# =============================================================================
PASTA_DADOS = "dados"

if not os.path.isdir(PASTA_DADOS):
    st.error(f"Pasta '{PASTA_DADOS}' não encontrada. Crie a pasta e coloque seus arquivos .csv nela.")
    st.stop()

arquivos_csv = sorted(glob(os.path.join(PASTA_DADOS, "*.csv")))

# -------------------- Sidebar: informações de arquivos ------------------------
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

# Lê e concatena todos os CSV em um único DataFrame "dados"
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

# -------------------- Pré-processamento global --------------------
# 1) Coluna de data
if "data" not in dados.columns:
    st.error("Coluna obrigatória 'data' não encontrada nos CSV.")
    st.stop()

dados["data"] = pd.to_datetime(dados["data"], errors="coerce")
dados = dados.dropna(subset=["data"])
dados = dados.sort_values("data")

# 2) Colunas numéricas
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

# 3) Métricas derivadas
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


# =============================================================================
# PARTE 3 – FILTRO DE PERÍODO, CARDS RESUMO E MENU LATERAL
# =============================================================================
CONSUMO_MIN = 105.0
CONSUMO_MAX = 115.0

with st.sidebar:
    st.markdown("---")
    st.subheader("Filtro de período")

    data_min = dados["data"].min().date()
    data_max = dados["data"].max().date()

    default_ini = max(data_min, data_max - timedelta(days=30))

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

# -------------------- Cards resumo no topo --------------------
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

# -------------------- Função de navegação (scroll por âncora) ----------------
def scroll_to(anchor: str):
    """
    Rola até o elemento com o id fornecido.
    O deslocamento para não cortar o título será feito no próprio <div id='...'>.
    """

    components.html(
        f"""
        <script>
        const frameWin = window.parent;
        const frameDoc = frameWin.document;
        const el = frameDoc.getElementById('{anchor}');
        if (el) {{
            el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
        </script>
        """,
        height=0,
    )




# -------------------- Menu lateral de navegação rápida -----------------------
with st.sidebar:
    st.markdown("---")
    st.subheader("Navegação rápida")
    secao = st.radio(
        "Ir para a seção:",
        [
            "Topo",
            "Mistura da ração",
            "Consumo",
            "Produção e perdas",
            "Qualidade & sanidade",
        ],
        index=0,
    )

# Dispara o scroll conforme a seção escolhida
#if secao == "Topo":
#    scroll_to("topo")
#elif secao == "Mistura da ração":
#    scroll_to("mistura")
#elif secao == "Consumo":
#    scroll_to("consumo")
#elif secao == "Produção e perdas":
#    scroll_to("producao")
#elif secao == "Qualidade & sanidade":
#    scroll_to("qualidade")


# =============================================================================
# PARTE 4 – FUNÇÕES AUXILIARES (GRÁFICO E DIAGNÓSTICO DA MISTURA)
# =============================================================================
def chart_serie_altair(df, col, titulo, ref_min, ref_max, ylim=None):
    """
    Cria um gráfico Altair no mesmo estilo visual dos outros gráficos do Streamlit,
    com:
      - faixa de referência definida por [ref_min, ref_max] (livre para cada gráfico);
      - meses em português no eixo X;
      - marcações de eixo a cada 5 dias (5, 10, 15, 20, ...);
      - folga extra no final do eixo X para não cortar o último ponto.

    df      : DataFrame com colunas 'data' e 'col'
    col     : nome da coluna de interesse (string)
    titulo  : título do gráfico (string)
    ref_min : limite inferior da faixa alvo (float)
    ref_max : limite superior da faixa alvo (float)
    ylim    : tupla (ymin, ymax) opcional para limitar o eixo Y
    """

    df_plot = df.copy()
    df_plot["ref_min"] = ref_min
    df_plot["ref_max"] = ref_max

    # Domínio de datas com "folga" no fim para não cortar o último ponto
    hoje = pd.Timestamp.today().normalize()
    dmax = hoje + pd.Timedelta(days=2)
    dmin = dmax - pd.Timedelta(days=30)  # janela fixa de 30 dias

    # Escala vertical única para todas as camadas
    scale_y = alt.Scale(domain=ylim, nice=False) if ylim else alt.Undefined

    # Expressão Vega-Lite para traduzir abreviações de meses para português
    label_expr = (
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace("
        "replace(datum.label,"
        "'Jan','Jan'),"
        "'Feb','Fev'),"
        "'Mar','Mar'),"
        "'Apr','Abr'),"
        "'May','Mai'),"
        "'Jun','Jun'),"
        "'Jul','Jul'),"
        "'Aug','Ago'),"
        "'Sep','Set'),"
        "'Oct','Out'),"
        "'Nov','Nov'),"
        "'Dec','Dez')"
    )

    # Eixo X: marcações a cada 5 dias
    x_axis = alt.Axis(
        title="",
        format="%d %b",                     # dia + mês abreviado
        tickCount={"interval": "day", "step": 5},
        labelExpr=label_expr,
    )

    x_scale = alt.Scale(domain=[dmin, dmax])

    base = alt.Chart(df_plot).encode(
        x=alt.X(
            "data:T",
            axis=x_axis,
            scale=x_scale,
        )
    )

    # Faixa de referência [ref_min, ref_max] usando a MESMA escala Y
    faixa = base.mark_area(opacity=0.15).encode(
        y=alt.Y("ref_min:Q", scale=scale_y),
        y2=alt.Y2("ref_max:Q"),
    )

    # Linha da série com a MESMA escala Y
    linha = base.mark_line().encode(
        y=alt.Y(f"{col}:Q", title="%", scale=scale_y),
    )

    # Pontos na linha usando mesma escala
    pontos = base.mark_point(size=60).encode(
        y=alt.Y(f"{col}:Q", scale=scale_y),
        tooltip=[
            alt.Tooltip("data:T", title="Data"),
            alt.Tooltip(f"{col}:Q", title="Valor (%)", format=".1f"),
        ],
    )

    # Rótulos numéricos sobre os pontos, mesma escala
    textos = base.mark_text(dy=-20, fontSize=15, color="white").encode(
        y=alt.Y(f"{col}:Q", scale=scale_y),
        text=alt.Text(f"{col}:Q", format=".1f"),
    )

    chart = (faixa + linha + pontos + textos).properties(
        height=250,
        title=titulo,
    )

    return chart.interactive()



def diagnostico_serie(df, col, ref_min, ref_max, nome):
    """
    Gera um texto de diagnóstico para a série usando a faixa [ref_min, ref_max].

    Inclui:
    - contagem de pontos dentro / acima / abaixo da faixa;
    - análise da média dos 2 últimos registros;
    - alerta nutricional específico para cada ingrediente (milho, farelo, calcário, núcleo).
    """
    if df.empty or col not in df.columns:
        return f"Diagnóstico para {nome}: série sem dados suficientes."

    y = df[col].dropna()
    if y.empty:
        return f"Diagnóstico para {nome}: série sem dados válidos (após remoção de NaN)."

    # -------------------------------------------------------------------------
    # 1) Estatística global simples: quantos pontos dentro / acima / abaixo
    # -------------------------------------------------------------------------
    dentro = ((y >= ref_min) & (y <= ref_max)).sum()
    acima = (y > ref_max).sum()
    abaixo = (y < ref_min).sum()
    total = len(y)

    partes = []
    partes.append(
        f"No período considerado (últimos **{total} registros**), "
        f"**{dentro}** pontos ficaram **dentro** da faixa alvo "
        f"({ref_min:.1f}–{ref_max:.1f} %), "
        f"**{acima}** acima e **{abaixo}** abaixo."
    )

    if dentro == total:
        partes.append("A mistura está **bem ajustada** em torno da faixa definida.")
    elif acima + abaixo > dentro:
        partes.append("Há **alta variabilidade** em relação à formulação recomendada.")
    else:
        partes.append(
            "A maior parte dos dias está próxima da formulação ideal, "
            "mas ainda há espaço para ajustes finos."
        )

    # -------------------------------------------------------------------------
    # 2) Tendência recente: média dos 2 últimos registros
    # -------------------------------------------------------------------------
    if len(y) >= 2:
        ultimos = y.tail(2)
        janela_desc = "2 últimos registros"
    else:
        ultimos = y
        janela_desc = "registros disponíveis"

    media_ultimos = ultimos.mean()
    partes.append(
        f"A média dos **{janela_desc}** é **{media_ultimos:.1f} %**."
    )

    # Situação recente em relação à faixa
    if media_ultimos > ref_max:
        tendencia = "acima"
    elif media_ultimos < ref_min:
        tendencia = "abaixo"
    else:
        tendencia = "dentro"

    # -------------------------------------------------------------------------
    # 3) Alerta nutricional específico por ingrediente
    # -------------------------------------------------------------------------
    nome_lower = nome.lower()

    alerta = ""
    if tendencia == "acima":
        if "milho" in nome_lower:
            alerta = (
                "Tendência recente de **excesso de milho**. "
                "Isso aumenta a densidade energética da dieta, favorecendo deposição de gordura, "
                "queda de persistência de postura e maior risco de ovos com casca frágil "
                "se farelo de soja e calcário não acompanham o ajuste."
            )
        elif "farelo" in nome_lower:
            alerta = (
                "Tendência recente de **excesso de farelo de soja**. "
                "Dietas muito proteicas podem aumentar custo, sobrecarregar metabolismo e "
                "não se converter em ganho de produção se a energia não estiver alinhada."
            )
        elif "calcário" in nome_lower or "calcario" in nome_lower:
            alerta = (
                "Tendência recente de **excesso de calcário**. "
                "Excesso de cálcio pode reduzir consumo, interferir na absorção de outros minerais "
                "e comprometer desempenho se não houver ajuste cuidadoso do restante da formulação."
            )
        elif "núcleo" in nome_lower or "nucleo" in nome_lower:
            alerta = (
                "Tendência recente de **excesso de núcleo**. "
                "Concentração muito alta de núcleo eleva o custo e pode gerar desbalanços de "
                "vitaminas e minerais, sem ganho proporcional em desempenho."
            )
        else:
            alerta = (
                "A média recente está **acima da faixa alvo**, sugerindo excesso deste componente "
                "na dieta. Avaliar impacto em custo e equilíbrio energia/proteína/minerais."
            )

    elif tendencia == "abaixo":
        if "milho" in nome_lower:
            alerta = (
                "Tendência recente de **déficit de milho**. "
                "Energia insuficiente leva a menor consumo efetivo, ovos menores e queda de produção, "
                "especialmente em períodos frios ou de maior exigência."
            )
        elif "farelo" in nome_lower:
            alerta = (
                "Tendência recente de **déficit de farelo de soja**. "
                "Proteína abaixo do recomendado reduz massa de ovo, piora a conversão alimentar "
                "e compromete a persistência de postura."
            )
        elif "calcário" in nome_lower or "calcario" in nome_lower:
            alerta = (
                "Tendência recente de **déficit de calcário**. "
                "Isso aumenta o risco de cascas finas, trincadas e maior percentual de ovos não conformes, "
                "além de mobilização de cálcio ósseo das aves."
            )
        elif "núcleo" in nome_lower or "nucleo" in nome_lower:
            alerta = (
                "Tendência recente de **déficit de núcleo**. "
                "Pode haver carência de vitaminas, minerais e aditivos, refletindo em queda de imunidade, "
                "pior qualidade de casca e maior sensibilidade a estresses."
            )
        else:
            alerta = (
                "A média recente está **abaixo da faixa alvo**, sugerindo deficiência deste componente "
                "na dieta. Monitorar possíveis quedas de desempenho e qualidade dos ovos."
            )
    else:
        alerta = (
            "A média recente permanece **dentro da faixa alvo**, indicando tendência de estabilidade. "
            "Manter o acompanhamento para evitar deriva gradual ao longo das próximas semanas."
        )

    partes.append(alerta)

    return " ".join(partes)



def bloco_instagram_mistura(df, col, titulo, ref_min, ref_max, texto_ref, nome_curto, ylim=None):
    """
    Renderiza um "card" vertical no estilo linha do tempo (Instagram):

    - Título do componente (ex.: 'Milho (%)')
    - Texto de referência (valores alvo / fórmula)
    - Gráfico temporal (Altair) com faixa [ref_min, ref_max]
    - Diagnóstico automático abaixo do gráfico
    """
    st.markdown(f"### {titulo}")
    st.markdown(texto_ref)

    # Gráfico Altair no estilo dos demais gráficos do dashboard
    chart = chart_serie_altair(df, col, titulo, ref_min=ref_min, ref_max=ref_max, ylim=ylim)
    st.altair_chart(chart, use_container_width=True)

    diag = diagnostico_serie(df, col, ref_min, ref_max, nome_curto)
    st.markdown(f"**Diagnóstico ({nome_curto}):** {diag}")

    st.markdown("---")



# =============================================================================
# PARTE 5 – SEÇÃO 1: MISTURA DA RAÇÃO (FEED VERTICAL)
# =============================================================================
#st.markdown("<div id='mistura'></div>", unsafe_allow_html=True)
st.markdown("<div id='mistura' style='position: relative; top: -30px;'></div>",unsafe_allow_html=True,)
st.subheader("Mistura da ração · linha do tempo")

#st.markdown(
#    """
#    Cada componente da ração é apresentado em um **card vertical**,
#    em formato de linha do tempo:

#    - título do componente  
#    - valores de referência (alvo da formulação)  
#    - gráfico com os últimos 10 dias  
#    - diagnóstico automático abaixo do gráfico.
#    """
#)

# ----- Leitura específica do arquivo mistura_racao.csv -----
caminho_mistura = os.path.join(PASTA_DADOS, "mistura_racao.csv")

if not os.path.exists(caminho_mistura):
    st.warning(
        "Arquivo `mistura_racao.csv` não encontrado na pasta de dados. "
        "Crie-o com as colunas: data,%_milho,%_calcario,%_soja,%_nucleo."
    )
else:
    df_mist = pd.read_csv(caminho_mistura)

    # Normaliza nomes de colunas (remove espaços etc.)
    df_mist.columns = [c.strip() for c in df_mist.columns]

    # Mapeamento flexível dos nomes reais para nomes padrão
    colunas_alvo_mist = {
        "data": ["data", "Data", "DATA"],
        "milho_pct": ["milho_pct", "%_milho", "Milho", "Milho (%)", "milho (%)"],
        "calcario_pct": ["calcario_pct", "%_calcario", "Calcário", "Calcario", "Calcário (%)"],
        "farelo_soja_pct": [
            "farelo_soja_pct",
            "%_soja",
            "Farelo de soja",
            "Farelo de Soja (%)",
        ],
        "nucleo_pct": ["nucleo_pct", "%_nucleo", "Núcleo", "Nucleo", "Núcleo (%)"],
    }

    df_norm = pd.DataFrame()
    for destino, candidatos in colunas_alvo_mist.items():
        encontrado = None
        for nome in candidatos:
            if nome in df_mist.columns:
                encontrado = nome
                break
        if encontrado is None:
            st.error(
                f"Não encontrei coluna correspondente a '{destino}'. "
                f"Colunas atuais em mistura_racao.csv: {list(df_mist.columns)}"
            )
            st.stop()
        else:
            df_norm[destino] = df_mist[encontrado]

    df_mist = df_norm

    # Converte colunas de % para float (aceita "63,5" e "63.5")
    for c in ["milho_pct", "farelo_soja_pct", "calcario_pct", "nucleo_pct"]:
        df_mist[c] = (
            df_mist[c]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

    # Converte data no formato brasileiro (dia/mês/ano),
    # ordena e mantém sempre as 10 datas mais recentes
    df_mist["data"] = pd.to_datetime(
        df_mist["data"],
        format="%d/%m/%Y",   # força dia/mês/ano
        dayfirst=True,
        errors="raise",
    )

    df_mist = df_mist.sort_values("data")
    df_mist = df_mist.tail(10).copy()

    # -------------------- FEED VERTICAL: UM CARD POR COMPONENTE --------------------
    # Card Milho
    bloco_instagram_mistura(
        df=df_mist,
        col="milho_pct",
        titulo="Milho (%)",
        ref_min=59,  # faixa inferior específica para o milho
        ref_max=67,  # faixa superior específica para o milho
        texto_ref="""
        **Referência teórica:** 62 % (faixa alvo: 59% – 67 %).  
        **Função:** principal fonte de energia da dieta.
        """,
        nome_curto="Milho",
        ylim=(40, 90),
    )

    # Card Farelo de soja
    bloco_instagram_mistura(
        df=df_mist,
        col="farelo_soja_pct",
        titulo="Farelo de soja (%)",
        ref_min=22,   # faixa específica para o farelo de soja
        ref_max=26,
        texto_ref="""
        **Referência teórica:** 24 % (faixa alvo: 22.8% – 25.2%)  
        **Função:** principal fonte de proteína da formulação.
        """,
        nome_curto="Farelo de soja",
        ylim=(0, 40),
    )

    # Card Calcário
    bloco_instagram_mistura(
        df=df_mist,
        col="calcario_pct",
        titulo="Calcário (%)",
        ref_min=9,    # faixa específica para o calcário
        ref_max=11,
        texto_ref="""
        **Referência teórica:** 10 % (faixa alvo: 9.5% – 10.5%)  
        **Função:** oferta de cálcio para qualidade de casca.
        """,
        nome_curto="Calcário",
        ylim=(0, 20),
    )

    # Card Núcleo
    bloco_instagram_mistura(
        df=df_mist,
        col="nucleo_pct",
        titulo="Núcleo (%)",
        ref_min=3,    # faixa específica para o núcleo
        ref_max=5,
        texto_ref="""
        **Referência teórica:** 4 % (faixa alvo: 3–5 %)  
        **Função:** vitaminas, minerais e aditivos concentrados.
        """,
        nome_curto="Núcleo",
        ylim=None,
    )

    st.caption(
        "Cada card utiliza as 10 leituras mais recentes do arquivo `mistura_racao.csv`."
    )


# =============================================================================
# PARTE 6 – SEÇÃO 2: CONSUMO (VERTICAL)
# =============================================================================
st.markdown("<div id='consumo' style='position: relative; top: -30px;'></div>",unsafe_allow_html=True,)
st.subheader("Consumo de ração (g/ave/dia) · linha do tempo")

if "consumo_g_ave_dia" in dados_filtrados.columns:
    # Gráfico principal (em coluna única)
    st.line_chart(
        dados_filtrados.set_index("data")[["consumo_g_ave_dia"]],
        height=300,
    )

    # Texto de referência e diagnóstico abaixo do gráfico
    st.markdown(
        f"""
        **Referência de manejo:** faixa ideal de **{CONSUMO_MIN:.0f}–{CONSUMO_MAX:.0f} g/ave/dia**.  

        **Diagnóstico automático:**  
        - Consumo médio no período filtrado: **{consumo_medio:.1f} g/ave/dia**.  
        - Valores abaixo da faixa podem indicar **baixa ingestão**, competição, problemas de comedouro ou ambiência.  
        - Valores muito acima podem indicar **desperdício** ou ajustes inadequados de densidade/manejo.
        """
    )
else:
    st.info("Coluna 'consumo_g_ave_dia' não encontrada nos dados.")

st.markdown("---")


# =============================================================================
# PARTE 7 – SEÇÃO 3: PRODUÇÃO E PERDAS (VERTICAL)
# =============================================================================
st.markdown("<div id='producao' style='position: relative; top: -30px;'></div>",unsafe_allow_html=True,)
st.subheader("Produção e perdas de ovos · linha do tempo")

if {"ovos_granja", "ovos_escola"}.issubset(dados_filtrados.columns):
    # Gráfico 1: linhas de produção (granja vs escola)
    st.markdown("### Produção diária de ovos (granja vs. escola)")
    st.line_chart(
        dados_filtrados.set_index("data")[["ovos_granja", "ovos_escola"]],
        height=300,
    )

    st.markdown(
        """
        **Referência conceitual:**  
        - A curva da escola deveria acompanhar de perto a curva da granja.  
        - Diferenças sistemáticas indicam perdas no transporte, registro ou manejo.
        """
    )

    # Gráfico 2: barras de perdas
    st.markdown("### Perdas no trajeto (granja → escola)")
    st.bar_chart(
        dados_filtrados.set_index("data")[["perda_ovos"]],
        height=300,
    )

    total_granja = dados_filtrados["ovos_granja"].sum()
    total_escola = dados_filtrados["ovos_escola"].sum()
    total_perdas = dados_filtrados["perda_ovos"].sum()

    # Diagnóstico abaixo dos gráficos
    st.markdown(
        f"""
        **Diagnóstico de produção e perdas (período filtrado):**  

        - Total produzido na granja: **{total_granja:.0f} ovos**  
        - Total registrado na escola: **{total_escola:.0f} ovos**  
        - Diferença absoluta (perdas acumuladas): **{total_perdas:.0f} ovos**  

        Se a diferença for recorrente e significativa, vale investigar:  
        - acondicionamento das bandejas e proteção durante o transporte;  
        - conferência de contagem na saída da granja e na chegada à escola;  
        - registro diário em planilhas para rastrear dias mais críticos.
        """
    )
else:
    st.info("Colunas 'ovos_granja' e 'ovos_escola' não encontradas nos dados.")

st.markdown("---")


# =============================================================================
# PARTE 8 – SEÇÃO 4: QUALIDADE & SANIDADE (VERTICAL)
# =============================================================================
st.markdown("<div id='qualidade' style='position: relative; top: -30px;'></div>",unsafe_allow_html=True,)
st.subheader("Qualidade dos ovos & sanidade · linha do tempo")

# Gráfico de percentual de defeituosos
if {"pct_defeituosos"}.issubset(dados_filtrados.columns):
    st.markdown("### Percentual de ovos não conformes (%)")
    st.line_chart(
        dados_filtrados.set_index("data")[["pct_defeituosos"]],
        height=300,
    )
    st.markdown(
        """
        **Referência prática:**  
        - Idealmente, o percentual de ovos não conformes deve ser mantido **o mais baixo possível**,  
          tipicamente abaixo de **3–5%**, dependendo do sistema de produção.  
        - Picos de defeitos podem estar associados a problemas de nutrição, sanidade ou manejo.
        """
    )

# Cards de métricas (mantidos em duas colunas só para compactar)
col_q1, col_q2 = st.columns(2)
with col_q1:
    if "ovos_defeituosos" in dados_filtrados.columns:
        total_def = dados_filtrados["ovos_defeituosos"].sum()
        st.metric("Total de ovos não conformes (período)", f"{total_def:.0f}")
with col_q2:
    if "aves_doentes" in dados_filtrados.columns:
        total_doentes = dados_filtrados["aves_doentes"].sum()
        st.metric("Soma de aves doentes observadas", f"{total_doentes:.0f}")

# Tabela detalhada ao final como "rodapé" do feed
st.markdown("### Tabela detalhada (dados filtrados)")
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

# =====================================================================
# DISPARA O SCROLL APÓS DESENHAR TODA A PÁGINA
# =====================================================================
if secao == "Topo":
    scroll_to("topo")
elif secao == "Mistura da ração":
    scroll_to("mistura")
elif secao == "Consumo":
    scroll_to("consumo")
elif secao == "Produção e perdas":
    scroll_to("producao")
elif secao == "Qualidade & sanidade":
    scroll_to("qualidade")


# =============================================================================
# PARTE 1 – IMPORTS E CONFIGURAÇÃO BÁSICA
# =============================================================================
import os
from glob import glob

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
import streamlit.components.v1 as components


# Configuração da página do Streamlit
st.set_page_config(
    page_title="Avicultura - Dashboard automático",
    layout="wide",
)

# Âncora de topo para navegação
st.markdown("<div id='topo' style='position: relative; top: -30px;'></div>", unsafe_allow_html=True)

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

dados["data"] = pd.to_datetime(
    dados["data"].astype(str).str.strip(),
    format="%d/%m/%Y",
    dayfirst=True,
    errors="coerce",
)

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

if {"ovos_quebrados", "ovos_sem_casca", "ovos_deformados", "ovos_granja"}.issubset(dados.columns):
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


# =============================================================================
# PARTE 4 – FUNÇÕES AUXILIARES (GRÁFICO E DIAGNÓSTICO)
# =============================================================================
def _build_x_axis_and_scale(df_plot):
    """
    Constrói eixo X padronizado (datas) para todos os gráficos Altair:
    - Domínio: últimos 30 dias até a data de hoje;
    - Ticks explícitos a cada 7 dias, SEMPRE terminando em hoje;
    - Formato 'dia mês' (ex.: 05 Dez) com meses em português.
    """
    # Janela fixa: últimos 30 dias até hoje
    hoje = pd.Timestamp.today().normalize()
    dmin = hoje - pd.Timedelta(days=30)
    dmax = hoje

    # Ticks semanais: hoje, hoje-7, hoje-14, ... dentro do domínio
    valores_ticks = []
    dia = hoje
    while dia >= dmin:
        valores_ticks.append(dia)
        dia -= pd.Timedelta(days=7)
    valores_ticks = list(reversed(valores_ticks))  # em ordem crescente

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

    x_axis = alt.Axis(
        title="",
        format="%d %b",
        values=valores_ticks,  # ticks explícitos (hoje, -7, -14, ...)
        labelExpr=label_expr,
    )

    x_scale = alt.Scale(domain=[dmin, dmax])

    return x_axis, x_scale




def chart_serie_altair(
    df,
    col,
    titulo,
    ref_min=None,
    ref_max=None,
    ylim=None,
    y_label=None,
    value_format=".1f",
    tooltip_label=None,
):
    """
    Cria um gráfico Altair de série temporal com:
      - eixo X padronizado (datas em PT-BR, ticks a cada 5 dias);
      - faixa de referência opcional [ref_min, ref_max];
      - personalização do rótulo do eixo Y e formatação de valores.
    """
    if df.empty or col not in df.columns:
        return None

    df_plot = df.copy()

    if y_label is None:
        y_label = "%"
    if tooltip_label is None:
        tooltip_label = "Valor"

    x_axis, x_scale = _build_x_axis_and_scale(df_plot)
    scale_y = alt.Scale(domain=ylim, nice=False) if ylim else alt.Undefined

    base = alt.Chart(df_plot).encode(
        x=alt.X("data:T", axis=x_axis, scale=x_scale)
    )

    camadas = []

    # Faixa de referência, se fornecida
    if (ref_min is not None) and (ref_max is not None):
        df_plot["ref_min"] = ref_min
        df_plot["ref_max"] = ref_max
        faixa = base.mark_area(opacity=0.15).encode(
            y=alt.Y("ref_min:Q", scale=scale_y),
            y2=alt.Y2("ref_max:Q"),
        )
        camadas.append(faixa)

    # Linha principal
    linha = base.mark_line().encode(
        y=alt.Y(f"{col}:Q", title=y_label, scale=scale_y),
    )
    camadas.append(linha)

    # Pontos
    pontos = base.mark_point(size=60).encode(
        y=alt.Y(f"{col}:Q", scale=scale_y),
        tooltip=[
            alt.Tooltip("data:T", title="Data"),
            alt.Tooltip(f"{col}:Q", title=tooltip_label, format=value_format),
        ],
    )
    camadas.append(pontos)

    # Rótulos numéricos sobre os pontos
    textos = base.mark_text(dy=-20, fontSize=10, color="white").encode(
        y=alt.Y(f"{col}:Q", scale=scale_y),
        text=alt.Text(f"{col}:Q", format=value_format),
    )
    camadas.append(textos)

    chart = alt.layer(*camadas).properties(
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

    if media_ultimos > ref_max:
        tendencia = "acima"
    elif media_ultimos < ref_min:
        tendencia = "abaixo"
    else:
        tendencia = "dentro"

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

def diagnostico_consumo(df, col, ref_min, ref_max, nome="Consumo de ração"):
    """
    Gera um texto de diagnóstico para o CONSUMO de ração (g/ave/dia),
    usando a faixa [ref_min, ref_max].

    Inclui:
    - contagem de dias abaixo / dentro / acima da faixa;
    - análise da média dos 2 últimos registros;
    - interpretação zootécnica para consumo baixo, alto ou dentro da faixa.
    """
    if df.empty or col not in df.columns:
        return f"Diagnóstico para {nome}: série sem dados suficientes."

    y = df[col].dropna()
    if y.empty:
        return f"Diagnóstico para {nome}: série sem dados válidos (após remoção de NaN)."

    # -------------------------------------------------------------------------
    # 1) Estatística global: quantos dias em cada faixa
    # -------------------------------------------------------------------------
    dentro = ((y >= ref_min) & (y <= ref_max)).sum()
    acima = (y > ref_max).sum()
    abaixo = (y < ref_min).sum()
    total = len(y)

    partes = []
    partes.append(
        f"No período analisado (**{total} dias** com dados válidos), "
        f"**{abaixo}** dia(s) ficaram **abaixo** da faixa alvo "
        f"({ref_min:.0f}–{ref_max:.0f} g/ave/dia), "
        f"**{dentro}** dentro e **{acima}** **acima**."
    )

    if dentro == total:
        partes.append(
            "O padrão de consumo está **bem ajustado** à faixa recomendada, "
            "o que tende a favorecer estabilidade de produção e conversão alimentar."
        )
    elif abaixo > acima:
        partes.append(
            "Predomina consumo **abaixo** da faixa ideal, sugerindo possível limitação de ingestão "
            "ou problemas pontuais de manejo/ambiência."
        )
    elif acima > abaixo:
        partes.append(
            "Predomina consumo **acima** da faixa ideal, indicando risco de **desperdício de ração** "
            "e aumento de custo por dúzia de ovos se a produção não acompanha esse aumento."
        )
    else:
        partes.append(
            "Há **variabilidade relevante** no consumo, alternando dias abaixo e acima da faixa. "
            "Vale investigar se há mudanças de manejo, temperatura ou formulação ao longo do período."
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
        f"A média dos **{janela_desc}** é **{media_ultimos:.1f} g/ave/dia**."
    )

    if media_ultimos > ref_max:
        tendencia = "acima"
    elif media_ultimos < ref_min:
        tendencia = "abaixo"
    else:
        tendencia = "dentro"

    # -------------------------------------------------------------------------
    # 3) Interpretação zootécnica da tendência recente
    # -------------------------------------------------------------------------
    if tendencia == "abaixo":
        alerta = (
            "A **tendência recente é de consumo ABAIXO da faixa ideal**. "
            "Isso pode indicar:\n"
            "- **Oferta diária de ração insuficiente**, os comedouros não estão recebendo ração suficiente no momento do trato;\n"
            "- **Baixa ingestão** por competição em comedouros ou densidade elevada;\n"
            "- Ambiência desfavorável (calor excessivo, frio intenso ou variações bruscas);\n"
            "- Problemas de acesso à ração (altura de comedouros, segregação de lotes, falhas na distribuição);\n"
            "- Palatabilidade ou granulometria inadequadas, levando as aves a selecionar ou desperdiçar parte da mistura.\n\n"
            "Do ponto de vista produtivo, consumo baixo tende a resultar em **queda de produção**, "
            "**ovos menores** e **pior persistência de postura** se mantido por vários dias. "
            "Recomenda-se conferir se a **quantidade oferecida por trato** está adequada e se os comedouros "
            "não permanecem vazios por longos períodos."
        )
    elif tendencia == "acima":
        alerta = (
            "A **tendência recente é de consumo ACIMA da faixa ideal**. "
            "Situações possíveis:\n"
            "- **Excesso de ração ofertada em cada trato**, com comedouros permanecendo cheios e "
            "sobras significativas ao final do dia (ração velha, fina e mais sujeita a seleção e desperdício);\n"
            "- Ajustes de manejo que aumentaram o acesso à ração, mas sem controle fino de quantidade ofertada;\n"
            "- Granulometria muito fina ou muito grossa, levando a **desperdício por seleção** e queda de eficiência;\n"
            "- Formulação com densidade energética mais baixa, fazendo a ave comer mais para compensar.\n\n"
            "Se o aumento de consumo **não vier acompanhado de ganho proporcional em produção**, "
            "há risco de **piorar a conversão alimentar** e **elevar o custo por dúzia de ovos**. "
            "Vale revisar se há **sobras excessivas nos comedouros** e ajustar a quantidade fornecida por trato."
        )
    else:  # dentro da faixa
        alerta = (
            "A **tendência recente permanece DENTRO da faixa recomendada**, "
            "o que sugere um **ajuste adequado entre ambiência, manejo, quantidade ofertada e formulação**. "
            "Vale manter o monitoramento contínuo para captar rapidamente qualquer desvio, "
            "especialmente em períodos de mudança de temperatura, fase de postura ou alteração de ração."
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

    chart = chart_serie_altair(
        df=df,
        col=col,
        titulo=titulo,
        ref_min=ref_min,
        ref_max=ref_max,
        ylim=ylim,
        y_label="%",
        value_format=".1f",
        tooltip_label=f"{nome_curto} (%)",
    )
    if chart is not None:
        st.altair_chart(chart, use_container_width=True)

    diag = diagnostico_serie(df, col, ref_min, ref_max, nome_curto)
    st.markdown(f"**Diagnóstico ({nome_curto}):** {diag}")

    st.markdown("---")


# =============================================================================
# PARTE 5 – SEÇÃO 1: MISTURA DA RAÇÃO
# =============================================================================
st.markdown("<div id='mistura' style='position: relative; top: -40px;'></div>", unsafe_allow_html=True)
st.subheader("Mistura da ração · linha do tempo")

caminho_mistura = os.path.join(PASTA_DADOS, "mistura_racao.csv")

if not os.path.exists(caminho_mistura):
    st.warning(
        "Arquivo `mistura_racao.csv` não encontrado na pasta de dados. "
        "Crie-o com as colunas: data,%_milho,%_calcario,%_soja,%_nucleo."
    )
else:
    df_mist = pd.read_csv(caminho_mistura)

    df_mist.columns = [c.strip() for c in df_mist.columns]

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

    for c in ["milho_pct", "farelo_soja_pct", "calcario_pct", "nucleo_pct"]:
        df_mist[c] = (
            df_mist[c]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

    df_mist["data"] = pd.to_datetime(
        df_mist["data"],
        format="%d/%m/%Y",
        dayfirst=True,
        errors="raise",
    )

    df_mist = df_mist.sort_values("data")
    df_mist = df_mist.tail(10).copy()

    bloco_instagram_mistura(
        df=df_mist,
        col="milho_pct",
        titulo="Milho (%)",
        ref_min=59,
        ref_max=67,
        texto_ref="""
        **Referência teórica:** 62 % (faixa alvo: 59% – 67 %).  
        **Função:** principal fonte de energia da dieta.
        """,
        nome_curto="Milho",
        ylim=(40, 90),
    )

    bloco_instagram_mistura(
        df=df_mist,
        col="farelo_soja_pct",
        titulo="Farelo de soja (%)",
        ref_min=22,
        ref_max=26,
        texto_ref="""
        **Referência teórica:** 24 % (faixa alvo: 22.8% – 25.2%)  
        **Função:** principal fonte de proteína da formulação.
        """,
        nome_curto="Farelo de soja",
        ylim=(0, 40),
    )

    bloco_instagram_mistura(
        df=df_mist,
        col="calcario_pct",
        titulo="Calcário (%)",
        ref_min=9,
        ref_max=11,
        texto_ref="""
        **Referência teórica:** 10 % (faixa alvo: 9.5% – 10.5%)  
        **Função:** oferta de cálcio para qualidade de casca.
        """,
        nome_curto="Calcário",
        ylim=(0, 20),
    )

    bloco_instagram_mistura(
        df=df_mist,
        col="nucleo_pct",
        titulo="Núcleo (%)",
        ref_min=3,
        ref_max=5,
        texto_ref="""
        **Referência teórica:** 4 % (faixa alvo: 3–5 %)  
        **Função:** vitaminas, minerais e aditivos concentrados.
        """,
        nome_curto="Núcleo",
        ylim=None,
    )


# =============================================================================
# PARTE 6 – SEÇÃO 2: CONSUMO
# =============================================================================
# =============================================================================
# PARTE 6 – SEÇÃO 2: CONSUMO
# =============================================================================
st.markdown("<div id='consumo' style='position: relative; top: -40px;'></div>", unsafe_allow_html=True)
st.markdown("### Consumo de ração (g/ave/dia)")

st.markdown("""
**Referência de manejo:** faixa ideal de **105–115 g/ave/dia**.  
**Função:** garantir ingestão suficiente para atender o requerimento de energia e nutrientes,
mantendo produção, peso corporal e qualidade de casca adequados.
""")

caminho_consumo = os.path.join(PASTA_DADOS, "consumo_racao.csv")

if not os.path.exists(caminho_consumo):
    st.warning(
        "Arquivo `consumo_racao.csv` não encontrado na pasta de dados. "
        "Crie-o com as colunas: data,consumo_g_ave_dia."
    )
else:
    df_consumo = pd.read_csv(caminho_consumo)

    # Remove espaços dos nomes de coluna
    df_consumo.columns = [c.strip() for c in df_consumo.columns]

    if not {"data", "consumo_g_ave_dia"}.issubset(df_consumo.columns):
        st.error(
            "O arquivo `consumo_racao.csv` deve conter as colunas "
            "`data` e `consumo_g_ave_dia`."
        )
    else:
        # Converte data
        df_consumo["data"] = pd.to_datetime(
            df_consumo["data"],
            format="%d/%m/%Y",
            dayfirst=True,
            errors="coerce",
        )
        df_consumo = df_consumo.dropna(subset=["data"])

        # Garante numérico, aceitando vírgula
        df_consumo["consumo_g_ave_dia"] = (
            df_consumo["consumo_g_ave_dia"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

        # Aplica o mesmo filtro de período da página
        mask_consumo = (
            (df_consumo["data"].dt.date >= ini)
            & (df_consumo["data"].dt.date <= fim)
        )
        df_consumo_filtrado = df_consumo[mask_consumo].copy()

        if df_consumo_filtrado.empty:
            st.info("Não há dados de `consumo_racao.csv` dentro do período selecionado.")
        else:
            # Gráfico em linha com faixa de referência
            chart_consumo = chart_serie_altair(
                df=df_consumo_filtrado,
                col="consumo_g_ave_dia",
                titulo="Consumo de ração (g/ave/dia)",
                ref_min=CONSUMO_MIN,
                ref_max=CONSUMO_MAX,
                ylim=(80, 140),
                y_label="Consumo (g/ave/dia)",
                value_format=".1f",
                tooltip_label="Consumo (g/ave/dia)",
            )

            if chart_consumo is not None:
                st.altair_chart(chart_consumo, use_container_width=True)

            # Estatística para o diagnóstico
            consumo_medio_periodo = df_consumo_filtrado["consumo_g_ave_dia"].mean()

            diag_consumo = diagnostico_consumo(
                df=df_consumo_filtrado,
                col="consumo_g_ave_dia",
                ref_min=CONSUMO_MIN,
                ref_max=CONSUMO_MAX,
                nome="Consumo de ração (g/ave/dia)",
            )

            # Somente o diagnóstico automático abaixo do gráfico
            st.markdown(f"**Diagnóstico (Consumo de ração):** {diag_consumo}")

            st.markdown("---")


# =============================================================================
# PARTE 7 – SEÇÃO 3: PRODUÇÃO E PERDAS (VERTICAL)
# =============================================================================
st.markdown("<div id='producao' style='position: relative; top: -40px;'></div>", unsafe_allow_html=True)
st.subheader("Produção e perdas de ovos · linha do tempo")

if {"ovos_granja", "ovos_escola"}.issubset(dados_filtrados.columns):
    df_prod = dados_filtrados[["data", "ovos_granja", "ovos_escola"]].dropna(subset=["ovos_granja", "ovos_escola"]).copy()

    if not df_prod.empty:
        df_long = df_prod.melt(id_vars="data", value_vars=["ovos_granja", "ovos_escola"], var_name="origem", value_name="ovos")

        x_axis, x_scale = _build_x_axis_and_scale(df_long)

        chart_prod = (
            alt.Chart(df_long)
            .encode(
                x=alt.X("data:T", axis=x_axis, scale=x_scale),
                y=alt.Y("ovos:Q", title="Produção de ovos (unid./dia)"),
                color=alt.Color(
                    "origem:N",
                    title="Origem",
                    scale=alt.Scale(domain=["ovos_granja", "ovos_escola"],
                                    range=["#1f77b4", "#ff7f0e"]),
                    legend=alt.Legend(labelExpr="replace(replace(datum.label,'ovos_granja','Granja'),'ovos_escola','Escola')"),
                ),
                tooltip=[
                    alt.Tooltip("data:T", title="Data"),
                    alt.Tooltip("origem:N", title="Origem"),
                    alt.Tooltip("ovos:Q", title="Ovos", format=".0f"),
                ],
            )
            .mark_line()
        )

        pontos_prod = (
            alt.Chart(df_long)
            .encode(
                x=alt.X("data:T", axis=x_axis, scale=x_scale),
                y=alt.Y("ovos:Q"),
                color="origem:N",
            )
            .mark_point(size=50)
        )

        st.markdown("### Produção diária de ovos (granja vs. escola)")
        st.altair_chart((chart_prod + pontos_prod).properties(height=300), use_container_width=True)

        st.markdown(
            """
            **Referência conceitual:**  
            - A curva da escola deveria acompanhar de perto a curva da granja.  
            - Diferenças sistemáticas indicam perdas no transporte, registro ou manejo.
            """
        )

    if "perda_ovos" in dados_filtrados.columns:
        df_perdas = dados_filtrados[["data", "perda_ovos"]].dropna(subset=["perda_ovos"]).copy()

        chart_perdas = chart_serie_altair(
            df=df_perdas,
            col="perda_ovos",
            titulo="Perdas no trajeto (granja → escola)",
            ref_min=None,
            ref_max=None,
            ylim=None,
            y_label="Perdas (ovos)",
            value_format=".0f",
            tooltip_label="Perdas (ovos)",
        )

        st.markdown("### Perdas no trajeto (granja → escola)")
        if chart_perdas is not None:
            st.altair_chart(chart_perdas, use_container_width=True)

    total_granja = dados_filtrados["ovos_granja"].sum()
    total_escola = dados_filtrados["ovos_escola"].sum()
    total_perdas = dados_filtrados["perda_ovos"].sum()

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
st.markdown("<div id='qualidade' style='position: relative; top: -40px;'></div>", unsafe_allow_html=True)
st.subheader("Qualidade dos ovos & sanidade · linha do tempo")

if "pct_defeituosos" in dados_filtrados.columns:
    df_qual = dados_filtrados[["data", "pct_defeituosos"]].dropna(subset=["pct_defeituosos"]).copy()

    chart_qual = chart_serie_altair(
        df=df_qual,
        col="pct_defeituosos",
        titulo="Percentual de ovos não conformes (%)",
        ref_min=0,
        ref_max=5,
        ylim=None,
        y_label="% de ovos não conformes",
        value_format=".1f",
        tooltip_label="% não conformes",
    )

    if chart_qual is not None:
        st.altair_chart(chart_qual, use_container_width=True)

    st.markdown(
        """
        **Referência prática:**  
        - Idealmente, o percentual de ovos não conformes deve ser mantido **o mais baixo possível**,  
          tipicamente abaixo de **3–5%**, dependendo do sistema de produção.  
        - Picos de defeitos podem estar associados a problemas de nutrição, sanidade ou manejo.
        """
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

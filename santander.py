# -*- coding: utf-8 -*-
# Plataforma Preditiva de Risco e Oportunidades (Regras + IA)
# Versão sem ML — mantém as legendas originais e as melhorias visuais/UX

import streamlit as st
import pandas as pd
import numpy as np
import datetime
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import graphviz
import math

# =========================
# 0) CONFIG / ESTILO
# =========================
st.set_page_config(
    layout="wide",
    page_title="Plataforma de Risco e Oportunidades (Regras + IA)",
    page_icon="🧠"
)

# Paleta
SANTANDER_RED = "#EC0000"
PRIMARY_TEXT_COLOR = "#000000"
COLOR_SUCCESS = "#006A4E"
COLOR_WARNING = "#FFBF00"
COLOR_INFO = "#0077C8"
COLOR_OPORTUNIDADE = {
    'Ouro':   {'bg': '#FFD700', 'text': PRIMARY_TEXT_COLOR},
    'Prata':  {'bg': '#E0E0E0', 'text': PRIMARY_TEXT_COLOR},
    'Bronze': {'bg': '#CD7F32', 'text': '#FFFFFF'}
}
pd.set_option("styler.render.max_elements", 1_000_000)

# Sidebar branding e CSS (visual moderno do Código 1)
st.sidebar.image("santander_logo.png", use_container_width=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    [data-testid="stSidebar"] .stRadio > label { display: none; }
    [data-testid="stSidebar"] .stRadio > div {
        gap: 12px; padding: 0; display: flex; flex-direction: column;
    }
    [data-testid="stSidebar"] .stRadio > div > label {
        background: linear-gradient(135deg, rgba(30,30,40,0.9) 0%, rgba(20,20,30,0.9) 100%);
        color: #e0e0e0; padding: 18px 20px; border-radius: 12px; border: none; cursor: pointer;
        transition: all 0.3s ease; font-weight: 500; font-size: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        position: relative; overflow: hidden; min-height: 56px; display: flex; align-items: center;
    }
    [data-testid="stSidebar"] .stRadio > div > label:hover {
        background: linear-gradient(135deg, rgba(40,40,50,0.95) 0%, rgba(30,30,40,0.95) 100%);
        transform: translateX(5px); box-shadow: 0 4px 12px rgba(236,0,0,0.15);
    }
    [data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
        background: linear-gradient(135deg, #EC0000 0%, #c40000 100%); color: white; font-weight: 600;
        box-shadow: 0 4px 16px rgba(236,0,0,0.4);
    }
    [data-testid="stSidebar"] .stRadio input[type="radio"] { display: none; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stSelectbox > div > div, .stMultiSelect > div > div { font-size: 16px; width: 100%; }
    .stSelectbox > div > div > div, .stMultiSelect > div > div > div { min-height: 45px; }
    .stSelectbox, .stMultiSelect { width: 100%; }
</style>
""", unsafe_allow_html=True)

# =========================
# 1) FUNÇÕES (REGRAS & UTILITÁRIOS)
# =========================
def classificar_saude_financeira(row):
    faturamento, saldo = row['VL_FATU'], row['VL_SLDO']
    if saldo >= 0:
        return 'Saudável'
    if faturamento <= 0:
        return 'Endividada'
    proporcao_divida = abs(saldo) / faturamento
    if proporcao_divida < 0.05: return 'Alavancagem Estratégica'
    if proporcao_divida < 0.10: return 'Ponto de Atenção'
    return 'Endividada'

def classificar_risco(row):
    score = 0
    score += {'Saudável': -3, 'Alavancagem Estratégica': -1, 'Ponto de Atenção': 2, 'Endividada': 4}.get(row['Saude_Financeira'], 0)
    score += {'Madura': -1, 'Inicial': 1}.get(row['Maturidade'], 0)
    score += {'Alta Concentração em Clientes': 1, 'Alta Concentração em Fornecedores': 1, 'Hub de Pagamentos': -1}.get(row['Dependencia_B2B'], 0)
    if score <= -2: return 'Muito Baixo'
    if score <= 0:  return 'Baixo'
    if score <= 2:  return 'Médio'
    if score <= 4:  return 'Alto'
    return 'Muito Alto'

def classificar_oportunidade(row):
    # Mesmo critério do Código 1 (mantém coerência das legendas)
    saude, risco = row['Saude_Financeira'], row['Risco_Santander']
    if saude == 'Saudável' and risco == 'Muito Baixo': return 'Ouro'
    if (saude == 'Alavancagem Estratégica' and risco in ['Baixo', 'Muito Baixo']) or (saude == 'Saudável' and risco == 'Baixo'): return 'Prata'
    if saude == 'Ponto de Atenção' and risco in ['Baixo', 'Médio']: return 'Bronze'
    return 'Não Elegível'

def classificar_b2b_intensidade(total):
    if total > 50: return 'Muito Alta'
    if total > 30: return 'Alta'
    if total > 10: return 'Média'
    if total > 5:  return 'Baixa'
    return 'Muito Baixa'

def analisar_dependencia(row):
    pgto, rcbe = row['Transacoes_Pagas'], row['Transacoes_Recebidas']
    if rcbe == 0 and pgto > 0: return 'Hub de Pagamentos'
    if pgto == 0 and rcbe > 0: return 'Concentradora de Recebimentos'
    if rcbe > 3 * pgto: return 'Alta Concentração em Clientes'
    if pgto > 3 * rcbe: return 'Alta Concentração em Fornecedores'
    return 'Relacionamento Equilibrado'

# =========================
# 2) DADOS / PIPELINE (SEM ML)
# =========================
@st.cache_data
def load_raw_data():
    base1_path, base2_path = Path("Base1.csv"), Path("Base2.csv")
    if not base1_path.exists() or not base2_path.exists():
        st.error("Arquivos de dados (Base1.csv, Base2.csv) não encontrados.")
        st.stop()
    base1 = pd.read_csv(base1_path, parse_dates=['DT_ABRT', 'DT_REFE'])
    try:
        base2 = pd.read_csv(base2_path, parse_dates=['DT_REFE'])
    except Exception:
        base2 = pd.read_csv(base2_path)
    return base1, base2

def _build_b2b_features(df2):
    df2_clean = df2.dropna(subset=['ID_PGTO', 'ID_RCBE'])
    rel_recebido = df2_clean.groupby('ID_RCBE')['ID_PGTO'].count().reset_index(name='Transacoes_Recebidas')
    rel_pago     = df2_clean.groupby('ID_PGTO')['ID_RCBE'].count().reset_index(name='Transacoes_Pagas')
    b2b = pd.merge(rel_recebido, rel_pago, left_on='ID_RCBE', right_on='ID_PGTO', how='outer')
    b2b = b2b.rename(columns={'ID_RCBE': 'ID'}).drop(columns='ID_PGTO').fillna(0)
    b2b['Total_Transacoes'] = b2b['Transacoes_Recebidas'] + b2b['Transacoes_Pagas']
    b2b['Intensidade_B2B']  = b2b['Total_Transacoes'].apply(classificar_b2b_intensidade)
    b2b['Dependencia_B2B']  = b2b.apply(analisar_dependencia, axis=1)
    return b2b

@st.cache_data
def get_processed_data():
    base1, base2 = load_raw_data()
    b2b = _build_b2b_features(base2)

    # Snapshot mais recente por ID (Código 1)
    df1_sorted = base1.sort_values(by=['ID', 'DT_REFE'], ascending=[True, False])
    df_latest  = df1_sorted.groupby('ID').first().reset_index()

    df = pd.merge(df_latest, b2b, on='ID', how='left')
    df.fillna({'Total_Transacoes': 0, 'Intensidade_B2B': 'Não Classificado', 'Dependencia_B2B': 'Não Classificado'}, inplace=True)

    hoje = datetime.datetime.now()
    df['Tempo_Atividade_Anos'] = round((hoje - df['DT_ABRT']).dt.days / 365.25, 1)
    df['Maturidade']           = df['Tempo_Atividade_Anos'].apply(lambda x: 'Madura' if x > 5 else 'Inicial')
    df['Saude_Financeira']     = df.apply(classificar_saude_financeira, axis=1)
    df['Perfil_da_Empresa']    = df['Maturidade'] + ' - ' + df['Saude_Financeira']
    df['Risco_Santander']      = df.apply(classificar_risco, axis=1)
    df['Oportunidade_Credito'] = df.apply(classificar_oportunidade, axis=1)

    return df, base1, base2

# =========================
# 3) IA (Gemini) — Simulada (sem dependência de ML)
# =========================
def gerar_prompt_analise_ia(empresa):
    return f"""
Você é um Analista de Crédito Sênior do Santander. Gere uma análise diagnóstica e recomendações em PT-BR.

**DADOS DO CLIENTE**
- CNPJ: {empresa['ID']}
- CNAE: {empresa.get('DS_CNAE', 'N/D')}
- Tempo de Atividade: {empresa.get('Tempo_Atividade_Anos', 0):.1f} anos ({empresa.get('Maturidade','N/D')})
- Faturamento mais recente: R$ {empresa.get('VL_FATU', 0):,.2f}
- Saldo mais recente: R$ {empresa.get('VL_SLDO', 0):,.2f}
- Saúde Financeira (Regras): {empresa.get('Saude_Financeira','N/D')}
- Nível de Risco (Regras): {empresa.get('Risco_Santander','N/D')}
- Perfil B2B: {empresa.get('Dependencia_B2B','N/D')} | Intensidade: {empresa.get('Intensidade_B2B','N/D')}
- Oportunidade (Regras): {empresa.get('Oportunidade_Credito','N/D')}

**Bloco 1: Análise Diagnóstica** (4-6 frases)
**Bloco 2: Recomendações Estratégicas** (2-3 bullets com produto + justificativa)
"""

def chamar_gemini_api(prompt: str) -> str:
    analise = (
        "A empresa apresenta perfil compatível com sua maturidade e uma estrutura financeira coerente com o fluxo de caixa. "
        "O comportamento transacional B2B não sugere dependências críticas, e o nível de risco, pelas regras do modelo, é adequado. "
        "Há espaço para alocação tática de crédito e oferta de soluções de gestão de caixa, respeitando a governança de risco."
    )
    recomendacoes = """
- **Capital de Giro Rotativo:** garante flexibilidade operacional diante da sazonalidade de caixa.
- **Antecipação de Recebíveis:** otimiza o fluxo de caixa e reduz pressão sobre o saldo.
- **Produtos de Investimento (CDB Corporativo):** rentabiliza excedentes com liquidez para necessidades táticas.
"""
    return f"### Análise Diagnóstica\n{analise}\n\n### Recomendações Estratégicas\n{recomendacoes}"

# === LLM Comparativo (Simulado + Regras): para 2+ CNPJs ===
def gerar_prompt_comparativo_ia(empresas_df: pd.DataFrame) -> str:
    linhas = []
    for _, r in empresas_df.iterrows():
        linhas.append(
            f"- ID {r['ID']} | Setor: {r['DS_CNAE']} | Fatu: R$ {r['VL_FATU']:,.0f} | "
            f"Saldo: R$ {r['VL_SLDO']:,.0f} | Saúde: {r['Saude_Financeira']} | "
            f"Risco: {r['Risco_Santander']} | Oportunidade: {r['Oportunidade_Credito']} | "
            f"B2B: {r['Dependencia_B2B']} ({r['Intensidade_B2B']})"
        )
    prompt = (
        "Compare logicamente os CNPJs abaixo, seguindo as REGRAS: "
        "1) priorizar oportunidades (Ouro > Prata > Bronze > Não Elegível); "
        "2) em empate, priorizar maior faturamento; "
        "3) alertar para Riscos 'Alto'/'Muito Alto'; "
        "4) evidenciar dependências B2B críticas; "
        "5) sugerir próximos passos comerciais por cluster (expansão, giro, monitoramento).\n\n" +
        "\n".join(linhas)
    )
    return prompt

def sintetizar_comparativo_logico(empresas_df: pd.DataFrame) -> str:
    # ranking por oportunidade
    rank_map = {'Ouro': 1, 'Prata': 2, 'Bronze': 3, 'Não Elegível': 4}
    df = empresas_df.copy()
    df['__rank'] = df['Oportunidade_Credito'].map(rank_map).fillna(5)
    df = df.sort_values(['__rank', 'VL_FATU'], ascending=[True, False])

    # Top oportunidades
    top_txt = []
    for _, r in df.head(min(3, len(df))).iterrows():
        top_txt.append(f"**{r['ID']}** (Tier **{r['Oportunidade_Credito']}**, Fatu R$ {r['VL_FATU']:,.0f}, Risco {r['Risco_Santander']})")

    # Alertas de risco alto
    risco_alto = empresas_df[empresas_df['Risco_Santander'].isin(['Alto', 'Muito Alto'])]['ID'].tolist()

    # Dependências críticas
    deps_criticas = ['Alta Concentração em Clientes', 'Alta Concentração em Fornecedores', 'Hub de Pagamentos', 'Concentradora de Recebimentos']
    dep_flags = empresas_df[empresas_df['Dependencia_B2B'].isin(deps_criticas)][['ID','Dependencia_B2B']].values.tolist()

    # Maior faturamento
    maior_fat = empresas_df.loc[empresas_df['VL_FATU'].idxmax()] if not empresas_df.empty else None

    # Recomendações táticas por cluster
    cluster_expansao = df[df['Oportunidade_Credito'].isin(['Ouro', 'Prata'])]['ID'].tolist()
    cluster_giro     = df[df['Oportunidade_Credito'].isin(['Bronze'])]['ID'].tolist()
    cluster_monitor  = df[(~df['Oportunidade_Credito'].isin(['Ouro','Prata','Bronze'])) | (df['Risco_Santander'].isin(['Alto','Muito Alto']))]['ID'].tolist()

    bullets = []
    if top_txt:
        bullets.append("**Prioridade Comercial (Top oportunidades):** " + "; ".join(top_txt) + ".")
    if maior_fat is not None:
        bullets.append(f"**Maior potencial de ticket** pelo faturamento: **{maior_fat['ID']}** (R$ {maior_fat['VL_FATU']:,.0f}).")
    if risco_alto:
        bullets.append(f"**Alertas de risco**: {', '.join(map(str, risco_alto))} (nível **Alto/Muito Alto**). Abordagem conservadora e acompanhamento próximo.")
    if dep_flags:
        bullets.append("**Dependências B2B críticas**: " + "; ".join([f"{i} ({d})" for i,d in dep_flags]) + ".")
    if cluster_expansao:
        bullets.append(f"**Expansão** (Ouro/Prata): {', '.join(map(str, cluster_expansao))} → linhas de expansão, giro rotativo, investimentos.")
    if cluster_giro:
        bullets.append(f"**Giro/Curto prazo** (Bronze): {', '.join(map(str, cluster_giro))} → giro curto, desconto de duplicatas.")
    if cluster_monitor:
        bullets.append(f"**Monitoramento** (risco/sem elegibilidade): {', '.join(map(str, cluster_monitor))} → adequar prazos, reduzir concentração e revisar estrutura.")

    return "\n".join([f"- {b}" for b in bullets]) if bullets else "- Amostra insuficiente para comparação."

def chamar_gemini_api_comparativo(prompt: str, empresas_df: pd.DataFrame) -> str:
    # Simulação: usa lógica determinística acima, mas mantém a assinatura de uma chamada LLM.
    corpo = sintetizar_comparativo_logico(empresas_df)
    return f"### 🧠 Comparação por IA (LLM + Regras)\n{corpo}"

# =========================
# 4) APP — NAVEGAÇÃO
# =========================
pagina = st.sidebar.radio(
    "NAVEGACAO",
    ["Visão Geral da Carteira", "Insights de CNPJs", "Cadeia de Valor"],
    label_visibility="collapsed"
)

# Carrega dados processados
df_processed, base1, base2 = get_processed_data()

# =========================
# 5) PÁGINA 1 — VISÃO GERAL (SEM ML)
# =========================
if pagina == "Visão Geral da Carteira":
    st.title('Dashboard de Risco e Oportunidades')
    st.subheader("Olá Eduardo, essa é sua carteira de clientes PJ")

    # Filtros
    cnae_options         = ['Todos'] + sorted(df_processed['DS_CNAE'].dropna().unique().tolist())
    perfil_options       = ['Todos'] + sorted(df_processed['Perfil_da_Empresa'].dropna().unique().tolist())
    risco_options        = ['Todos'] + ['Muito Baixo', 'Baixo', 'Médio', 'Alto', 'Muito Alto']
    oportunidade_options = ['Todos'] + ['Ouro', 'Prata', 'Bronze', 'Não Elegível']

    with st.expander("🔎 Filtros da Carteira", expanded=False):
        colA, colB, colC, colD = st.columns(4)
        with colA:
            selected_cnae = st.selectbox('Setor (CNAE)', cnae_options, index=0)
        with colB:
            selected_perfil = st.selectbox('Perfil da Empresa', perfil_options, index=0)
        with colC:
            selected_risco = st.selectbox('Nível de Risco', risco_options, index=0)
        with colD:
            selected_oportunidade = st.selectbox('Oportunidade de Crédito', oportunidade_options, index=0)

    filtered_df = df_processed.copy()
    if selected_cnae != 'Todos':
        filtered_df = filtered_df[filtered_df['DS_CNAE'] == selected_cnae]
    if selected_perfil != 'Todos':
        filtered_df = filtered_df[filtered_df['Perfil_da_Empresa'] == selected_perfil]
    if selected_risco != 'Todos':
        filtered_df = filtered_df[filtered_df['Risco_Santander'] == selected_risco]
    if selected_oportunidade != 'Todos':
        filtered_df = filtered_df[filtered_df['Oportunidade_Credito'] == selected_oportunidade]

    # KPIs
    st.subheader("Visão Geral da Carteira de Clientes")
    st.caption("Os cartões abaixo resumem os dados das empresas selecionadas nos filtros.")
    k1, k2 = st.columns(2)
    with k1:
        with st.container(border=True):
            st.metric("🏢 Clientes Total", f"{len(filtered_df):,}")
    with k2:
        with st.container(border=True):
            oportunidades_df = filtered_df[filtered_df['Oportunidade_Credito'] != 'Não Elegível']
            st.metric("💰 Clientes com Oportunidade de Crédito", f"{len(oportunidades_df):,}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ====== Tabela detalhada (com busca & paginação) ======
    st.subheader('Indicador de Oportunidade de Crédito')

    def style_oportunidade(val):
        style = COLOR_OPORTUNIDADE.get(val)
        if style:
            return f'background-color: {style["bg"]}; color: {style["text"]}; border-radius: 8px; padding: 3px 10px; text-align: center; font-weight: 500; font-size: 12px;'
        return ''

    with st.container(border=True):
        search_query = st.text_input("Pesquisar por ID (CNPJ)", placeholder="Digite o CNPJ ou parte dele...")
        df_view = filtered_df.copy()
        if search_query:
            df_view['ID'] = df_view['ID'].astype(str)
            df_view = df_view[df_view['ID'].str.contains(search_query, case=False)]

        total_rows = len(df_view)
        col1, col2, col_info = st.columns([1, 2, 3])
        with col1:
            items_per_page = st.selectbox("Itens por página", [10, 25, 50, 100], index=0)
        total_pages = math.ceil(total_rows / items_per_page) if total_rows > 0 else 1
        with col2:
            page_number = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)

        start_idx = (page_number - 1) * items_per_page
        end_idx   = start_idx + items_per_page
        page_df   = df_view.iloc[start_idx:end_idx]

        with col_info:
            st.markdown(f"&nbsp; <br> **Mostrando {len(page_df)} de {total_rows} resultados.**", unsafe_allow_html=True)

        cols_display = ['ID', 'DS_CNAE', 'Perfil_da_Empresa', 'VL_FATU', 'VL_SLDO', 'Risco_Santander', 'Oportunidade_Credito']
        df_display = page_df[cols_display].copy() if not page_df.empty else pd.DataFrame(columns=cols_display)

        styler = df_display.style.map(style_oportunidade, subset=['Oportunidade_Credito'])
        styler = styler.format({"VL_FATU": "R$ {:,.0f}", "VL_SLDO": "R$ {:,.0f}"})
        st.dataframe(styler, use_container_width=True, hide_index=True)

    with st.expander("Clique para ver a legenda"):
        st.markdown("""
        ### Oportunidade de Crédito

        - 🟡 **Ouro:** Empresas com saúde financeira 'Saudável' e risco 'Muito Baixo'. Perfil ideal para crédito de expansão e produtos de investimento.
        - ⚪ **Prata:** Empresas 'Saudável' com risco 'Baixo', ou em 'Alavancagem Estratégica' com risco baixo/muito baixo. Potencial para capital de giro e financiamentos.
        - 🟤 **Bronze:** Empresas em 'Ponto de Atenção' com risco baixo ou médio. Indicam necessidade pontual de capital, ideal para produtos de curto prazo.
        - ⚫ **Não Elegível:** Empresas 'Endividadas' ou com risco 'Alto'/'Muito Alto'. Requerem análise cautelosa e monitoramento constante.

        ### Perfil da Empresa
        - **Saudável:** Empresas com saldo positivo.
        - **Alavancagem Estratégica:** Dívida < 5% do faturamento.
        - **Ponto de Atenção:** Dívida entre 5% e 10% do faturamento.
        - **Endividada:** Dívida > 10% do faturamento ou faturamento <= 0.
        """)

    # ====== Análises Macro ======
    st.markdown("---")
    st.subheader("Análises Macro da Carteira")
    with st.container(border=True):
        tab1, tab2, tab3 = st.tabs(["📊 Saúde Financeira e Risco", "🔗 Análise B2B", "💡 Oportunidades por Setor"])

        with tab1:
            st.markdown("Análise da distribuição das empresas por saúde financeira e pelo nível de risco calculado.")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("###### Distribuição de Clientes por Perfil da Empresa")
                saude_counts = filtered_df['Saude_Financeira'].value_counts().reindex(['Saudável', 'Alavancagem Estratégica', 'Ponto de Atenção', 'Endividada'])
                if not saude_counts.dropna().empty:
                    color_map = {'Saudável': COLOR_SUCCESS, 'Alavancagem Estratégica': COLOR_INFO, 'Ponto de Atenção': COLOR_WARNING, 'Endividada': SANTANDER_RED}
                    fig = go.Figure(go.Bar(x=saude_counts.index, y=saude_counts.values, marker_color=[color_map.get(i) for i in saude_counts.index]))
                    fig.update_layout(template="plotly_white", xaxis_title="", yaxis_title="Nº de Empresas", showlegend=False, margin=dict(t=10, l=10, r=10, b=10), font_color=PRIMARY_TEXT_COLOR)
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(
                        """
                        **Saudável:** Empresas com saldo positivo.<br>
                        **Alavancagem Estratégica:** Dívida < 5% do faturamento.<br>
                        **Ponto de Atenção:** Dívida entre 5% e 10% do faturamento.<br>
                        **Endividada:** Dívida > 10% do faturamento ou faturamento <= 0.
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.info("Não há dados para exibir com os filtros atuais.")

            with col2:
                st.markdown("###### Distribuição por Nível de Risco")
                risco_counts = filtered_df['Risco_Santander'].value_counts().reindex(['Muito Baixo', 'Baixo', 'Médio', 'Alto', 'Muito Alto'])
                if not risco_counts.dropna().empty:
                    color_scale = [COLOR_SUCCESS, '#5DBB63', COLOR_WARNING, '#FF8C00', SANTANDER_RED]
                    fig = go.Figure(go.Bar(x=risco_counts.index, y=risco_counts.values, marker_color=color_scale))
                    fig.update_layout(template="plotly_white", xaxis_title="", yaxis_title="Nº de Empresas", showlegend=False, margin=dict(t=10, l=10, r=10, b=10), font_color=PRIMARY_TEXT_COLOR)
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("O nível de risco é calculado com base na saúde financeira, maturidade e dependência B2B da empresa")
                else:
                    st.info("Não há dados para exibir com os filtros atuais.")

            st.markdown("---")
            st.markdown("###### Relação Faturamento vs. Saldo")
            if not filtered_df.empty:
                fig_sc = px.scatter(filtered_df, x='VL_FATU', y='VL_SLDO', color='Risco_Santander', labels={'VL_FATU': 'Faturamento', 'VL_SLDO': 'Saldo'})
                fig_sc.update_layout(template="plotly_white", margin=dict(t=10, l=10, r=10, b=10))
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("Não há dados para exibir o gráfico de dispersão.")

        with tab2:
            st.markdown("Análise da intensidade e do tipo de relacionamento (pagamentos vs. recebimentos) entre as empresas.")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('###### Risco vs. Dependência B2B')
                if not filtered_df.empty:
                    pivot = filtered_df.pivot_table(index='Dependencia_B2B', columns='Risco_Santander', values='ID', aggfunc='count', fill_value=0)
                    ordem_categorias = ['Concentradora de Recebimentos', 'Alta Concentração em Clientes', 'Relacionamento Equilibrado', 'Alta Concentração em Fornecedores', 'Hub de Pagamentos', 'Não Classificado']
                    pivot = pivot.reindex([cat for cat in ordem_categorias if cat in pivot.index])

                    if not pivot.empty and len(pivot.columns) > 0:
                        risco_color_map = {
                            'Muito Baixo': COLOR_SUCCESS, 'Baixo': '#5DBB63',
                            'Médio': COLOR_WARNING, 'Alto': '#FF8C00', 'Muito Alto': SANTANDER_RED
                        }
                        fig = go.Figure()
                        ordem_risco = ['Muito Alto', 'Alto', 'Médio', 'Baixo', 'Muito Baixo']
                        for risco_cat in [r for r in ordem_risco if r in pivot.columns]:
                            fig.add_trace(go.Bar(x=pivot.index, y=pivot[risco_cat], name=risco_cat, marker_color=risco_color_map.get(risco_cat)))
                        fig.update_layout(
                            barmode='stack', template="plotly_white", xaxis_title="", yaxis_title="Nº de Empresas",
                            showlegend=True, margin=dict(t=20, l=10, r=10, b=10), font_color=PRIMARY_TEXT_COLOR,
                            legend=dict(title_text='Nível de Risco', orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        st.caption(
                            "**Dependência B2B** categoriza as empresas pelo fluxo de transações:\n"
                            "- **Hub de Pagamentos** (paga muito, recebe pouco)\n"
                            "- **Concentradora de Recebimentos** (recebe muito, paga pouco)\n"
                            "- **Alta Concentração em Clientes/Fornecedores** (forte desequilíbrio para um lado)\n"
                            "- **Relacionamento Equilibrado**"
                        )
                    else:
                        st.info("Não há dados para exibir com os filtros atuais.")
                else:
                    st.info("Não há dados para exibir com os filtros atuais.")

            with col2:
                st.markdown('###### Intensidade do Relacionamento B2B')
                if not filtered_df.empty:
                    intensidade_counts = filtered_df['Intensidade_B2B'].value_counts().reindex(['Muito Baixa', 'Baixa', 'Média', 'Alta', 'Muito Alta'])
                    intensidade_color_map = {'Muito Baixa': '#D3D3D3', 'Baixa': '#A9A9A9', 'Média': COLOR_INFO, 'Alta': COLOR_WARNING, 'Muito Alta': SANTANDER_RED}
                    if not intensidade_counts.dropna().empty:
                        fig = go.Figure(go.Bar(x=intensidade_counts.index, y=intensidade_counts.values, marker_color=[intensidade_color_map.get(i) for i in intensidade_counts.index]))
                        fig.update_layout(template="plotly_white", xaxis_title="", yaxis_title="Nº de Empresas", margin=dict(t=10, l=10, r=10, b=10), font_color=PRIMARY_TEXT_COLOR)
                        st.plotly_chart(fig, use_container_width=True)
                        st.caption("Este gráfico mostra a distribuição das empresas pela intensidade de suas transações B2B, desde **Muito Baixa** (poucas transações) até **Muito Alta** (grande volume de transações).")
                    else:
                        st.info("Não há dados para exibir com os filtros atuais.")
                else:
                    st.info("Não há dados para exibir com os filtros atuais.")

        with tab3:
            st.markdown("Mapa de calor que mostra a concentração de oportunidades de crédito por setor de atuação e tier (Ouro, Prata, Bronze). O tamanho do retângulo é proporcional ao faturamento.")
            oportunidades_df_tab = filtered_df[filtered_df['Oportunidade_Credito'] != 'Não Elegível']
            if not oportunidades_df_tab.empty:
                fig_treemap = px.treemap(
                    oportunidades_df_tab, path=[px.Constant("Todas"), 'DS_CNAE', 'Oportunidade_Credito'],
                    values='VL_FATU', color='Oportunidade_Credito',
                    color_discrete_map={k: v['bg'] for k, v in COLOR_OPORTUNIDADE.items()}
                )
                fig_treemap.update_layout(margin=dict(t=30, l=10, r=10, b=10), template="plotly_white", font_color=PRIMARY_TEXT_COLOR)
                st.plotly_chart(fig_treemap, use_container_width=True)
                st.caption(
                    "Oportunidades de crédito são classificadas em tiers: "
                    "**Ouro** (empresas saudáveis e de risco muito baixo), "
                    "**Prata** (empresas estratégicas ou saudáveis de baixo risco), "
                    "e **Bronze** (empresas em ponto de atenção com risco baixo a médio)."
                )
            else:
                st.info("Nenhuma oportunidade de crédito encontrada com os filtros atuais.")

# =========================
# 6) PÁGINA 2 — INSIGHTS (Regras + IA) — ATUALIZADA
# =========================
elif pagina == "Insights de CNPJs":
    st.title('Insights de CNPJs')
    tab_regras, tab_ia = st.tabs(["🧭 Assistido (Regras)", "🧠 IA (Gemini)"])

    # --------- Aba Regras (multi-CNPJ) ----------
    with tab_regras:
        st.markdown("Selecione um ou mais CNPJs para gerar insights automáticos (Regras).")
        with st.container(border=True):
            todos_cnpjs = sorted(df_processed['ID'].unique().tolist())
            cnpjs_selecionados = st.multiselect(
                "Selecione os CNPJs para análise (pode selecionar múltiplos):",
                options=todos_cnpjs,
                help="Selecione um ou mais CNPJs para filtrar ou clique para ver a lista completa"
            )

            gerar_insights = st.button("🚀 Gerar Insights", type="primary")

            if gerar_insights and cnpjs_selecionados:
                empresas_analisadas = df_processed[df_processed['ID'].isin(cnpjs_selecionados)]

                if empresas_analisadas.empty:
                    st.warning("⚠️ Nenhum CNPJ válido encontrado na base de dados.")
                else:
                    st.success(f"✅ {len(empresas_analisadas)} empresa(s) encontrada(s)")

                    # --- 1 EMPRESA: mantém a visualização existente ---
                    if len(empresas_analisadas) == 1:
                        emp = empresas_analisadas.iloc[0]
                        st.markdown(f"### {emp['ID']}")
                        st.caption(f"**Setor:** {emp['DS_CNAE']}")
                        st.markdown("<br>", unsafe_allow_html=True)

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Faturamento", f"R$ {emp['VL_FATU']:,.0f}")
                        m2.metric("Saldo", f"R$ {emp['VL_SLDO']:,.0f}")
                        m3.metric("Risco", emp['Risco_Santander'])
                        oport_color = COLOR_OPORTUNIDADE.get(emp['Oportunidade_Credito'], {'bg': '#E0E0E0', 'text': '#000000'})
                        with m4:
                            st.markdown(
                                f"<div style='text-align: center;'><small>Oportunidade</small><br>"
                                f"<span style='background-color: {oport_color['bg']}; color: {oport_color['text']}; "
                                f"padding: 5px 15px; border-radius: 8px; font-weight: 600; display: inline-block; margin-top: 5px;'>{emp['Oportunidade_Credito']}</span></div>",
                                unsafe_allow_html=True
                            )

                        st.markdown("<br>", unsafe_allow_html=True)
                        t1, t2, t3 = st.tabs(["🎯 Recomendações", "💡 Análise de Risco", "📊 Dados Gerais"])

                        with t1:
                            recs = []
                            if emp['Oportunidade_Credito'] in ['Ouro', 'Prata']:
                                recs += [("💼", "Crédito para Expansão", "Investimentos em infraestrutura"),
                                         ("💰", "Capital de Giro Rotativo", "Flexibilidade operacional")]
                                if emp['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                    recs.append(("📈", "Antecipação de Recebíveis", "Melhore o fluxo de caixa"))
                            if emp['Oportunidade_Credito'] == 'Bronze':
                                recs += [("💳", "Capital de Giro Curto Prazo", "Necessidades pontuais"),
                                         ("📄", "Desconto de Duplicatas", "Liquidez imediata")]
                            if emp['VL_SLDO'] > emp['VL_FATU'] * 0.1:
                                recs += [("💎", "Investimentos", "Otimize reserva financeira"),
                                         ("🏦", "CDB Corporativo", "Rentabilidade com liquidez")]
                            if emp['Dependencia_B2B'] == 'Hub de Pagamentos' or emp['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                recs.append(("💸", "Pagamentos em Lote", "Automatize processos"))

                            if recs:
                                c1, c2 = st.columns(2)
                                for i, (ic, t, d) in enumerate(recs):
                                    with (c1 if i % 2 == 0 else c2):
                                        with st.container(border=True):
                                            st.markdown(f"### {ic} {t}")
                                            st.markdown(d)
                            else:
                                st.info("Sem recomendações específicas — consultar especialista.")

                        with t2:
                            insights = []
                            if emp['Saude_Financeira'] == 'Saudável':
                                insights.append(("✅", "Situação Positiva", "Saldo positivo, boa gestão de caixa."))
                            elif emp['Saude_Financeira'] == 'Alavancagem Estratégica':
                                insights.append(("📊", "Alavancagem Controlada", "Dívida <5% do faturamento."))
                            elif emp['Saude_Financeira'] == 'Ponto de Atenção':
                                insights.append(("⚠️", "Atenção Necessária", "Dívida entre 5-10% do faturamento."))
                            else:
                                insights.append(("🔴", "Risco Elevado", "Dívida >10% do faturamento ou faturamento crítico."))

                            if emp['Maturidade'] == 'Madura':
                                insights.append(("🏢", "Empresa Consolidada", f"{emp['Tempo_Atividade_Anos']} anos de operação."))
                            else:
                                insights.append(("🌱", "Empresa em Crescimento", f"{emp['Tempo_Atividade_Anos']} anos, fase de expansão."))

                            dep = emp['Dependencia_B2B']
                            dep_map = {
                                'Hub de Pagamentos': "Muitos pagamentos, poucos recebimentos (dependência de fornecedores).",
                                'Concentradora de Recebimentos': "Muitos recebimentos, poucos pagamentos (base ampla de clientes).",
                                'Alta Concentração em Clientes': "Risco de poucos clientes concentrarem receita.",
                                'Alta Concentração em Fornecedores': "Risco de poucos fornecedores concentrarem custos.",
                                'Relacionamento Equilibrado': "Fluxos balanceados."
                            }
                            insights.append(("🔗", "Dependência B2B", dep_map.get(dep, "Não classificado.")))

                            if emp['Oportunidade_Credito'] == 'Ouro':
                                insights.append(("🥇", "Excelente Oportunidade", "Crédito premium, expansão e investimentos."))
                            elif emp['Oportunidade_Credito'] == 'Prata':
                                insights.append(("🥈", "Boa Oportunidade", "Capital de giro e financiamentos estruturados."))
                            elif emp['Oportunidade_Credito'] == 'Bronze':
                                insights.append(("🥉", "Oportunidade Pontual", "Capital de curto prazo / produtos específicos."))
                            else:
                                insights.append(("⛔", "Não Elegível", "Requer reestruturação ou análise profunda."))

                            if emp['VL_SLDO'] < 0 and emp['VL_FATU'] > 0:
                                prop = abs(emp['VL_SLDO']) / emp['VL_FATU'] * 100
                                insights.append(("💳", "Análise de Caixa", f"Saldo negativo = {prop:.1f}% do faturamento."))
                            elif emp['VL_SLDO'] > 0:
                                prop = emp['VL_SLDO'] / emp['VL_FATU'] * 100 if emp['VL_FATU'] > 0 else 0
                                insights.append(("💰", "Reserva Saudável", f"Saldo positivo = {prop:.1f}% do faturamento."))

                            for ic, t, d in insights:
                                with st.container(border=True):
                                    st.markdown(f"### {ic} {t}")
                                    st.markdown(d)

                        with t3:
                            cA, cB = st.columns(2)
                            with cA:
                                with st.container(border=True):
                                    st.markdown("**Perfil da Empresa**")
                                    st.markdown(f"• Maturidade: **{emp['Maturidade']}**")
                                    st.markdown(f"• Anos de operação: **{emp['Tempo_Atividade_Anos']}**")
                                    st.markdown(f"• Saúde Financeira: **{emp['Saude_Financeira']}**")
                            with cB:
                                with st.container(border=True):
                                    st.markdown("**Relacionamento B2B**")
                                    st.markdown(f"• Intensidade: **{emp['Intensidade_B2B']}**")
                                    st.markdown(f"• Dependência: **{emp['Dependencia_B2B']}**")
                                    st.markdown(f"• Total de Transações: **{int(emp['Total_Transacoes'])}**")

                    # --- MÚLTIPLAS EMPRESAS: tabs por CNPJ + bloco comparativo + LLM (simulado) ---
                    else:
                        tabs = st.tabs([f"{e['ID']}" for _, e in empresas_analisadas.iterrows()])
                        for i, (_, empresa) in enumerate(empresas_analisadas.iterrows()):
                            with tabs[i]:
                                st.caption(f"**Setor:** {empresa['DS_CNAE']}")
                                st.markdown("<br>", unsafe_allow_html=True)

                                c1, c2, c3, c4 = st.columns(4)
                                c1.metric("Faturamento", f"R$ {empresa['VL_FATU']:,.0f}")
                                c2.metric("Saldo", f"R$ {empresa['VL_SLDO']:,.0f}")
                                c3.metric("Risco", empresa['Risco_Santander'])
                                oport_color = COLOR_OPORTUNIDADE.get(empresa['Oportunidade_Credito'], {'bg': '#E0E0E0', 'text': '#000000'})
                                with c4:
                                    st.markdown(
                                        f"<div style='text-align: center;'><small>Oportunidade</small><br>"
                                        f"<span style='background-color: {oport_color['bg']}; color: {oport_color['text']}; "
                                        f"padding: 5px 15px; border-radius: 8px; font-weight: 600; display: inline-block; margin-top: 5px;'>{empresa['Oportunidade_Credito']}</span></div>",
                                        unsafe_allow_html=True
                                    )

                                st.markdown("<br>", unsafe_allow_html=True)
                                sub1, sub2, sub3 = st.tabs(["🎯 Recomendações", "💡 Análise de Risco", "📊 Dados Gerais"])

                                with sub1:
                                    recs = []
                                    if empresa['Oportunidade_Credito'] in ['Ouro', 'Prata']:
                                        recs += [("💼", "Crédito para Expansão", "Investimentos em infraestrutura"),
                                                 ("💰", "Capital de Giro Rotativo", "Flexibilidade operacional")]
                                        if empresa['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                            recs.append(("📈", "Antecipação de Recebíveis", "Melhore o fluxo de caixa"))
                                    if empresa['Oportunidade_Credito'] == 'Bronze':
                                        recs += [("💳", "Capital de Giro Curto Prazo", "Necessidades pontuais"),
                                                 ("📄", "Desconto de Duplicatas", "Liquidez imediata")]
                                    if empresa['VL_SLDO'] > empresa['VL_FATU'] * 0.1:
                                        recs += [("💎", "Investimentos", "Otimize reserva financeira"),
                                                 ("🏦", "CDB Corporativo", "Rentabilidade com liquidez")]
                                    if empresa['Dependencia_B2B'] == 'Hub de Pagamentos' or empresa['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                        recs.append(("💸", "Pagamentos em Lote", "Automatize processos"))

                                    if recs:
                                        col_rec1, col_rec2 = st.columns(2)
                                        for idx_rec, (icon, titulo, descricao) in enumerate(recs):
                                            with (col_rec1 if idx_rec % 2 == 0 else col_rec2):
                                                with st.container(border=True):
                                                    st.markdown(f"### {icon} {titulo}")
                                                    st.markdown(descricao)
                                    else:
                                        st.info("Consulte um especialista para produtos adequados ao perfil desta empresa.")

                                with sub2:
                                    insights = []
                                    if empresa['Saude_Financeira'] == 'Saudável':
                                        insights.append(("✅", "Situação Positiva", "Saldo positivo, boa gestão de caixa."))
                                    elif empresa['Saude_Financeira'] == 'Alavancagem Estratégica':
                                        insights.append(("📊", "Alavancagem Controlada", "Dívida <5% do faturamento."))
                                    elif empresa['Saude_Financeira'] == 'Ponto de Atenção':
                                        insights.append(("⚠️", "Atenção Necessária", "Dívida entre 5-10% do faturamento."))
                                    else:
                                        insights.append(("🔴", "Risco Elevado", "Dívida >10% do faturamento ou faturamento crítico."))

                                    if empresa['Maturidade'] == 'Madura':
                                        insights.append(("🏢", "Empresa Consolidada", f"{empresa['Tempo_Atividade_Anos']} anos de operação."))
                                    else:
                                        insights.append(("🌱", "Empresa em Crescimento", f"{empresa['Tempo_Atividade_Anos']} anos, fase de expansão."))

                                    dep = empresa['Dependencia_B2B']
                                    dep_map = {
                                        'Hub de Pagamentos': "Muitos pagamentos, poucos recebimentos (dependência de fornecedores).",
                                        'Concentradora de Recebimentos': "Muitos recebimentos, poucos pagamentos (base ampla de clientes).",
                                        'Alta Concentração em Clientes': "Risco de poucos clientes concentrarem receita.",
                                        'Alta Concentração em Fornecedores': "Risco de poucos fornecedores concentrarem custos.",
                                        'Relacionamento Equilibrado': "Fluxos balanceados."
                                    }
                                    insights.append(("🔗", "Dependência B2B", dep_map.get(dep, "Não classificado.")))

                                    if empresa['Oportunidade_Credito'] == 'Ouro':
                                        insights.append(("🥇", "Excelente Oportunidade", "Crédito premium, expansão e investimentos."))
                                    elif empresa['Oportunidade_Credito'] == 'Prata':
                                        insights.append(("🥈", "Boa Oportunidade", "Capital de giro e financiamentos estruturados."))
                                    elif empresa['Oportunidade_Credito'] == 'Bronze':
                                        insights.append(("🥉", "Oportunidade Pontual", "Capital de curto prazo / produtos específicos."))
                                    else:
                                        insights.append(("⛔", "Não Elegível", "Requer reestruturação ou análise profunda."))

                                    if empresa['VL_SLDO'] < 0 and empresa['VL_FATU'] > 0:
                                        proporcao = abs(empresa['VL_SLDO']) / empresa['VL_FATU'] * 100
                                        insights.append(("💳", "Análise de Caixa", f"Saldo negativo representa {proporcao:.1f}% do faturamento anual."))
                                    elif empresa['VL_SLDO'] > 0:
                                        proporcao = empresa['VL_SLDO'] / empresa['VL_FATU'] * 100 if empresa['VL_FATU'] > 0 else 0
                                        insights.append(("💰", "Reserva Saudável", f"Saldo positivo equivale a {proporcao:.1f}% do faturamento anual."))

                                    for icon, titulo, descricao in insights:
                                        with st.container(border=True):
                                            st.markdown(f"### {icon} {titulo}")
                                            st.markdown(descricao)

                                with sub3:
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        with st.container(border=True):
                                            st.markdown("**Perfil da Empresa**")
                                            st.markdown(f"• Maturidade: **{empresa['Maturidade']}**")
                                            st.markdown(f"• Anos de operação: **{empresa['Tempo_Atividade_Anos']}**")
                                            st.markdown(f"• Saúde Financeira: **{empresa['Saude_Financeira']}**")
                                    with col_b:
                                        with st.container(border=True):
                                            st.markdown("**Relacionamento B2B**")
                                            st.markdown(f"• Intensidade: **{empresa['Intensidade_B2B']}**")
                                            st.markdown(f"• Dependência: **{empresa['Dependencia_B2B']}**")
                                            st.markdown(f"• Total de Transações: **{int(empresa['Total_Transacoes'])}**")

                        # --- BLOCO COMPARATIVO (2+ CNPJs) ---
                        st.markdown("---")
                        st.subheader("📊 Análise Comparativa")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("##### Faturamento Comparado")
                            fig = go.Figure(go.Bar(
                                x=empresas_analisadas['ID'],
                                y=empresas_analisadas['VL_FATU'],
                                marker_color=SANTANDER_RED
                            ))
                            fig.update_layout(
                                template="plotly_white",
                                xaxis_title="",
                                yaxis_title="Faturamento (R$)",
                                margin=dict(t=10, l=10, r=10, b=10)
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            st.markdown("##### Distribuição de Risco")
                            risco_dist = empresas_analisadas['Risco_Santander'].value_counts()
                            if not risco_dist.empty:
                                fig = go.Figure(go.Pie(labels=risco_dist.index, values=risco_dist.values, hole=0.3))
                                fig.update_layout(template="plotly_white", margin=dict(t=10, l=10, r=10, b=10))
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("Sem dados suficientes para a pizza de risco.")

                        # Insights comparativos objetivos (Regras)
                        st.markdown("##### Insights Comparativos (Regras)")
                        mapa_rank = {'Ouro': 1, 'Prata': 2, 'Bronze': 3}
                        candidatos = empresas_analisadas[empresas_analisadas['Oportunidade_Credito'].isin(mapa_rank.keys())].copy()
                        if not candidatos.empty:
                            candidatos['rank'] = candidatos['Oportunidade_Credito'].map(mapa_rank)
                            melhor = candidatos.sort_values(['rank', 'VL_FATU'], ascending=[True, False]).iloc[0]
                            st.success(f"**Melhor Oportunidade:** {melhor['ID']} (Tier {melhor['Oportunidade_Credito']})")

                        if not empresas_analisadas.empty:
                            maior_fat_idx = empresas_analisadas['VL_FATU'].idxmax()
                            if pd.notnull(maior_fat_idx):
                                maior = empresas_analisadas.loc[maior_fat_idx]
                                st.info(f"**Maior Faturamento:** {maior['ID']} (R$ {maior['VL_FATU']:,.0f})")

                        maior_risco = empresas_analisadas[empresas_analisadas['Risco_Santander'].isin(['Alto', 'Muito Alto'])]
                        if not maior_risco.empty:
                            st.warning(f"**Atenção:** {len(maior_risco)} empresa(s) com risco **Alto/Muito Alto**")

                        # === NOVO: Parecer LLM + Regras ===
                        st.markdown("---")
                        st.subheader("🧠 Comparação por IA (LLM + Regras)")
                        prompt_comp = gerar_prompt_comparativo_ia(empresas_analisadas)
                        with st.expander("Ver prompt comparativo enviado para a IA"):
                            st.text(prompt_comp)
                        parecer_llm = chamar_gemini_api_comparativo(prompt_comp, empresas_analisadas)
                        st.markdown(parecer_llm, unsafe_allow_html=True)

            elif gerar_insights and not cnpjs_selecionados:
                st.info("Selecione um ou mais CNPJs para começar a análise.")

    # --------- Aba IA (LLM apenas) ----------
    with tab_ia:
        st.markdown("Selecione um CNPJ para gerar uma **análise diagnóstica e recomendações estratégicas** com IA (Gemini).")
        with st.container(border=True):
            todos_cnpjs = sorted(df_processed['ID'].unique().tolist())
            cnpj = st.selectbox("Selecione o CNPJ:", options=todos_cnpjs, help="Digite ou selecione o CNPJ.")
            if st.button("🚀 Gerar Análise com IA"):
                empresa = df_processed[df_processed['ID'] == cnpj].iloc[0]
                st.markdown(f"### Análise do CNPJ: {empresa['ID']}")
                st.caption(f"**Setor:** {empresa['DS_CNAE']}")

                k1, k2, k3 = st.columns(3)
                k1.metric("Risco (Regras)", empresa.get('Risco_Santander', 'N/D'))
                k2.metric("Saúde (Regras)", empresa.get('Saude_Financeira', 'N/D'))
                k3.metric("Oportunidade (Regras)", empresa.get('Oportunidade_Credito', 'N/D'))
                st.markdown("---")

                with st.spinner('IA analisando...'):
                    prompt = gerar_prompt_analise_ia(empresa)
                    with st.expander("Ver prompt enviado para a IA"):
                        st.text(prompt)
                    resposta = chamar_gemini_api(prompt)

                st.markdown(resposta, unsafe_allow_html=True)

                # Apoio visual (comparativo e histórico — sem ML)
                st.markdown("---")
                st.subheader("Dados de Apoio à Análise")
                tabB1, tabB2 = st.tabs(["📊 Benchmarking Setorial", "📈 Histórico Financeiro"])

                with tabB1:
                    setor = empresa['DS_CNAE']
                    df_setor = df_processed[df_processed['DS_CNAE'] == setor]
                    avg_fatu = df_setor['VL_FATU'].mean()
                    avg_saldo = df_setor['VL_SLDO'].mean()

                    cA, cB = st.columns(2)
                    with cA:
                        fig = go.Figure()
                        fig.add_trace(go.Bar(name='Empresa', x=['Faturamento'], y=[empresa['VL_FATU']], marker_color=SANTANDER_RED))
                        fig.add_trace(go.Bar(name='Média do Setor', x=['Faturamento'], y=[avg_fatu], marker_color='lightgrey'))
                        fig.update_layout(title='Faturamento vs. Média do Setor', yaxis_title='R$', template="plotly_white")
                        st.plotly_chart(fig, use_container_width=True)
                    with cB:
                        fig = go.Figure()
                        fig.add_trace(go.Bar(name='Empresa', x=['Saldo'], y=[empresa['VL_SLDO']], marker_color=SANTANDER_RED))
                        fig.add_trace(go.Bar(name='Média do Setor', x=['Saldo'], y=[avg_saldo], marker_color='lightgrey'))
                        fig.update_layout(title='Saldo vs. Média do Setor', yaxis_title='R$', template="plotly_white")
                        st.plotly_chart(fig, use_container_width=True)

                with tabB2:
                    historico_empresa = base1[base1['ID'] == cnpj].sort_values('DT_REFE')
                    if not historico_empresa.empty:
                        fig = px.line(historico_empresa, x='DT_REFE', y=['VL_FATU', 'VL_SLDO'], title='Histórico de Faturamento e Saldo', labels={'DT_REFE': 'Data de Referência'})
                        fig.update_layout(template="plotly_white", margin=dict(t=10, l=10, r=10, b=10))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Sem histórico disponível.")

# =========================
# 7) PÁGINA 3 — CADEIA de VALOR (SEM ML)
# =========================
elif pagina == "Cadeia de Valor":
    st.title('Análise da Cadeia de Valor')
    st.markdown("Selecione uma empresa para visualizar o risco de seus principais clientes e fornecedores em um mapa de rede.")

    options = sorted(df_processed['ID'].unique().tolist())
    empresa_id = st.selectbox('Selecione a Empresa:', options=options, help="Digite o ID da empresa para buscar.")

    if empresa_id:
        clientes = base2[base2['ID_RCBE'] == empresa_id]
        top_clientes_id = clientes.groupby('ID_PGTO')['VL'].sum().nlargest(5).index if 'VL' in clientes.columns and not clientes.empty else []
        clientes_df = df_processed[df_processed['ID'].isin(top_clientes_id)]

        fornecedores = base2[base2['ID_PGTO'] == empresa_id]
        top_fornecedores_id = fornecedores.groupby('ID_RCBE')['VL'].sum().nlargest(5).index if 'VL' in fornecedores.columns and not fornecedores.empty else []
        fornecedores_df = df_processed[df_processed['ID'].isin(top_fornecedores_id)]

        empresa_central_info = df_processed[df_processed['ID'] == empresa_id].iloc[0]

        col_kpi, col_graph = st.columns([1, 2])
        with col_kpi:
            st.markdown("###### Resumo do Risco da Cadeia")
            with st.container(border=True):
                alto_risco_clientes = clientes_df[clientes_df['Risco_Santander'].isin(['Alto', 'Muito Alto'])].shape[0]
                st.metric("Clientes de Alto Risco", f"{alto_risco_clientes} de {len(clientes_df)}", help="Número de clientes, entre os 5 principais, com risco 'Alto' ou 'Muito Alto'.")

            with st.container(border=True):
                alto_risco_fornecedores = fornecedores_df[fornecedores_df['Risco_Santander'].isin(['Alto', 'Muito Alto'])].shape[0]
                st.metric("Fornecedores de Alto Risco", f"{alto_risco_fornecedores} de {len(fornecedores_df)}", help="Número de fornecedores, entre os 5 principais, com risco 'Alto' ou 'Muito Alto'.")

            st.markdown("###### Análise de Dependência")
            with st.container(border=True):
                dep_crit = 0
                for _, row in clientes_df.iterrows():
                    dep = row.get('Dependencia_B2B', 'Nao Classificado')
                    if dep in ['Alta Concentração em Fornecedores', 'Concentradora de Recebimentos']:
                        dep_crit += 1
                for _, row in fornecedores_df.iterrows():
                    dep = row.get('Dependencia_B2B', 'Nao Classificado')
                    if dep in ['Alta Concentração em Clientes', 'Hub de Pagamentos']:
                        dep_crit += 1
                if dep_crit:
                    st.warning(f"⚠️ {dep_crit} empresa(s) com dependência crítica.")
                else:
                    st.success("✅ Nenhuma dependência crítica detectada.")

        with col_graph:
            st.markdown("###### Mapa da Cadeia de Valor")
            risco_color_map = {
                'Muito Baixo': '#2E8B57', 'Baixo': '#90EE90',
                'Médio': '#FFD700', 'Alto': '#FFA07A', 'Muito Alto': '#DC143C'
            }
            dependencia_symbol_map = {
                'Concentradora de Recebimentos': '💰',
                'Alta Concentração em Clientes': '📊',
                'Alta Concentração em Fornecedores': '🏭',
                'Hub de Pagamentos': '💸',
                'Relacionamento Equilibrado': '⚖️',
                'Não Classificado': ''
            }

            graph = graphviz.Digraph()
            graph.attr('node', shape='box', style='rounded,filled')

            risco_central = empresa_central_info['Risco_Santander']
            dep_central = empresa_central_info.get('Dependencia_B2B', 'Não Classificado')
            simbolo_central = dependencia_symbol_map.get(dep_central, '')

            label_central = f"{empresa_id}\n(Risco: {risco_central})"
            if dep_central != 'Não Classificado':
                label_central += f"\n{simbolo_central} {dep_central}"

            graph.node(str(empresa_id), label_central, fillcolor="#ADD8E6")

            for _, row in clientes_df.iterrows():
                risco = row['Risco_Santander']
                dep = row.get('Dependencia_B2B', 'Não Classificado')
                cor = risco_color_map.get(risco, '#D3D3D3')
                simbolo = dependencia_symbol_map.get(dep, '')

                label = f"Cliente: {row['ID']}\n(Risco: {risco})"
                if dep != 'Não Classificado':
                    label += f"\n{simbolo} {dep}"

                if dep in ['Alta Concentração em Fornecedores', 'Concentradora de Recebimentos']:
                    graph.node(str(row['ID']), label, fillcolor=cor, penwidth="3", color="red")
                else:
                    graph.node(str(row['ID']), label, fillcolor=cor)

                graph.edge(str(row['ID']), str(empresa_id))

            for _, row in fornecedores_df.iterrows():
                risco = row['Risco_Santander']
                dep = row.get('Dependencia_B2B', 'Não Classificado')
                cor = risco_color_map.get(risco, '#D3D3D3')
                simbolo = dependencia_symbol_map.get(dep, '')

                label = f"Forn.: {row['ID']}\n(Risco: {risco})"
                if dep != 'Não Classificado':
                    label += f"\n{simbolo} {dep}"

                if dep in ['Alta Concentração em Clientes', 'Hub de Pagamentos']:
                    graph.node(str(row['ID']), label, fillcolor=cor, penwidth="3", color="red")
                else:
                    graph.node(str(row['ID']), label, fillcolor=cor)

                graph.edge(str(empresa_id), str(row['ID']))

            st.graphviz_chart(graph)

            with st.expander("📖 Legenda do Mapa de Rede"):
                col_leg1, col_leg2 = st.columns(2)
                with col_leg1:
                    st.markdown("**🎨 Cores (Nível de Risco):**")
                    st.markdown("- 🟢 Verde Escuro: Risco Muito Baixo")
                    st.markdown("- 🟢 Verde Claro: Risco Baixo")
                    st.markdown("- 🟡 Amarelo: Risco Médio")
                    st.markdown("- 🟠 Laranja: Risco Alto")
                    st.markdown("- 🔴 Vermelho: Risco Muito Alto")
                    st.markdown("- 🔵 Azul: Empresa Central")
                with col_leg2:
                    st.markdown("**📊 Símbolos (Dependência B2B):**")
                    st.markdown("- 💰 Concentradora de Recebimentos")
                    st.markdown("- 📊 Alta Concentração em Clientes")
                    st.markdown("- 🏭 Alta Concentração em Fornecedores")
                    st.markdown("- 💸 Hub de Pagamentos")
                    st.markdown("- ⚖️ Relacionamento Equilibrado")
                    st.markdown("**⚠️ Borda vermelha:** Indica dependência crítica")

                st.info("As setas indicam o fluxo de pagamento: saindo da empresa pagadora para a recebedora.")
import streamlit as st
import pandas as pd
import datetime
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import graphviz
import math # Importado para a função de arredondamento da paginação

# --- 0. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Dashboard de Risco e Oportunidades",
    page_icon="🏦"
)

# --- PALETA DE CORES (usada em todo o dashboard) ---
SANTANDER_RED = "#EC0000"
PRIMARY_TEXT_COLOR = "#000000"
COLOR_SUCCESS = "#006A4E"
COLOR_WARNING = "#FFBF00"
COLOR_INFO = "#0077C8"
COLOR_OPORTUNIDADE = {
    'Ouro': {'bg': '#FFD700', 'text': PRIMARY_TEXT_COLOR},
    'Prata': {'bg': '#E0E0E0', 'text': PRIMARY_TEXT_COLOR},
    'Bronze': {'bg': '#CD7F32', 'text': '#FFFFFF'}
}

pd.set_option("styler.render.max_elements", 1_000_000)

# --- 1. FUNÇÕES DE CLASSIFICAÇÃO (REUTILIZÁVEIS) ---
def classificar_saude_financeira(row):
    faturamento, saldo = row['VL_FATU'], row['VL_SLDO']
    if saldo >= 0: return 'Saudável'
    if faturamento <= 0: return 'Endividada'
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
    if score <= 0: return 'Baixo'
    if score <= 2: return 'Médio'
    if score <= 4: return 'Alto'
    return 'Muito Alto'

def classificar_oportunidade(row):
    saude, risco = row['Saude_Financeira'], row['Risco_Santander']
    if saude == 'Saudável' and risco == 'Muito Baixo': return 'Ouro'
    if (saude == 'Alavancagem Estratégica' and risco in ['Baixo', 'Muito Baixo']) or (saude == 'Saudável' and risco == 'Baixo'): return 'Prata'
    if saude == 'Ponto de Atenção' and risco in ['Baixo', 'Médio']: return 'Bronze'
    return 'Não Elegível'

# --- 2. FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO DE DADOS ---
@st.cache_data
def load_raw_data():
    base1_path, base2_path = Path("Base1.csv"), Path("Base2.csv")
    if not base1_path.exists() or not base2_path.exists():
        st.error("Arquivos de dados (Base1.csv, Base2.csv) não encontrados.")
        st.stop()
    base1 = pd.read_csv(base1_path, parse_dates=['DT_ABRT', 'DT_REFE'])
    base2 = pd.read_csv(base2_path)
    return base1, base2

@st.cache_data
def get_processed_data(_df1, _df2):
    df1 = _df1.copy()
    df2 = _df2.copy()
    df2_clean = df2.dropna(subset=['ID_PGTO', 'ID_RCBE'])
    rel_recebido = df2_clean.groupby('ID_RCBE')['ID_PGTO'].count().reset_index(name='Transacoes_Recebidas')
    rel_pago = df2_clean.groupby('ID_PGTO')['ID_RCBE'].count().reset_index(name='Transacoes_Pagas')
    relacionamento = pd.merge(rel_recebido, rel_pago, left_on='ID_RCBE', right_on='ID_PGTO', how='outer')
    relacionamento = relacionamento.rename(columns={'ID_RCBE': 'ID'}).drop(columns='ID_PGTO').fillna(0)
    relacionamento['Total_Transacoes'] = relacionamento['Transacoes_Recebidas'] + relacionamento['Transacoes_Pagas']
    
    def classificar_b2b_intensidade(total):
        if total > 50: return 'Muito Alta'
        if total > 30: return 'Alta'
        if total > 10: return 'Média'
        if total > 5: return 'Baixa'
        return 'Muito Baixa'
    relacionamento['Intensidade_B2B'] = relacionamento['Total_Transacoes'].apply(classificar_b2b_intensidade)
    
    def analisar_dependencia(row):
        pgto, rcbe = row['Transacoes_Pagas'], row['Transacoes_Recebidas']
        if rcbe == 0 and pgto > 0: return 'Hub de Pagamentos'
        if pgto == 0 and rcbe > 0: return 'Concentradora de Recebimentos'
        if rcbe > 3 * pgto: return 'Alta Concentração em Clientes'
        if pgto > 3 * rcbe: return 'Alta Concentração em Fornecedores'
        return 'Relacionamento Equilibrado'
    relacionamento['Dependencia_B2B'] = relacionamento.apply(analisar_dependencia, axis=1)
    
    df1_sorted = df1.sort_values(by=['ID', 'DT_REFE'], ascending=[True, False])
    df_agg = df1_sorted.groupby('ID').first().reset_index()
    df_final = pd.merge(df_agg, relacionamento, on='ID', how='left')
    df_final.fillna({'Total_Transacoes': 0, 'Intensidade_B2B': 'Não Classificado', 'Dependencia_B2B': 'Não Classificado'}, inplace=True)
    
    hoje = datetime.datetime.now()
    df_final['Tempo_Atividade_Anos'] = round((hoje - df_final['DT_ABRT']).dt.days / 365.25, 1)
    df_final['Maturidade'] = df_final['Tempo_Atividade_Anos'].apply(lambda x: 'Madura' if x > 5 else 'Inicial')
    df_final['Saude_Financeira'] = df_final.apply(classificar_saude_financeira, axis=1)
    df_final['Perfil_da_Empresa'] = df_final['Maturidade'] + ' - ' + df_final['Saude_Financeira']
    df_final['Risco_Santander'] = df_final.apply(classificar_risco, axis=1)
    df_final['Oportunidade_Credito'] = df_final.apply(classificar_oportunidade, axis=1)
    return df_final
    
# --- 3. LAYOUT DO DASHBOARD ---
base1, base2 = load_raw_data()
df_processed = get_processed_data(base1, base2)

# Sidebar com navegação estilizada
st.sidebar.image("santander_logo.png", width='stretch')

# NAVEGAÇÃO POR PÁGINAS - Moderna
st.sidebar.markdown("<br>", unsafe_allow_html=True)

# CSS customizado para navegação moderna
st.markdown("""
<style>
    /* Sidebar com mesma cor da página e linha divisória sutil */
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Esconder o label do radio */
    [data-testid="stSidebar"] .stRadio > label {
        display: none;
    }

    /* Container dos botões */
    [data-testid="stSidebar"] .stRadio > div {
        gap: 12px;
        padding: 0;
        display: flex;
        flex-direction: column;
    }

    /* Estilo dos cards de navegação */
    [data-testid="stSidebar"] .stRadio > div > label {
        background: linear-gradient(135deg, rgba(30, 30, 40, 0.9) 0%, rgba(20, 20, 30, 0.9) 100%);
        color: #e0e0e0;
        padding: 18px 20px;
        border-radius: 12px;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
        font-weight: 500;
        font-size: 14px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
        min-height: 56px;
        display: flex;
        align-items: center;
    }

    /* Efeito de hover nos cards */
    [data-testid="stSidebar"] .stRadio > div > label:hover {
        background: linear-gradient(135deg, rgba(40, 40, 50, 0.95) 0%, rgba(30, 30, 40, 0.95) 100%);
        transform: translateX(5px);
        box-shadow: 0 4px 12px rgba(236, 0, 0, 0.15);
    }

    /* Card selecionado com destaque vermelho Santander */
    [data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
        background: linear-gradient(135deg, #EC0000 0%, #c40000 100%);
        color: white;
        font-weight: 600;
        box-shadow: 0 4px 16px rgba(236, 0, 0, 0.4);
    }

    /* Esconder o radio button original */
    [data-testid="stSidebar"] .stRadio input[type="radio"] {
        display: none;
    }

    /* Texto da sidebar */
    [data-testid="stSidebar"] * {
        color: white !important;
    }

    /* Aumentar tamanho dos selectbox */
    .stSelectbox > div > div {
        font-size: 16px;
        width: 100%;
    }

    .stMultiSelect > div > div {
        font-size: 16px;
        width: 100%;
    }

    /* Aumentar altura do input do selectbox */
    .stSelectbox > div > div > div {
        min-height: 45px;
    }

    .stMultiSelect > div > div > div {
        min-height: 45px;
    }

    /* Garantir largura total do container */
    .stSelectbox, .stMultiSelect {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

pagina = st.sidebar.radio(
    "NAVEGACAO",
    ["Visão Geral da Carteira", "Insights de CNPJs", "Cadeia de Valor"],
    label_visibility="collapsed"
)

st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

# Inicializar variáveis de filtro
cnae_options = ['Todos'] + sorted(df_processed['DS_CNAE'].unique().tolist())
perfil_options = ['Todos'] + sorted(df_processed['Perfil_da_Empresa'].unique().tolist())
risco_options = ['Todos'] + ['Muito Baixo', 'Baixo', 'Médio', 'Alto', 'Muito Alto']
oportunidade_options = ['Todos'] + ['Ouro', 'Prata', 'Bronze', 'Não Elegível']

selected_cnae = 'Todos'
selected_perfil = 'Todos'
selected_risco = 'Todos'
selected_oportunidade = 'Todos'

# Filtros aplicados apenas na página de Visão Geral
filtered_df = df_processed.copy()

# === PAGINA 1: VISAO GERAL DA CARTEIRA ===
if pagina == "Visão Geral da Carteira":
    # Seção de Título e KPIs
    st.title('Dashboard de Risco e Oportunidades')
    st.subheader("Olá Eduardo, essa é sua carteira de clientes PJ")

    # Filtros no topo da página
    with st.expander("🔎 Filtros da Carteira", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            selected_cnae = st.selectbox('Setor (CNAE)', cnae_options)
        with col2:
            selected_perfil = st.selectbox('Perfil da Empresa', perfil_options)
        with col3:
            selected_risco = st.selectbox('Nível de Risco', risco_options)
        with col4:
            selected_oportunidade = st.selectbox('Oportunidade de Crédito', oportunidade_options)

    # Aplicação dos filtros
    if selected_cnae != 'Todos': filtered_df = filtered_df[filtered_df['DS_CNAE'] == selected_cnae]
    if selected_perfil != 'Todos': filtered_df = filtered_df[filtered_df['Perfil_da_Empresa'] == selected_perfil]
    if selected_risco != 'Todos': filtered_df = filtered_df[filtered_df['Risco_Santander'] == selected_risco]
    if selected_oportunidade != 'Todos': filtered_df = filtered_df[filtered_df['Oportunidade_Credito'] == selected_oportunidade]

    st.subheader("Visão Geral da Carteira de Clientes")
    st.caption("Os cartões abaixo resumem os dados das empresas selecionadas nos filtros laterais.")
    kpi1, kpi2 = st.columns(2)
    with kpi1:
        with st.container(border=True):
            st.metric("🏢 Clientes Total", f"{len(filtered_df):,}")
    with kpi2:
        with st.container(border=True):
            oportunidades_df = filtered_df[filtered_df['Oportunidade_Credito'] != 'Não Elegível']
            st.metric("💰 Clientes com Oportunidade de Crédito", f"{len(oportunidades_df):,}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- SEÇÃO DA TABELA DETALHADA (COM PESQUISA E PAGINAÇÃO) ---
    
    st.subheader('Indicador de Oportunidade de Crédito')    
    
    def style_oportunidade(val):
        style = COLOR_OPORTUNIDADE.get(val)
        if style:
            return f'background-color: {style["bg"]}; color: {style["text"]}; border-radius: 8px; padding: 3px 10px; text-align: center; font-weight: 500; font-size: 12px;'
        return ''
    
    with st.container(border=True):
        # --- CONTROLES DA TABELA DETALHADA ---
        search_query = st.text_input("Pesquisar por ID (CNPJ)", placeholder="Digite o CNPJ ou parte dele...")
    
        # Aplica o filtro de pesquisa
        if search_query:
            # Garante que a coluna ID seja do tipo string para usar o .str.contains
            filtered_df['ID'] = filtered_df['ID'].astype(str)
            search_results_df = filtered_df[filtered_df['ID'].str.contains(search_query, case=False)]
        else:
            search_results_df = filtered_df
    
        total_rows = len(search_results_df)
    
        # --- CONTROLES DE PAGINAÇÃO ---
        col1, col2, col_info = st.columns([1, 2, 3])
        with col1:
            items_per_page = st.selectbox("Itens por página", [10, 25, 50, 100], index=0)
        
        total_pages = math.ceil(total_rows / items_per_page) if total_rows > 0 else 1
        
        with col2:
            page_number = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
        
        # Lógica para fatiar o DataFrame
        start_idx = (page_number - 1) * items_per_page
        end_idx = start_idx + items_per_page
        paginated_df = search_results_df.iloc[start_idx:end_idx]
    
        # Informações de resultados
        with col_info:
            st.markdown(f"&nbsp; <br> **Mostrando {len(paginated_df)} de {total_rows} resultados.**", unsafe_allow_html=True)
    
        # --- EXIBIÇÃO DA TABELA PAGINADA E ESTILIZADA ---
        cols_display = ['ID', 'DS_CNAE', 'Perfil_da_Empresa', 'VL_FATU', 'VL_SLDO', 'Risco_Santander', 'Oportunidade_Credito']
        
        # Garante que o dataframe paginado tenha as colunas corretas caso esteja vazio
        if paginated_df.empty:
            df_display = pd.DataFrame(columns=cols_display)
        else:
            df_display = paginated_df[cols_display].copy()
    
        styler = df_display.style.map(style_oportunidade, subset=['Oportunidade_Credito'])
        styler = styler.format({"VL_FATU": "R$ {:,.0f}", "VL_SLDO": "R$ {:,.0f}"})
        
        # ALTERAÇÃO: use_container_width=True -> width='stretch'
        st.dataframe(
            styler,
            width='stretch',
            hide_index=True # Esconde o índice do pandas que não é mais necessário
        )
    
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
    
    # Seção de Análises Visuais do Portfólio
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
                    # ALTERAÇÃO: use_container_width=True -> width='stretch'
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
                    # ALTERAÇÃO: use_container_width=True -> width='stretch'
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(
                        "O nível de risco é calculado com base na saúde financeira, maturidade e dependência B2B da empresa"
                    )
                else:
                    st.info("Não há dados para exibir com os filtros atuais.")
            st.markdown("---") 
            st.markdown("###### Relação Faturamento vs. Saldo")
            if not filtered_df.empty:
                st.scatter_chart(filtered_df, x='VL_FATU', y='VL_SLDO', color='Risco_Santander')
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
                            fig.add_trace(go.Bar(
                                x=pivot.index, y=pivot[risco_cat], name=risco_cat,
                                marker_color=risco_color_map.get(risco_cat)
                            ))
                        fig.update_layout(
                            barmode='stack', template="plotly_white", xaxis_title="", yaxis_title="Nº de Empresas",
                            showlegend=True, margin=dict(t=20, l=10, r=10, b=10), font_color=PRIMARY_TEXT_COLOR,
                            legend=dict(
                                title_text='Nível de Risco', 
                                orientation="h", 
                                yanchor="bottom", y=1.02, 
                                xanchor="right", x=1
                            )
                        )
                        # ALTERAÇÃO: use_container_width=True -> width='stretch'
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
                    intensidade_color_map = {
                        'Muito Baixa': '#D3D3D3', 
                        'Baixa': '#A9A9A9',      
                        'Média': COLOR_INFO,     
                        'Alta': COLOR_WARNING,   
                        'Muito Alta': SANTANDER_RED
                    }
                    if not intensidade_counts.dropna().empty:
                        fig = go.Figure(go.Bar(
                            x=intensidade_counts.index, y=intensidade_counts.values,
                            marker_color=[intensidade_color_map.get(i) for i in intensidade_counts.index]
                        ))
                        fig.update_layout(
                            template="plotly_white", xaxis_title="", yaxis_title="Nº de Empresas",
                            margin=dict(t=10, l=10, r=10, b=10), font_color=PRIMARY_TEXT_COLOR
                        )
                        # ALTERAÇÃO: use_container_width=True -> width='stretch'
                        st.plotly_chart(fig, use_container_width=True)
                        st.caption(
                            "Este gráfico mostra a distribuição das empresas pela intensidade de suas transações B2B, "
                            "desde **Muito Baixa** (poucas transações) até **Muito Alta** (grande volume de transações)."
                        )
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
                # ALTERAÇÃO: use_container_width=True -> width='stretch'
                st.plotly_chart(fig_treemap, use_container_width=True)
                st.caption(
                    "Oportunidades de crédito são classificadas em tiers: "
                    "**Ouro** (empresas saudáveis e de risco muito baixo), "
                    "**Prata** (empresas estratégicas ou saudáveis de baixo risco), "
                    "e **Bronze** (empresas em ponto de atenção com risco baixo a médio)."
                )
            else:
                st.info("Nenhuma oportunidade de crédito encontrada com os filtros atuais.")

# === PAGINA 2: ANALISE INDIVIDUAL DE CNPJs ===
elif pagina == "Insights de CNPJs":
    st.title('Insights de CNPJs')
    st.markdown("Selecione um ou mais CNPJs para gerar insights automaticos detalhados sobre credito e risco.")

    with st.container(border=True):
        # Lista de todos CNPJs disponíveis ordenados
        todos_cnpjs = sorted(df_processed['ID'].unique().tolist())
    
        cnpjs_selecionados = st.multiselect(
            "Selecione os CNPJs para análise (pode selecionar múltiplos):",
            options=todos_cnpjs,
            help="Selecione um ou mais CNPJs para filtrar ou clique para ver a lista completa"
        )
    
        cnpjs_list = cnpjs_selecionados
    
        gerar_insights = st.button("🚀 Gerar Insights", type="primary")
    
        if gerar_insights and cnpjs_list:
    
            if cnpjs_list:
                # Filtrar empresas
                empresas_analisadas = df_processed[df_processed['ID'].isin(cnpjs_list)]
    
                if empresas_analisadas.empty:
                    st.warning("⚠️ Nenhum CNPJ válido encontrado na base de dados.")
                else:
                    st.success(f"✅ {len(empresas_analisadas)} empresa(s) encontrada(s)")
    
                    # --- TABS PARA MÚLTIPLAS EMPRESAS ---
                    if len(empresas_analisadas) == 1:
                        # Se for apenas 1 empresa, mostrar direto sem tabs
                        empresa = empresas_analisadas.iloc[0]
    
                        # Cabeçalho da empresa
                        st.markdown(f"### {empresa['ID']}")
                        st.caption(f"**Setor:** {empresa['DS_CNAE']}")
                        st.markdown("<br>", unsafe_allow_html=True)
    
                        # Métricas principais em cards
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Faturamento", f"R$ {empresa['VL_FATU']:,.0f}")
                        with col2:
                            st.metric("Saldo", f"R$ {empresa['VL_SLDO']:,.0f}")
                        with col3:
                            st.metric("Risco", empresa['Risco_Santander'])
                        with col4:
                            oport_color = COLOR_OPORTUNIDADE.get(empresa['Oportunidade_Credito'], {'bg': '#E0E0E0', 'text': '#000000'})
                            st.markdown(f"<div style='text-align: center;'><small>Oportunidade</small><br><span style='background-color: {oport_color['bg']}; color: {oport_color['text']}; padding: 5px 15px; border-radius: 8px; font-weight: 600; display: inline-block; margin-top: 5px;'>{empresa['Oportunidade_Credito']}</span></div>", unsafe_allow_html=True)
    
                        st.markdown("<br>", unsafe_allow_html=True)
    
                        # Usar tabs para organizar o conteúdo - ordem otimizada para analista de crédito
                        tab1, tab2, tab3 = st.tabs(["🎯 Recomendações", "💡 Análise de Risco", "📊 Dados Gerais"])
    
                        with tab1:
                            st.markdown("### Produtos Recomendados")
    
                            recomendacoes = []
    
                            if empresa['Oportunidade_Credito'] in ['Ouro', 'Prata']:
                                recomendacoes.append(("💼", "Linha de Crédito para Expansão", "Ideal para investimentos em infraestrutura"))
                                recomendacoes.append(("💰", "Capital de Giro Rotativo", "Flexibilidade para operações do dia a dia"))
                                if empresa['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                    recomendacoes.append(("📈", "Antecipação de Recebíveis", "Melhore seu fluxo de caixa"))
    
                            if empresa['Oportunidade_Credito'] == 'Bronze':
                                recomendacoes.append(("💳", "Capital de Giro de Curto Prazo", "Necessidades pontuais"))
                                recomendacoes.append(("📄", "Desconto de Duplicatas", "Liquidez imediata"))
    
                            if empresa['VL_SLDO'] > empresa['VL_FATU'] * 0.1:
                                recomendacoes.append(("💎", "Produtos de Investimento", "Otimize sua reserva financeira"))
                                recomendacoes.append(("🏦", "CDB Corporativo", "Rentabilidade com liquidez"))
    
                            if empresa['Dependencia_B2B'] == 'Hub de Pagamentos' or empresa['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                recomendacoes.append(("💸", "Soluções de Pagamento em Lote", "Automatize seus processos"))
    
                            if recomendacoes:
                                col_rec1, col_rec2 = st.columns(2)
                                for idx, (icon, titulo, descricao) in enumerate(recomendacoes):
                                    with (col_rec1 if idx % 2 == 0 else col_rec2):
                                        with st.container(border=True):
                                            st.markdown(f"### {icon} {titulo}")
                                            st.markdown(descricao)
                            else:
                                st.info("Consulte um especialista para produtos adequados ao perfil desta empresa.")
    
                        with tab2:
                            st.markdown("### Análise Detalhada")
    
                            insights = []
    
                            # Insight 1: Saúde Financeira
                            if empresa['Saude_Financeira'] == 'Saudável':
                                insights.append(("✅", "Situação Positiva", "Empresa com saldo positivo, demonstrando boa gestão de caixa."))
                            elif empresa['Saude_Financeira'] == 'Alavancagem Estratégica':
                                insights.append(("📊", "Alavancagem Controlada", "Dívida inferior a 5% do faturamento, indicando uso estratégico de crédito."))
                            elif empresa['Saude_Financeira'] == 'Ponto de Atenção':
                                insights.append(("⚠️", "Atenção Necessária", "Dívida entre 5-10% do faturamento. Monitoramento recomendado."))
                            else:
                                insights.append(("🔴", "Risco Elevado", "Dívida superior a 10% do faturamento ou faturamento crítico."))
    
                            # Insight 2: Maturidade
                            if empresa['Maturidade'] == 'Madura':
                                insights.append(("🏢", "Empresa Consolidada", f"Com {empresa['Tempo_Atividade_Anos']} anos de operação, demonstra estabilidade no mercado."))
                            else:
                                insights.append(("🌱", "Empresa em Crescimento", f"Com {empresa['Tempo_Atividade_Anos']} anos, está em fase de expansão."))
    
                            # Insight 3: Dependência B2B
                            if empresa['Dependencia_B2B'] == 'Hub de Pagamentos':
                                insights.append(("💸", "Hub de Pagamentos", "Realiza muitos pagamentos mas recebe pouco. Pode ser uma distribuidora ou empresa com alta dependência de fornecedores."))
                            elif empresa['Dependencia_B2B'] == 'Concentradora de Recebimentos':
                                insights.append(("💰", "Concentradora de Receitas", "Recebe muito mas paga pouco. Pode ser uma varejista ou prestadora de serviços com muitos clientes finais."))
                            elif empresa['Dependencia_B2B'] == 'Alta Concentração em Clientes':
                                insights.append(("📊", "Alta Dependência de Clientes", "Forte concentração em recebimentos. Risco de dependência de poucos clientes."))
                            elif empresa['Dependencia_B2B'] == 'Alta Concentração em Fornecedores':
                                insights.append(("🏭", "Alta Dependência de Fornecedores", "Forte concentração em pagamentos. Risco de dependência de poucos fornecedores."))
                            elif empresa['Dependencia_B2B'] == 'Relacionamento Equilibrado':
                                insights.append(("⚖️", "Cadeia Balanceada", "Equilíbrio saudável entre pagamentos e recebimentos."))
    
                            # Insight 4: Oportunidade de Crédito
                            if empresa['Oportunidade_Credito'] == 'Ouro':
                                insights.append(("🥇", "Excelente Oportunidade", "Cliente ideal para produtos de crédito premium, expansão e investimentos."))
                            elif empresa['Oportunidade_Credito'] == 'Prata':
                                insights.append(("🥈", "Boa Oportunidade", "Cliente adequado para capital de giro e financiamentos estruturados."))
                            elif empresa['Oportunidade_Credito'] == 'Bronze':
                                insights.append(("🥉", "Oportunidade Pontual", "Cliente com necessidade de capital de curto prazo ou produtos específicos."))
                            else:
                                insights.append(("⛔", "Não Elegível", "Cliente requer análise mais profunda ou reestruturação antes de novos créditos."))
    
                            # Insight 5: Análise de Fluxo de Caixa
                            if empresa['VL_SLDO'] < 0 and empresa['VL_FATU'] > 0:
                                proporcao = abs(empresa['VL_SLDO']) / empresa['VL_FATU'] * 100
                                insights.append(("💳", "Análise de Caixa", f"Saldo negativo representa {proporcao:.1f}% do faturamento anual."))
                            elif empresa['VL_SLDO'] > 0:
                                proporcao = empresa['VL_SLDO'] / empresa['VL_FATU'] * 100 if empresa['VL_FATU'] > 0 else 0
                                insights.append(("💰", "Reserva Saudável", f"Saldo positivo equivale a {proporcao:.1f}% do faturamento anual."))
    
                            # Exibir insights em cards
                            for icon, titulo, descricao in insights:
                                with st.container(border=True):
                                    st.markdown(f"### {icon} {titulo}")
                                    st.markdown(descricao)
    
                        with tab3:
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
    
                    else:
                        # Se forem múltiplas empresas, usar tabs por empresa
                        tabs = st.tabs([f"{emp['ID']}" for _, emp in empresas_analisadas.iterrows()])
    
                        for tab_idx, (idx, empresa) in enumerate(empresas_analisadas.iterrows()):
                            with tabs[tab_idx]:
                                # Cabeçalho da empresa
                                st.caption(f"**Setor:** {empresa['DS_CNAE']}")
                                st.markdown("<br>", unsafe_allow_html=True)
    
                                # Métricas principais em cards
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Faturamento", f"R$ {empresa['VL_FATU']:,.0f}")
                                with col2:
                                    st.metric("Saldo", f"R$ {empresa['VL_SLDO']:,.0f}")
                                with col3:
                                    st.metric("Risco", empresa['Risco_Santander'])
                                with col4:
                                    oport_color = COLOR_OPORTUNIDADE.get(empresa['Oportunidade_Credito'], {'bg': '#E0E0E0', 'text': '#000000'})
                                    st.markdown(f"<div style='text-align: center;'><small>Oportunidade</small><br><span style='background-color: {oport_color['bg']}; color: {oport_color['text']}; padding: 5px 15px; border-radius: 8px; font-weight: 600; display: inline-block; margin-top: 5px;'>{empresa['Oportunidade_Credito']}</span></div>", unsafe_allow_html=True)
    
                                st.markdown("<br>", unsafe_allow_html=True)
    
                                # Subtabs dentro de cada empresa - ordem otimizada para analista de crédito
                                subtab1, subtab2, subtab3 = st.tabs(["🎯 Recomendações", "💡 Análise de Risco", "📊 Dados Gerais"])
    
                                with subtab1:
                                    st.markdown("### Produtos Recomendados")
    
                                    recomendacoes = []
    
                                    if empresa['Oportunidade_Credito'] in ['Ouro', 'Prata']:
                                        recomendacoes.append(("💼", "Linha de Crédito para Expansão", "Ideal para investimentos em infraestrutura"))
                                        recomendacoes.append(("💰", "Capital de Giro Rotativo", "Flexibilidade para operações do dia a dia"))
                                        if empresa['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                            recomendacoes.append(("📈", "Antecipação de Recebíveis", "Melhore seu fluxo de caixa"))
    
                                    if empresa['Oportunidade_Credito'] == 'Bronze':
                                        recomendacoes.append(("💳", "Capital de Giro de Curto Prazo", "Necessidades pontuais"))
                                        recomendacoes.append(("📄", "Desconto de Duplicatas", "Liquidez imediata"))
    
                                    if empresa['VL_SLDO'] > empresa['VL_FATU'] * 0.1:
                                        recomendacoes.append(("💎", "Produtos de Investimento", "Otimize sua reserva financeira"))
                                        recomendacoes.append(("🏦", "CDB Corporativo", "Rentabilidade com liquidez"))
    
                                    if empresa['Dependencia_B2B'] == 'Hub de Pagamentos' or empresa['Intensidade_B2B'] in ['Alta', 'Muito Alta']:
                                        recomendacoes.append(("💸", "Soluções de Pagamento em Lote", "Automatize seus processos"))
    
                                    if recomendacoes:
                                        col_rec1, col_rec2 = st.columns(2)
                                        for idx_rec, (icon, titulo, descricao) in enumerate(recomendacoes):
                                            with (col_rec1 if idx_rec % 2 == 0 else col_rec2):
                                                with st.container(border=True):
                                                    st.markdown(f"### {icon} {titulo}")
                                                    st.markdown(descricao)
                                    else:
                                        st.info("Consulte um especialista para produtos adequados ao perfil desta empresa.")
    
                                with subtab2:
                                    st.markdown("### Análise Detalhada")
    
                                    insights = []
    
                                    if empresa['Saude_Financeira'] == 'Saudável':
                                        insights.append(("✅", "Situação Positiva", "Empresa com saldo positivo, demonstrando boa gestão de caixa."))
                                    elif empresa['Saude_Financeira'] == 'Alavancagem Estratégica':
                                        insights.append(("📊", "Alavancagem Controlada", "Dívida inferior a 5% do faturamento, indicando uso estratégico de crédito."))
                                    elif empresa['Saude_Financeira'] == 'Ponto de Atenção':
                                        insights.append(("⚠️", "Atenção Necessária", "Dívida entre 5-10% do faturamento. Monitoramento recomendado."))
                                    else:
                                        insights.append(("🔴", "Risco Elevado", "Dívida superior a 10% do faturamento ou faturamento crítico."))
    
                                    if empresa['Maturidade'] == 'Madura':
                                        insights.append(("🏢", "Empresa Consolidada", f"Com {empresa['Tempo_Atividade_Anos']} anos de operação, demonstra estabilidade no mercado."))
                                    else:
                                        insights.append(("🌱", "Empresa em Crescimento", f"Com {empresa['Tempo_Atividade_Anos']} anos, está em fase de expansão."))
    
                                    if empresa['Dependencia_B2B'] == 'Hub de Pagamentos':
                                        insights.append(("💸", "Hub de Pagamentos", "Realiza muitos pagamentos mas recebe pouco. Pode ser uma distribuidora ou empresa com alta dependência de fornecedores."))
                                    elif empresa['Dependencia_B2B'] == 'Concentradora de Recebimentos':
                                        insights.append(("💰", "Concentradora de Receitas", "Recebe muito mas paga pouco. Pode ser uma varejista ou prestadora de serviços com muitos clientes finais."))
                                    elif empresa['Dependencia_B2B'] == 'Alta Concentração em Clientes':
                                        insights.append(("📊", "Alta Dependência de Clientes", "Forte concentração em recebimentos. Risco de dependência de poucos clientes."))
                                    elif empresa['Dependencia_B2B'] == 'Alta Concentração em Fornecedores':
                                        insights.append(("🏭", "Alta Dependência de Fornecedores", "Forte concentração em pagamentos. Risco de dependência de poucos fornecedores."))
                                    elif empresa['Dependencia_B2B'] == 'Relacionamento Equilibrado':
                                        insights.append(("⚖️", "Cadeia Balanceada", "Equilíbrio saudável entre pagamentos e recebimentos."))
    
                                    if empresa['Oportunidade_Credito'] == 'Ouro':
                                        insights.append(("🥇", "Excelente Oportunidade", "Cliente ideal para produtos de crédito premium, expansão e investimentos."))
                                    elif empresa['Oportunidade_Credito'] == 'Prata':
                                        insights.append(("🥈", "Boa Oportunidade", "Cliente adequado para capital de giro e financiamentos estruturados."))
                                    elif empresa['Oportunidade_Credito'] == 'Bronze':
                                        insights.append(("🥉", "Oportunidade Pontual", "Cliente com necessidade de capital de curto prazo ou produtos específicos."))
                                    else:
                                        insights.append(("⛔", "Não Elegível", "Cliente requer análise mais profunda ou reestruturação antes de novos créditos."))
    
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
    
                                with subtab3:
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
    
                    # --- ANÁLISE COMPARATIVA (se mais de 1 CNPJ) ---
                    if len(empresas_analisadas) > 1:
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
                            fig = go.Figure(go.Pie(
                                labels=risco_dist.index,
                                values=risco_dist.values,
                                hole=0.3
                            ))
                            fig.update_layout(
                                template="plotly_white",
                                margin=dict(t=10, l=10, r=10, b=10)
                            )
                            st.plotly_chart(fig, use_container_width=True)
    
                        # Insights comparativos
                        st.markdown("##### Insights Comparativos")
    
                        melhor_oportunidade = empresas_analisadas.loc[
                            empresas_analisadas['Oportunidade_Credito'].isin(['Ouro', 'Prata', 'Bronze'])
                        ].sort_values(
                            'Oportunidade_Credito',
                            key=lambda x: x.map({'Ouro': 1, 'Prata': 2, 'Bronze': 3})
                        ).head(1)
    
                        if not melhor_oportunidade.empty:
                            st.success(f"**Melhor Oportunidade**: {melhor_oportunidade.iloc[0]['ID']} (Tier {melhor_oportunidade.iloc[0]['Oportunidade_Credito']})")
    
                        maior_faturamento = empresas_analisadas.loc[empresas_analisadas['VL_FATU'].idxmax()]
                        st.info(f"**Maior Faturamento**: {maior_faturamento['ID']} (R$ {maior_faturamento['VL_FATU']:,.0f})")
    
                        maior_risco = empresas_analisadas[empresas_analisadas['Risco_Santander'].isin(['Alto', 'Muito Alto'])]
                        if not maior_risco.empty:
                            st.warning(f"**Atenção**: {len(maior_risco)} empresa(s) com risco Alto/Muito Alto")
            else:
                st.warning("Por favor, selecione ao menos um CNPJ válido.")

        elif gerar_insights and not cnpjs_list:
                st.info("Selecione um ou mais CNPJs para começar a análise.")

# === PAGINA 3: CADEIA DE VALOR ===
elif pagina == "Cadeia de Valor":
    st.title('Analise da Cadeia de Valor')
    st.markdown("Selecione uma empresa para visualizar o risco de seus principais clientes e fornecedores em um mapa de rede.")

    options = sorted(df_processed['ID'].unique().tolist())
    empresa_selecionada_id = st.selectbox(
        'Selecione a Empresa para Análise:',
        options=options,
        help="Digite o ID da empresa para buscar."
    )

    if empresa_selecionada_id:
        clientes = base2[base2['ID_RCBE'] == empresa_selecionada_id]
        top_clientes_id = clientes.groupby('ID_PGTO')['VL'].sum().nlargest(5).index
        clientes_df = df_processed[df_processed['ID'].isin(top_clientes_id)]

        fornecedores = base2[base2['ID_PGTO'] == empresa_selecionada_id]
        top_fornecedores_id = fornecedores.groupby('ID_RCBE')['VL'].sum().nlargest(5).index
        fornecedores_df = df_processed[df_processed['ID'].isin(top_fornecedores_id)]

        empresa_central_info = df_processed[df_processed['ID'] == empresa_selecionada_id].iloc[0]

        col_kpi, col_graph = st.columns([1, 2])
        with col_kpi:
            st.markdown("###### Resumo do Risco da Cadeia")
            with st.container(border=True):
                alto_risco_clientes = clientes_df[clientes_df['Risco_Santander'].isin(['Alto', 'Muito Alto'])].shape[0]
                st.metric("Clientes de Alto Risco", f"{alto_risco_clientes} de {len(clientes_df)}",
                          help="Número de clientes, entre os 5 principais, com risco 'Alto' ou 'Muito Alto'.")

            with st.container(border=True):
                alto_risco_fornecedores = fornecedores_df[fornecedores_df['Risco_Santander'].isin(['Alto', 'Muito Alto'])].shape[0]
                st.metric("Fornecedores de Alto Risco", f"{alto_risco_fornecedores} de {len(fornecedores_df)}",
                          help="Número de fornecedores, entre os 5 principais, com risco 'Alto' ou 'Muito Alto'.")

            st.markdown("###### Analise de Dependencia")
            with st.container(border=True):
                dependencias_criticas = []

                for _, row in clientes_df.iterrows():
                    dep = row.get('Dependencia_B2B', 'Nao Classificado')
                    if dep in ['Alta Concentracao em Fornecedores', 'Concentradora de Recebimentos']:
                        dependencias_criticas.append('cliente')

                for _, row in fornecedores_df.iterrows():
                    dep = row.get('Dependencia_B2B', 'Nao Classificado')
                    if dep in ['Alta Concentracao em Clientes', 'Hub de Pagamentos']:
                        dependencias_criticas.append('fornecedor')

                if dependencias_criticas:
                    st.warning(f"⚠️ {len(dependencias_criticas)} empresa(s) com dependencia critica detectada")
                else:
                    st.success("✅ Nenhuma dependencia critica detectada")

        with col_graph:
            st.markdown("###### Mapa da Cadeia de Valor")
            risco_color_map = {
                'Muito Baixo': '#2E8B57', 'Baixo': '#90EE90',
                'Medio': '#FFD700', 'Alto': '#FFA07A', 'Muito Alto': '#DC143C'
            }

            dependencia_symbol_map = {
                'Concentradora de Recebimentos': '💰',
                'Alta Concentracao em Clientes': '📊',
                'Alta Concentracao em Fornecedores': '🏭',
                'Hub de Pagamentos': '💸',
                'Relacionamento Equilibrado': '⚖️',
                'Nao Classificado': ''
            }

            graph = graphviz.Digraph()
            graph.attr('node', shape='box', style='rounded,filled')

            risco_central = empresa_central_info['Risco_Santander']
            dep_central = empresa_central_info.get('Dependencia_B2B', 'Nao Classificado')
            simbolo_central = dependencia_symbol_map.get(dep_central, '')

            label_central = f"{empresa_selecionada_id}\n(Risco: {risco_central})"
            if dep_central != 'Nao Classificado':
                label_central += f"\n{simbolo_central} {dep_central}"

            graph.node(str(empresa_selecionada_id), label_central, fillcolor="#ADD8E6")

            for _, row in clientes_df.iterrows():
                risco = row['Risco_Santander']
                dep = row.get('Dependencia_B2B', 'Nao Classificado')
                cor = risco_color_map.get(risco, '#D3D3D3')
                simbolo = dependencia_symbol_map.get(dep, '')

                label = f"Cliente: {row['ID']}\n(Risco: {risco})"
                if dep != 'Nao Classificado':
                    label += f"\n{simbolo} {dep}"

                if dep in ['Alta Concentracao em Fornecedores', 'Concentradora de Recebimentos']:
                    graph.node(str(row['ID']), label, fillcolor=cor, penwidth="3", color="red")
                else:
                    graph.node(str(row['ID']), label, fillcolor=cor)

                graph.edge(str(row['ID']), str(empresa_selecionada_id))

            for _, row in fornecedores_df.iterrows():
                risco = row['Risco_Santander']
                dep = row.get('Dependencia_B2B', 'Nao Classificado')
                cor = risco_color_map.get(risco, '#D3D3D3')
                simbolo = dependencia_symbol_map.get(dep, '')

                label = f"Forn.: {row['ID']}\n(Risco: {risco})"
                if dep != 'Nao Classificado':
                    label += f"\n{simbolo} {dep}"

                if dep in ['Alta Concentracao em Clientes', 'Hub de Pagamentos']:
                    graph.node(str(row['ID']), label, fillcolor=cor, penwidth="3", color="red")
                else:
                    graph.node(str(row['ID']), label, fillcolor=cor)

                graph.edge(str(empresa_selecionada_id), str(row['ID']))

            st.graphviz_chart(graph)

            with st.expander("📖 Legenda do Mapa de Rede"):
                col_leg1, col_leg2 = st.columns(2)

                with col_leg1:
                    st.markdown("**🎨 Cores (Nivel de Risco):**")
                    st.markdown("- 🟢 Verde Escuro: Risco Muito Baixo")
                    st.markdown("- 🟢 Verde Claro: Risco Baixo")
                    st.markdown("- 🟡 Amarelo: Risco Medio")
                    st.markdown("- 🟠 Laranja: Risco Alto")
                    st.markdown("- 🔴 Vermelho: Risco Muito Alto")
                    st.markdown("- 🔵 Azul: Empresa Central")

                with col_leg2:
                    st.markdown("**📊 Simbolos (Dependencia B2B):**")
                    st.markdown("- 💰 Concentradora de Recebimentos")
                    st.markdown("- 📊 Alta Concentracao em Clientes")
                    st.markdown("- 🏭 Alta Concentracao em Fornecedores")
                    st.markdown("- 💸 Hub de Pagamentos")
                    st.markdown("- ⚖️ Relacionamento Equilibrado")
                    st.markdown("")
                    st.markdown("**⚠️ Borda vermelha:** Indica dependencia critica")

                st.info("As setas indicam o fluxo de pagamento: saindo da empresa pagadora para a recebedora.")

        with st.expander("Ver tabelas de detalhes dos principais clientes e fornecedores"):
            col_clientes, col_fornecedores = st.columns(2)
            with col_clientes:
                st.write("**Principais Clientes (Top 5)**")
                cols_detail = ['ID', 'DS_CNAE', 'Saude_Financeira', 'Risco_Santander']
                if 'Dependencia_B2B' in clientes_df.columns:
                    cols_detail.append('Dependencia_B2B')
                st.dataframe(clientes_df[cols_detail], width='stretch')
            with col_fornecedores:
                st.write("**Principais Fornecedores (Top 5)**")
                cols_detail = ['ID', 'DS_CNAE', 'Saude_Financeira', 'Risco_Santander']
                if 'Dependencia_B2B' in fornecedores_df.columns:
                    cols_detail.append('Dependencia_B2B')
                st.dataframe(fornecedores_df[cols_detail], width='stretch')
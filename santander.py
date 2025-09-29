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

# Sidebar de filtros
# ALTERAÇÃO: use_container_width=True -> width='stretch'
st.sidebar.image("santander_logo.png", width='stretch')
st.sidebar.title('Filtros da Carteira')
cnae_options = ['Todos'] + sorted(df_processed['DS_CNAE'].unique().tolist())
perfil_options = ['Todos'] + sorted(df_processed['Perfil_da_Empresa'].unique().tolist())
risco_options = ['Todos'] + ['Muito Baixo', 'Baixo', 'Médio', 'Alto', 'Muito Alto']
oportunidade_options = ['Todos'] + ['Ouro', 'Prata', 'Bronze', 'Não Elegível']

selected_cnae = st.sidebar.selectbox('Setor (CNAE)', cnae_options)
selected_perfil = st.sidebar.selectbox('Perfil da Empresa', perfil_options)
selected_risco = st.sidebar.selectbox('Nível de Risco', risco_options)
selected_oportunidade = st.sidebar.selectbox('Oportunidade de Crédito', oportunidade_options)

# Aplicação dos filtros
filtered_df = df_processed.copy()
if selected_cnae != 'Todos': filtered_df = filtered_df[filtered_df['DS_CNAE'] == selected_cnae]
if selected_perfil != 'Todos': filtered_df = filtered_df[filtered_df['Perfil_da_Empresa'] == selected_perfil]
if selected_risco != 'Todos': filtered_df = filtered_df[filtered_df['Risco_Santander'] == selected_risco]
if selected_oportunidade != 'Todos': filtered_df = filtered_df[filtered_df['Oportunidade_Credito'] == selected_oportunidade]

# Seção de Título e KPIs
st.title('Dashboard de Risco e Oportunidades')
st.subheader("Olá Eduardo, essa é sua carteira de clientes PJ")

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

# --- SEÇÃO DE ANÁLISE DE CADEIA DE VALOR (MODIFICADA) ---
st.markdown("---")
st.subheader("🔗 Análise da Cadeia de Valor do Cliente")
st.markdown("Selecione uma empresa para visualizar o risco de seus principais clientes e fornecedores em um mapa de rede. Onde o topo simboliza os clientes, no meio a empresa em análise e embaixo seus fornecedores.")

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
        
        st.markdown("###### Análise de Dependência")
        with st.container(border=True):
            dependencias_criticas = []
            
            for _, row in clientes_df.iterrows():
                dep = row.get('Dependencia_B2B', 'Não Classificado')
                if dep in ['Alta Concentração em Fornecedores', 'Concentradora de Recebimentos']:
                    dependencias_criticas.append('cliente')
            
            for _, row in fornecedores_df.iterrows():
                dep = row.get('Dependencia_B2B', 'Não Classificado')
                if dep in ['Alta Concentração em Clientes', 'Hub de Pagamentos']:
                    dependencias_criticas.append('fornecedor')
            
            if dependencias_criticas:
                st.warning(f"⚠️ {len(dependencias_criticas)} empresa(s) com dependência crítica detectada")
            else:
                st.success("✅ Nenhuma dependência crítica detectada")

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
        
        label_central = f"{empresa_selecionada_id}\n(Risco: {risco_central})"
        if dep_central != 'Não Classificado':
            label_central += f"\n{simbolo_central} {dep_central}"
        
        graph.node(str(empresa_selecionada_id), label_central, fillcolor="#ADD8E6")

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
            
            graph.edge(str(row['ID']), str(empresa_selecionada_id))

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
            
            graph.edge(str(empresa_selecionada_id), str(row['ID']))
            
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
                st.markdown("")
                st.markdown("**⚠️ Borda vermelha:** Indica dependência crítica")
            
            st.info("As setas indicam o fluxo de pagamento: saindo da empresa pagadora para a recebedora.")

    with st.expander("Ver tabelas de detalhes dos principais clientes e fornecedores"):
        col_clientes, col_fornecedores = st.columns(2)
        with col_clientes:
            st.write("**Principais Clientes (Top 5)**")
            cols_detail = ['ID', 'DS_CNAE', 'Saude_Financeira', 'Risco_Santander']
            if 'Dependencia_B2B' in clientes_df.columns:
                cols_detail.append('Dependencia_B2B')
            # ALTERAÇÃO: use_container_width=True -> width='stretch'
            st.dataframe(clientes_df[cols_detail], width='stretch')
        with col_fornecedores:
            st.write("**Principais Fornecedores (Top 5)**")
            cols_detail = ['ID', 'DS_CNAE', 'Saude_Financeira', 'Risco_Santander']
            if 'Dependencia_B2B' in fornecedores_df.columns:
                cols_detail.append('Dependencia_B2B')
            # ALTERAÇÃO: use_container_width=True -> width='stretch'
            st.dataframe(fornecedores_df[cols_detail], width='stretch')

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
import streamlit as st
import pandas as pd
import datetime
from pathlib import Path
import plotly.express as px

# --- Configuração da Página ---
# Usar o modo wide para melhor aproveitamento do espaço e definir um título para a aba do navegador
st.set_page_config(layout="wide", page_title="Dashboard de Análise de Risco")

# --- Funções de Processamento de Dados ---

@st.cache_data
def load_data():
    """Carrega os dados dos arquivos CSV de forma segura."""
    base1_path = Path("Base1.csv")
    base2_path = Path("Base2.csv")

    if not base1_path.exists() or not base2_path.exists():
        st.error("Arquivos de dados (Base1.csv e Base2.csv) não encontrados. Por favor, certifique-se de que eles estão na mesma pasta do script.")
        return None, None
     
    base1 = pd.read_csv(base1_path)
    base2 = pd.read_csv(base2_path)
    return base1, base2

@st.cache_data
def process_data(df1, df2):
    """
    Executa todo o processamento, enriquecimento e classificação dos dados.
    Esta função agora inclui a nova lógica de saúde financeira e risco.
    """
    # --- Processamento Base 1: Perfil da Empresa ---
    df1['DT_ABRT'] = pd.to_datetime(df1['DT_ABRT'])
    
    # Maturidade da Empresa
    hoje = datetime.datetime.now()
    df1['Tempo_Atividade_Anos'] = round((hoje - df1['DT_ABRT']).dt.days / 365.25, 1)
    df1['Maturidade'] = df1['Tempo_Atividade_Anos'].apply(lambda x: 'Madura' if x > 5 else 'Inicial')

    # LÓGICA REFINADA: Reintroduzindo "Ponto de Atenção" com novos limites
    def classificar_saude_financeira(row):
        faturamento = row['VL_FATU']
        saldo = row['VL_SLDO']
        
        if faturamento <= 0:
            return 'Endividada' if saldo < 0 else 'Saudável'

        if saldo >= 0:
            return 'Saudável'
        
        proporcao_divida = abs(saldo) / faturamento
        
        if proporcao_divida < 0.05:
            return 'Alavancagem Estratégica'
        elif proporcao_divida < 0.10: # De 5% a 10%
            return 'Ponto de Atenção'
        else: # Acima de 10%
            return 'Endividada'

    df1['Saude_Financeira'] = df1.apply(classificar_saude_financeira, axis=1)
    df1['Perfil_da_Empresa'] = df1['Maturidade'] + ' - ' + df1['Saude_Financeira']

    # --- Processamento Base 2: Relacionamento B2B ---
    df2_clean = df2.dropna(subset=['ID_PGTO', 'ID_RCBE'])
     
    relacionamento_recebido = df2_clean.groupby('ID_RCBE')['ID_PGTO'].count().reset_index(name='Transacoes_Recebidas')
    relacionamento_pago = df2_clean.groupby('ID_PGTO')['ID_RCBE'].count().reset_index(name='Transacoes_Pagas')
     
    relacionamento = pd.merge(relacionamento_recebido, relacionamento_pago, left_on='ID_RCBE', right_on='ID_PGTO', how='outer')
    relacionamento = relacionamento.rename(columns={'ID_RCBE': 'ID_CNPJ'}).drop(columns='ID_PGTO')
    relacionamento.fillna(0, inplace=True)
    relacionamento['Total_Transacoes'] = relacionamento['Transacoes_Recebidas'] + relacionamento['Transacoes_Pagas']

    def classificar_b2b_intensidade(row):
        total = row['Total_Transacoes']
        if total > 50: return 'Muito Alta'
        elif total > 30: return 'Alta'
        elif total > 10: return 'Média'
        elif total > 5: return 'Baixa'
        else: return 'Muito Baixa'
    relacionamento['Intensidade_B2B'] = relacionamento.apply(classificar_b2b_intensidade, axis=1)
     
    def analisar_dependencia(row):
        pgto = row['Transacoes_Pagas']
        rcbe = row['Transacoes_Recebidas']
        if rcbe == 0 and pgto > 0: return 'Hub de Pagamentos'
        if pgto == 0 and rcbe > 0: return 'Concentradora de Recebimentos'
        if rcbe > 3 * pgto: return 'Dependente de Clientes'
        elif pgto > 3 * rcbe: return 'Dependente de Fornecedores'
        else: return 'Relacionamento Equilibrado'
    relacionamento['Dependencia_B2B'] = relacionamento.apply(analisar_dependencia, axis=1)

    # --- Unificação e Classificação Final ---
    df_merged = pd.merge(df1, relacionamento, left_on='ID', right_on='ID_CNPJ', how='left')
    df_merged.fillna({'Total_Transacoes': 0, 'Intensidade_B2B': 'Não Classificado', 'Dependencia_B2B': 'Não Classificado'}, inplace=True)

    # LÓGICA REFINADA: Classificação de Risco com "Ponto de Atenção"
    def classificar_risco(row):
        score = 0
        if row['Saude_Financeira'] == 'Saudável': score -= 3
        if row['Saude_Financeira'] == 'Alavancagem Estratégica': score -= 1
        if row['Saude_Financeira'] == 'Ponto de Atenção': score += 2 # Risco intermediário
        if row['Saude_Financeira'] == 'Endividada': score += 4

        if row['Maturidade'] == 'Madura': score -= 1
        else: score += 1

        if row['Dependencia_B2B'] in ['Dependente de Clientes', 'Dependente de Fornecedores']: score += 1
        if row['Dependencia_B2B'] == 'Hub de Pagamentos': score -= 1
        
        if score <= -2: return 'Muito Baixo'
        elif score <= 0: return 'Baixo'
        elif score <= 2: return 'Médio'
        elif score <= 4: return 'Alto'
        else: return 'Muito Alto'

    df_merged['Risco_Santander'] = df_merged.apply(classificar_risco, axis=1)

    # Lógica de Oportunidade de Crédito (inalterada, Ponto de Atenção não é oportunidade)
    cond_oportunidade = (
        (df_merged['Saude_Financeira'].isin(['Saudável', 'Alavancagem Estratégica'])) &
        (df_merged['Risco_Santander'].isin(['Baixo', 'Muito Baixo']))
    )
    df_merged['Oportunidade_Credito'] = cond_oportunidade.apply(lambda x: 'Sim' if x else 'Não')

    return df_merged

# --- Início do Layout do Dashboard ---

st.title('🏦 Dashboard de Análise de Perfil de Empresas')
st.markdown("""
Este dashboard foi aprimorado para uma análise de risco mais profunda, diferenciando empresas **endividadas** daquelas em **alavancagem estratégica**. 
Use os filtros para explorar o portfólio e identificar clientes com perfis de baixo risco e alto potencial de crescimento.
""")

base1, base2 = load_data()

if base1 is not None and base2 is not None:
    df_final = process_data(base1, base2)

    # --- Filtros na Barra Lateral ---
    st.sidebar.header('Filtros Interativos')
    
    selected_cnae = st.sidebar.selectbox('Filtrar por Setor (CNAE):', ['Todos'] + sorted(df_final['DS_CNAE'].unique().tolist()))
    selected_perfil = st.sidebar.selectbox('Filtrar por Perfil da Empresa:', ['Todos'] + sorted(df_final['Perfil_da_Empresa'].unique().tolist()))
    selected_risco = st.sidebar.selectbox('Filtrar por Nível de Risco:', ['Todos'] + sorted(df_final['Risco_Santander'].unique().tolist()))
    selected_oportunidade = st.sidebar.selectbox('Filtrar por Oportunidade de Crédito:', ['Todos', 'Sim', 'Não'])

    # Aplicação dos filtros
    filtered_df = df_final.copy()
    if selected_cnae != 'Todos': filtered_df = filtered_df[filtered_df['DS_CNAE'] == selected_cnae]
    if selected_perfil != 'Todos': filtered_df = filtered_df[filtered_df['Perfil_da_Empresa'] == selected_perfil]
    if selected_risco != 'Todos': filtered_df = filtered_df[filtered_df['Risco_Santander'] == selected_risco]
    if selected_oportunidade != 'Todos': filtered_df = filtered_df[filtered_df['Oportunidade_Credito'] == selected_oportunidade]

    # --- KPIs Principais ---
    st.subheader("Visão Geral do Portfólio Filtrado")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Empresas na Seleção", f"{len(filtered_df):,}")
    
    oportunidades = filtered_df[filtered_df['Oportunidade_Credito'] == 'Sim']
    kpi2.metric("Oportunidades de Crédito", f"{len(oportunidades):,}")

    perc_alavancagem = 0
    if not filtered_df.empty:
        perc_alavancagem = (filtered_df['Saude_Financeira'] == 'Alavancagem Estratégica').sum() / len(filtered_df) * 100
    kpi3.metric("Em Alavancagem Estratégica", f"{perc_alavancagem:.1f}%")

    avg_faturamento = 0
    if not filtered_df.empty:
        avg_faturamento = filtered_df['VL_FATU'].mean()
    kpi4.metric("Faturamento Médio", f"R$ {avg_faturamento:,.0f}")
    
    st.markdown("---")

    # --- Visualizações Aprimoradas ---
    st.subheader("Análises Visuais Aprofundadas")
    
    tab1, tab2, tab3 = st.tabs([" Saúde Financeira e Risco", "Análise B2B", "Análise por Setor (CNAE)"])
    
    with tab1:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.write('**Distribuição da Saúde Financeira**')
            saude_counts = filtered_df['Saude_Financeira'].value_counts().reset_index()
            saude_counts.columns = ['Saude_Financeira', 'count']

            # ATUALIZAÇÃO: Mapa de cores e legenda refletem a nova lógica
            color_map = {
                'Saudável': '#2E8B57',
                'Alavancagem Estratégica': '#4682B4',
                'Ponto de Atenção': '#FFD700',
                'Endividada': '#DC143C'
            }

            fig = px.bar(
                saude_counts,
                x='Saude_Financeira',
                y='count',
                color='Saude_Financeira',
                color_discrete_map=color_map,
                labels={'count': 'Número de Empresas', 'Saude_Financeira': 'Saúde Financeira'}
            )
            fig.update_xaxes(title_text='')
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("""
            **Legenda:**
            - **Saudável:** Saldo positivo.
            - **Alavancagem Estratégica:** Saldo negativo < 5% do faturamento.
            - **Ponto de Atenção:** Saldo negativo entre 5% e 10% do faturamento.
            - **Endividada:** Saldo negativo > 10% do faturamento.
            """)
        with col2:
            st.write('**Distribuição de Empresas por Nível de Risco**')
            risco_counts = filtered_df['Risco_Santander'].value_counts().reindex(['Muito Baixo', 'Baixo', 'Médio', 'Alto', 'Muito Alto'])
            st.bar_chart(risco_counts, use_container_width=True)
        st.write('**Relação entre Faturamento e Saldo por Risco**')
        st.scatter_chart(filtered_df, x='VL_FATU', y='VL_SLDO', color='Risco_Santander', use_container_width=True)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.write('**Risco vs. Dependência B2B**')
            b2b_risco_pivot = filtered_df.pivot_table(index='Risco_Santander', columns='Dependencia_B2B', values='ID', aggfunc='count', fill_value=0).T
            st.bar_chart(b2b_risco_pivot, use_container_width=True)
        with col2:
            st.write('**Intensidade do Relacionamento B2B**')
            intensidade_counts = filtered_df['Intensidade_B2B'].value_counts().reindex(['Muito Baixa', 'Baixa', 'Média', 'Alta', 'Muito Alta'])
            st.bar_chart(intensidade_counts, use_container_width=True)

    with tab3:
        st.write('**Faturamento e Saldo Médio por Setor (CNAE)**')
        if not filtered_df.empty:
            cnae_metrics = filtered_df.groupby('DS_CNAE').agg(
                Faturamento_Medio=('VL_FATU', 'mean'),
                Saldo_Medio=('VL_SLDO', 'mean')
            ).sort_values(by='Faturamento_Medio', ascending=False).head(20)
            st.bar_chart(cnae_metrics, use_container_width=True)
        else:
            st.warning("Não há dados para esta visualização com os filtros selecionados.")
            
    st.markdown("---")
    
    # --- NOVA SEÇÃO: Análise de Risco na Cadeia de Valor ---
    st.subheader("🔗 Análise de Risco na Cadeia de Valor")
    st.markdown("Selecione uma empresa para analisar a saúde financeira de seus principais clientes e fornecedores.")

    empresa_selecionada_id = st.selectbox(
        'Selecione a Empresa para Análise de Cadeia:',
        options=df_final['ID'].unique(),
        format_func=lambda x: f"{x} - {df_final[df_final['ID'] == x]['DS_CNAE'].iloc[0]}"
    )

    if empresa_selecionada_id:
        clientes = base2[base2['ID_RCBE'] == empresa_selecionada_id]
        if not clientes.empty:
            top_clientes_id = clientes.groupby('ID_PGTO')['VL'].sum().nlargest(10).index
            clientes_df = df_final[df_final['ID'].isin(top_clientes_id)][['ID', 'DS_CNAE', 'Saude_Financeira', 'Risco_Santander']]
        else:
            clientes_df = pd.DataFrame()

        fornecedores = base2[base2['ID_PGTO'] == empresa_selecionada_id]
        if not fornecedores.empty:
            top_fornecedores_id = fornecedores.groupby('ID_RCBE')['VL'].sum().nlargest(10).index
            fornecedores_df = df_final[df_final['ID'].isin(top_fornecedores_id)][['ID', 'DS_CNAE', 'Saude_Financeira', 'Risco_Santander']]
        else:
            fornecedores_df = pd.DataFrame()

        col_clientes, col_fornecedores = st.columns(2)
        with col_clientes:
            st.write("**Principais Clientes (Risco de Recebimento)**")
            if not clientes_df.empty:
                st.dataframe(clientes_df, use_container_width=True)
            else:
                st.info("Nenhum cliente significativo encontrado nas transações.")
        with col_fornecedores:
            st.write("**Principais Fornecedores (Risco Operacional)**")
            if not fornecedores_df.empty:
                st.dataframe(fornecedores_df, use_container_width=True)
            else:
                st.info("Nenhum fornecedor significativo encontrado nas transações.")

    st.markdown("---")

    # --- Tabelas de Dados com Paginação ---
    cols_display = ['ID', 'DS_CNAE', 'Perfil_da_Empresa', 'VL_FATU', 'VL_SLDO', 
                    'Intensidade_B2B', 'Dependencia_B2B', 'Risco_Santander', 'Oportunidade_Credito']

    st.subheader('Tabela Detalhada de Empresas')
    if 'pagina_empresas' not in st.session_state: st.session_state.pagina_empresas = 0
    linhas_por_pagina = st.slider('Itens por página (Geral)', 10, 100, 15, key='slider_empresas')
    total_linhas = len(filtered_df)
    total_paginas = max(1, (total_linhas // linhas_por_pagina) + (1 if total_linhas % linhas_por_pagina > 0 else 0))
    col_prev, col_page, col_next = st.columns([2, 8, 2])
    if col_prev.button('Anterior', key='prev_emp'): st.session_state.pagina_empresas = max(0, st.session_state.pagina_empresas - 1)
    col_page.write(f"Página **{st.session_state.pagina_empresas + 1}** de **{total_paginas}**")
    if col_next.button('Próxima', key='next_emp'): st.session_state.pagina_empresas = min(total_paginas - 1, st.session_state.pagina_empresas + 1)
    
    inicio = st.session_state.pagina_empresas * linhas_por_pagina
    fim = inicio + linhas_por_pagina
    df_paginado = filtered_df[cols_display].iloc[inicio:fim]
    st.dataframe(df_paginado.style.format({"VL_FATU": "R$ {:,.2f}", "VL_SLDO": "R$ {:,.2f}"}), use_container_width=True)

    st.subheader('Empresas Oportunas para Crédito')
    
    if 'pagina_oportunidades' not in st.session_state: st.session_state.pagina_oportunidades = 0
    
    total_linhas_op = len(oportunidades)
    if total_linhas_op > 0:
        linhas_por_pagina_op = st.slider('Itens por página (Oportunidades)', 10, 100, 10, key='slider_oportunidades')
        total_paginas_op = max(1, (total_linhas_op // linhas_por_pagina_op) + (1 if total_linhas_op % linhas_por_pagina_op > 0 else 0))

        col_op_prev, col_op_page, col_op_next = st.columns([2, 8, 2])
        if col_op_prev.button('Anterior (Op.)', key='prev_op'): st.session_state.pagina_oportunidades = max(0, st.session_state.pagina_oportunidades - 1)
        col_op_page.write(f"Página **{st.session_state.pagina_oportunidades + 1}** de **{total_paginas_op}** (Oportunidades)")
        if col_op_next.button('Próxima (Op.)', key='next_op'): st.session_state.pagina_oportunidades = min(total_paginas_op - 1, st.session_state.pagina_oportunidades + 1)
        
        inicio_op = st.session_state.pagina_oportunidades * linhas_por_pagina_op
        fim_op = inicio_op + linhas_por_pagina_op

        df_oportunidade_paginado = oportunidades[cols_display].iloc[inicio_op:fim_op]
        st.dataframe(df_oportunidade_paginado.style.format({"VL_FATU": "R$ {:,.2f}", "VL_SLDO": "R$ {:,.2f}"}), use_container_width=True)
    else:
        st.info("Nenhuma empresa de oportunidade encontrada com os filtros atuais.")
else:
    st.warning("Aguardando o carregamento dos arquivos de dados...")


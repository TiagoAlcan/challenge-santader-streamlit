import streamlit as st
import pandas as pd
import datetime
from pathlib import Path

# Função para carregar os dados
@st.cache_data
def load_data():
    base1_path = Path("Base1.csv")
    base2_path = Path("Base2.csv")

    if not base1_path.exists() or not base2_path.exists():
        st.error("Arquivos de dados (Base1.csv e Base2.csv) não encontrados. Por favor, certifique-se de que eles estão na mesma pasta do script.")
        return None, None
    
    base1 = pd.read_csv(base1_path)
    base2 = pd.read_csv(base2_path)
    return base1, base2

# Função para processar os dados
def process_data(df1, df2):
    # Processamento da Base 1
    df1['DT_ABRT'] = pd.to_datetime(df1['DT_ABRT'])
    df1['DT_REFE'] = pd.to_datetime(df1['DT_REFE'])
    df1['Tempo_Atividade_dias'] = (df1['DT_REFE'] - df1['DT_ABRT']).dt.days

    # Classificação do tempo de atividade
    hoje = datetime.datetime.now()
    df1['Tempo_Atividade_Anos'] = (hoje - df1['DT_ABRT']).dt.days / 365.25
    df1['Maturidade'] = df1['Tempo_Atividade_Anos'].apply(lambda x: 'Madura' if x > 5 else 'Inicial')

    # Classificação do estado financeiro
    def classificar_estado_financeiro(row):
        faturamento = row['VL_FATU']
        saldo = row['VL_SLDO']
        if faturamento > 1000000 and saldo > 0:
            return 'Ascensão'
        elif faturamento > 1000000 and saldo <= 0:
            return 'Declínio'
        elif faturamento <= 1000000 and saldo > 0:
            return 'Ascensão'
        else:
            return 'Declínio'

    df1['Estado_Financeiro'] = df1.apply(classificar_estado_financeiro, axis=1)

    # Combinar maturidade e estado financeiro para a "Estado da Empresa"
    df1['Estado_da_Empresa'] = df1['Maturidade'] + ' em ' + df1['Estado_Financeiro']

    # Processamento da Base 2 para o relacionamento B2B
    df2_clean = df2.dropna(subset=['ID_PGTO', 'ID_RCBE'])
    
    # Calcular o número de transações recebidas e pagas por empresa
    relacionamento_recebido = df2_clean.groupby('ID_RCBE')['ID_PGTO'].count().reset_index(name='Transacoes_Recebidas')
    relacionamento_pago = df2_clean.groupby('ID_PGTO')['ID_RCBE'].count().reset_index(name='Transacoes_Pagas')
    
    # Unir os DataFrames para ter uma visão completa por CNPJ
    relacionamento = pd.merge(relacionamento_recebido, relacionamento_pago, left_on='ID_RCBE', right_on='ID_PGTO', how='outer')
    relacionamento = relacionamento.rename(columns={'ID_RCBE': 'ID_CNPJ'}).drop(columns='ID_PGTO')
    relacionamento.fillna(0, inplace=True)
    relacionamento['Total_Transacoes'] = relacionamento['Transacoes_Recebidas'] + relacionamento['Transacoes_Pagas']

    # Classificar o grau de relacionamento B2B
    def classificar_b2b(row):
        total = row['Total_Transacoes']
        if total > 50:
            return 'Muito Alto'
        elif total > 30:
            return 'Alto'
        elif total > 10:
            return 'Médio'
        elif total > 5:
            return 'Baixo'
        else:
            return 'Muito Baixo'

    relacionamento['Relacionamento_B2B'] = relacionamento.apply(classificar_b2b, axis=1)
    
    # Análise de dependência
    def analisar_dependencia(row):
        pgto = row['Transacoes_Pagas']
        rcbe = row['Transacoes_Recebidas']
        if rcbe > 3 * pgto:
            return 'Empresa dependente de outras'
        elif pgto > 3 * rcbe:
            return 'Outras dependem da empresa'
        else:
            return 'Relacionamento equilibrado'
    
    relacionamento['Tipo_Relacionamento_B2B'] = relacionamento.apply(analisar_dependencia, axis=1)

    # Unir as bases
    df_merged = pd.merge(df1, relacionamento, left_on='ID', right_on='ID_CNPJ', how='left')
    df_merged.fillna({'Total_Transacoes': 0, 'Relacionamento_B2B': 'Não Classificado'}, inplace=True)

    # Classificação do Risco para o Santander
    def classificar_risco(row):
        estado = row['Estado_da_Empresa']
        relacionamento = row['Relacionamento_B2B']
        saldo = row['VL_SLDO']
        faturamento = row['VL_FATU']
        
        risco_score = 0
        
        # Pontuação baseada no estado da empresa
        if 'Declínio' in estado:
            risco_score += 3
        elif 'Ascensão' in estado:
            risco_score -= 2
        
        # Pontuação baseada no saldo e faturamento
        if saldo < 0:
            risco_score += 2
        if faturamento < 500000:
            risco_score += 1

        # Pontuação baseada no relacionamento B2B
        if relacionamento in ['Muito Alto', 'Alto']:
            risco_score -= 1  # Estabilidade na rede B2B
        elif relacionamento in ['Muito Baixo', 'Baixo']:
            risco_score += 1
            
        # Classificação final
        if risco_score <= -1:
            return 'Muito Baixo'
        elif risco_score == 0:
            return 'Baixo'
        elif risco_score == 1:
            return 'Médio'
        elif risco_score == 2:
            return 'Alto'
        else:
            return 'Muito Alto'

    df_merged['Risco_Santander'] = df_merged.apply(classificar_risco, axis=1)

    # Sensibilizar empresas oportunas para crédito
    df_merged['Oportunidade_Credito'] = df_merged.apply(lambda row: 'Sim' if row['Estado_da_Empresa'] in ['Inicial em Ascensão', 'Madura em Ascensão'] and row['Risco_Santander'] in ['Baixo', 'Muito Baixo'] else 'Não', axis=1)

    return df_merged

# Título do aplicativo
st.title('Dashboard de Análise de Perfil de Empresas')
st.markdown("""
Este dashboard interativo permite analisar e classificar empresas com base em diversos critérios, como tempo de atividade, saúde financeira e relacionamento B2B, para avaliar o risco de crédito e identificar oportunidades para o Banco Santander.
""")

# Carregar e processar os dados
base1, base2 = load_data()

if base1 is not None and base2 is not None:
    df_final = process_data(base1, base2)

    # Filtros laterais
    st.sidebar.header('Filtros')
    
    cnae_options = ['Todos'] + sorted(df_final['DS_CNAE'].unique().tolist())
    selected_cnae = st.sidebar.selectbox('Filtrar por CNAE:', cnae_options)

    estado_options = ['Todos'] + sorted(df_final['Estado_da_Empresa'].unique().tolist())
    selected_estado = st.sidebar.selectbox('Filtrar por Estado da Empresa:', estado_options)
    
    b2b_options = ['Todos'] + sorted(df_final['Relacionamento_B2B'].unique().tolist())
    selected_b2b = st.sidebar.selectbox('Filtrar por Relacionamento B2B:', b2b_options)
    
    risco_options = ['Todos'] + sorted(df_final['Risco_Santander'].unique().tolist())
    selected_risco = st.sidebar.selectbox('Filtrar por Nível de Risco:', risco_options)
    
    oportunidade_options = ['Todos', 'Sim', 'Não']
    selected_oportunidade = st.sidebar.selectbox('Oportunidade de Crédito:', oportunidade_options)

    # Aplicar filtros
    filtered_df = df_final.copy()
    if selected_cnae != 'Todos':
        filtered_df = filtered_df[filtered_df['DS_CNAE'] == selected_cnae]
    if selected_estado != 'Todos':
        filtered_df = filtered_df[filtered_df['Estado_da_Empresa'] == selected_estado]
    if selected_b2b != 'Todos':
        filtered_df = filtered_df[filtered_df['Relacionamento_B2B'] == selected_b2b]
    if selected_risco != 'Todos':
        filtered_df = filtered_df[filtered_df['Risco_Santander'] == selected_risco]
    if selected_oportunidade != 'Todos':
        filtered_df = filtered_df[filtered_df['Oportunidade_Credito'] == selected_oportunidade]

    st.subheader('Tabela de Empresas Classificadas')
    st.write(f"Mostrando {len(filtered_df)} de {len(df_final)} empresas.")
    st.dataframe(filtered_df[['ID', 'Tempo_Atividade_Anos', 'Maturidade', 'DS_CNAE', 'VL_FATU', 'VL_SLDO', 
                              'Estado_da_Empresa', 'Relacionamento_B2B', 'Tipo_Relacionamento_B2B', 
                              'Risco_Santander', 'Oportunidade_Credito']], use_container_width=True)
    
    # Exemplo de empresas oportunas para crédito
    st.subheader('Empresas Oportunas para Crédito (Baixo Risco e em Ascensão)')
    oportunidade_df = filtered_df[filtered_df['Oportunidade_Credito'] == 'Sim']
    st.dataframe(oportunidade_df[['ID', 'Estado_da_Empresa', 'Risco_Santander', 'VL_FATU', 'VL_SLDO', 'DS_CNAE']], use_container_width=True)

    # Visualizações (gráficos)
    st.subheader('Análise Visual')
    
    col1, col2 = st.columns(2)
    with col1:
        st.write('**Distribuição de Empresas por Estado**')
        estado_counts = filtered_df['Estado_da_Empresa'].value_counts()
        st.bar_chart(estado_counts)

    with col2:
        st.write('**Distribuição de Empresas por Nível de Risco**')
        risco_counts = filtered_df['Risco_Santander'].value_counts()
        st.bar_chart(risco_counts)

    st.write('**Relação entre Faturamento e Saldo**')
    st.scatter_chart(filtered_df, x='VL_FATU', y='VL_SLDO', color='Risco_Santander')

    st.write('**Risco vs. Tipo de Relacionamento B2B**')
    b2b_risco_pivot = filtered_df.pivot_table(
        index='Risco_Santander',
        columns='Tipo_Relacionamento_B2B',
        values='ID',
        aggfunc='count',
        fill_value=0
    ).T
    st.bar_chart(b2b_risco_pivot)

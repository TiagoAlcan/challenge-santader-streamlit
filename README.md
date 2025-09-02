# 🏦 Dashboard de Análise de Risco de Crédito
### Este projeto consiste em um dashboard interativo construído com Streamlit para análise de perfil e risco de crédito de empresas. A aplicação utiliza dados anonimizados de faturamento, saldo, maturidade e transações B2B para gerar insights estratégicos, identificar oportunidades de crédito e analisar o risco na cadeia de valor de cada empresa.

## Stack de Tecnologia
### A aplicação foi desenvolvida utilizando as seguintes tecnologias:

- Linguagem: Python 3.x
- Biblioteca de Interface Web: Streamlit
- Manipulação de Dados: Pandas
- Visualização de Dados: Plotly Express

# 🚀 Como Rodar o Projeto Localmente
### Siga os passos abaixo para executar o dashboard em sua máquina.

### Pré-requisitos
- Python 3.8 ou superior instalado.
- pip (gerenciador de pacotes do Python).

1. Preparação do Ambiente
É uma boa prática criar um ambiente virtual para isolar as dependências do projeto.

# Crie um ambiente virtual (ex: .venv)
python -m venv .venv

# Ative o ambiente virtual (caso seja necessário)
## No Windows:
.venv\Scripts\activate
## No macOS/Linux:
source .venv/bin/activate

2. Instalação das Dependências
Com o ambiente ativado, instale as bibliotecas necessárias:

`pip install streamlit pandas plotly`

3. Arquivos de Dados
Certifique-se de que os seguintes arquivos CSV estejam na mesma pasta que o script analise_risco_app.py:

- Base1.csv: Contém dados cadastrais e financeiros das empresas.

- Base2.csv: Contém os dados de transações entre as empresas.

- Layout.csv: Arquivo descritivo (metadados) das outras bases.

4. Execução da Aplicação
Para iniciar o dashboard, execute o seguinte comando no seu terminal, a partir da pasta do projeto:

`streamlit run santander.py`

Após executar o comando, o Streamlit irá iniciar um servidor local e abrir o dashboard automaticamente no seu navegador padrão.

Funcionalidades do Dashboard
Filtros Interativos: Permite segmentar a base de empresas por setor (CNAE), perfil, nível de risco e oportunidade de crédito.

KPIs Dinâmicos: Métricas chave que se atualizam com base nos filtros aplicados.

Análise Visual: Gráficos detalhados sobre a saúde financeira, distribuição de risco, e relacionamentos B2B.

Mapa de Oportunidades: Um Treemap interativo que mostra a concentração de oportunidades de crédito por setor e perfil da empresa.

Análise da Cadeia de Valor: Ferramenta para selecionar uma empresa e analisar o risco financeiro de seus principais clientes e fornecedores.

Tabelas Paginadas: Visualização detalhada dos dados com sistema de paginação para melhor performance.

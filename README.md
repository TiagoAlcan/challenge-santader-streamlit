Claro\! Aqui está um documento `README.md` completo e bem estruturado para a documentação do seu projeto. Ele foi escrito em Markdown e inclui todas as seções essenciais, como visão geral, tecnologias, instalação e como executar o dashboard.

-----

# Dashboard de Risco e Oportunidades de Clientes PJ

## Visão Geral

Este projeto é um dashboard interativo construído com Streamlit para a análise de um portfólio de clientes Pessoa Jurídica (PJ). A ferramenta permite a visualização, filtragem e análise de dados financeiros e transacionais para identificar perfis de risco, dependências na cadeia de valor e oportunidades de negócio (crédito, investimentos, etc.).

O dashboard consolida informações de múltiplas fontes de dados para criar uma visão 360º de cada empresa e do portfólio como um todo.

### Principais Funcionalidades

  - **Visão Geral do Portfólio:** KPIs dinâmicos que resumem a seleção atual de empresas.
  - **Tabela Detalhada:** Uma tabela paginada e pesquisável com informações-chave de cada empresa.
  - **Análise da Cadeia de Valor:** Um mapa de rede interativo que exibe o risco dos principais clientes e fornecedores de uma empresa selecionada, destacando dependências críticas.
  - **Classificação Automática:** Algoritmos para classificar a saúde financeira, o nível de risco e o potencial de oportunidade de cada empresa.
  - **Análises Visuais:** Gráficos interativos para explorar a distribuição do portfólio por:
      - Saúde Financeira vs. Risco.
      - Perfil de Relacionamento B2B (Intensidade e Dependência).
      - Oportunidades de Crédito por Setor (CNAE).
      - Distribuição Geográfica e Risco Médio por Setor (requer dados adicionais).
  - **Filtragem Dinâmica:** Filtros na barra lateral para segmentar o portfólio por setor, perfil, nível de risco, oportunidade e localização.

## Tecnologias Utilizadas

  - **Linguagem:** Python 3.8+
  - **Framework Principal:** [Streamlit](https://streamlit.io/)
  - **Manipulação de Dados:** [Pandas](https://pandas.pydata.org/)
  - **Visualização de Dados:** [Plotly](https://plotly.com/python/)
  - **Renderização de Grafos:** [Graphviz](https://graphviz.org/)

## Pré-requisitos

Antes de iniciar, certifique-se de que você tem os seguintes softwares instalados em seu sistema:

1.  **Python 3.8 ou superior:** [Download Python](https://www.python.org/downloads/)

2.  **PIP** (gerenciador de pacotes do Python, geralmente instalado com o Python).

3.  **Graphviz (Software):** A biblioteca Python `graphviz` é apenas um *wrapper*. Você precisa instalar o software Graphviz no seu sistema operacional para que os grafos da cadeia de valor sejam renderizados.

      - **Windows:**
          - Baixe o instalador no [site oficial](https://graphviz.org/download/).
          - Durante a instalação, **certifique-se de marcar a opção "Add Graphviz to the system PATH"**.
      - **macOS (usando Homebrew):**
        ```bash
        brew install graphviz
        ```
      - **Linux (Debian/Ubuntu):**
        ```bash
        sudo apt-get update
        sudo apt-get install graphviz -y
        ```

## Instalação e Configuração

Siga os passos abaixo para configurar o ambiente e executar o projeto localmente.

**1. Clone o Repositório (ou crie um diretório para o projeto)**

Se estiver usando Git:

```bash
git clone https://seu-repositorio.com/dashboard-risco.git
cd dashboard-risco
```

Caso contrário, crie uma pasta e coloque o arquivo `.py` e os arquivos de dados dentro dela.

**2. Crie e Ative um Ambiente Virtual (Recomendado)**

Isso isola as dependências do projeto e evita conflitos com outros projetos Python.

```bash
# Criar o ambiente virtual
python -m venv venv

# Ativar o ambiente
# No Windows:
venv\Scripts\activate
# No macOS/Linux:
source venv/bin/activate
```

**3. Instale as Dependências Python**

Crie um arquivo chamado `requirements.txt` no diretório do projeto com o seguinte conteúdo:

```txt
streamlit
pandas
plotly
graphviz
```

Em seguida, instale todas as bibliotecas de uma vez com o comando:

```bash
pip install -r requirements.txt
```

## Arquivos de Dados

Para que o dashboard funcione corretamente, os seguintes arquivos CSV devem estar no mesmo diretório que o script Python:

#### Arquivos Essenciais

  - `Base1.csv`: Contém os dados cadastrais e financeiros de cada empresa.
      - Colunas esperadas: `ID` (CNPJ), `DS_CNAE`, `DT_ABRT`, `DT_REFE`, `VL_FATU`, `VL_SLDO`.
  - `Base2.csv`: Contém os dados transacionais entre as empresas.
      - Colunas esperadas: `ID_PGTO` (ID do pagador), `ID_RCBE` (ID do recebedor), `VL` (valor da transação).

#### Arquivos Opcionais (para Insights Adicionais)

O dashboard é capaz de funcionar sem estes arquivos, mas as análises geográficas e setoriais avançadas ficarão desabilitadas.

  - `Base3_Geografico.csv`: Mapeia cada empresa a sua localização.
      - Colunas esperadas: `ID`, `SG_UF`, `NM_MUNICIPIO`.
  - `Base4_Setorial.csv`: Fornece dados macroeconômicos por setor.
      - Colunas esperadas: `DS_CNAE`, `RISCO_SETORIAL` (ex: 'Alto', 'Médio', 'Baixo'), `TENDENCIA_CRESCIMENTO` (ex: 'Positiva', 'Neutra').

## Como Executar

Com o ambiente virtual ativado e as dependências instaladas, execute o seguinte comando no seu terminal (estando no diretório do projeto):

```bash
streamlit run nome_do_seu_script.py
```

*Substitua `nome_do_seu_script.py` pelo nome real do seu arquivo Python.*

Após executar o comando, o Streamlit abrirá uma nova aba no seu navegador com o dashboard em execução.

## Estrutura do Dashboard

  - **Barra Lateral Esquerda:** Contém todos os filtros que podem ser aplicados ao portfólio.
  - **Seção Superior:** Apresenta os principais KPIs (Indicadores-Chave de Desempenho) que refletem a seleção atual dos filtros.
  - **Tabela Detalhada:** Exibe os dados brutos das empresas selecionadas, com suporte para pesquisa e paginação.
  - **Análise de Cadeia de Valor:** Permite selecionar uma empresa e visualizar seu ecossistema de clientes e fornecedores.
  - **Abas de Análise Visual:** Agrupam diferentes gráficos para uma análise mais profunda do portfólio.

-----

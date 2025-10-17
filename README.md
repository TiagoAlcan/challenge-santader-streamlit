# Dashboard de Risco e Oportunidades de Clientes PJ

## Visão Geral

Dashboard em **Streamlit** para análise de portfólio PJ. Consolida dados financeiros e transacionais para classificar **saúde**, **risco** e **oportunidades** via **Regras (explicáveis)** e apoio textual por **LLM (simulado)**.

## Principais Funcionalidades

- **Visão Geral do Portfólio**: KPIs dinâmicos conforme filtros.
- **Tabela Detalhada**: busca por CNPJ, paginação, tiers (Ouro/Prata/Bronze).
- **Classificação Automática (Regras)**: Saúde Financeira, Nível de Risco, Oportunidade de Crédito.
- **Análises Visuais**: saúde/risco, B2B (intensidade/dependência), treemap de oportunidades, dispersão Faturamento×Saldo.
- **Insights de CNPJs**:
  - **Assistido (Regras)**:
    - **1 CNPJ**: visão detalhada com recomendações e B2B.
    - **2+ CNPJs**: comparação lado a lado com **parecer lógico do LLM (simulado) + Regras**.
  - **IA (LLM)**: análise diagnóstica textual por CNPJ (simulada).
- **Cadeia de Valor**: grafo (Graphviz) de clientes/fornecedores com cores por risco e ícones de dependência.

## Tecnologias

- **Linguagem:** Python 3.8+ [Download Python](https://www.python.org/downloads/)
- **Framework Principal:** [Streamlit](https://streamlit.io/)
- **Manipulação de Dados:** [Pandas](https://pandas.pydata.org/)
- **Visualização de Dados:** [Plotly](https://plotly.com/python/)
- **Renderização de Grafos:** [Graphviz](https://graphviz.org/)

## Repositório

```bash
git clone https://github.com/TiagoAlcan/challenge-santader-streamlit
cd challenge-santader-streamlit
```

## Instalação

```bash
# (opcional) ambiente virtual
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# dependências
pip install -r requirements.txt
```

**requirements.txt**

```txt
streamlit
pandas
numpy
plotly
graphviz
```

> O app já usa `use_container_width=True` (substitui `use_column_width`, depreciado).

## Graphviz (software)

- **Windows**: instale do site oficial e marque _Add Graphviz to PATH_
- **macOS (Homebrew)**:
  ```bash
  brew install graphviz
  ```
- **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt-get update && sudo apt-get install -y graphviz
  ```

## Dados

Coloque no diretório do app:

**Essenciais**

- `Base1.csv` — `ID`, `DS_CNAE`, `DT_ABRT`, `DT_REFE`, `VL_FATU`, `VL_SLDO`
- `Base2.csv` — `ID_PGTO`, `ID_RCBE`, `VL`

**Opcionais**

- `Base3_Geografico.csv` — `ID`, `SG_UF`, `NM_MUNICIPIO`
- `Base4_Setorial.csv` — `DS_CNAE`, `RISCO_SETORIAL`, `TENDENCIA_CRESCIMENTO`

## Execução

```bash
streamlit run nome_do_seu_script.py
```

_Substitua `nome_do_seu_script.py` pelo nome real do seu arquivo Python._

## Estrutura do App

- **Barra Lateral**: filtros e navegação.
- **KPIs**: indicadores chave por seleção.
- **Tabela Detalhada**: pesquisa por CNPJ + paginação.
- **Abas Visuais**: Saúde & Risco, Análise B2B, Oportunidades por Setor.
- **Insights de CNPJs**: Assistido (Regras + comparação com LLM simulado) e IA (LLM simulado).
- **Cadeia de Valor**: grafo de clientes/fornecedores.

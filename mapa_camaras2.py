import pandas as pd
import plotly.express as px
import streamlit as st
import requests
from io import BytesIO
import itertools

# ----------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------
st.set_page_config(page_title="Mapa Panorâmico de Sementes", layout="wide", page_icon="🌱")
st.title("Ocupação das Câmaras Frias")


# ----------------------------------------------------
# 2. CARREGAMENTO E LIMPEZA DOS DADOS
# ----------------------------------------------------
@st.cache_data(ttl=600)
def carregar_dados():
    # COLOQUE O SEU ID DO GOOGLE DRIVE AQUI (Apenas o código, sem o resto do link)
    arquivo_id = '1F_FT7Ygixc6ZBAqzZRy3l2iD7tNefFvM'
    url = f'https://docs.google.com/spreadsheets/d/{arquivo_id}/export?format=xlsx'

    try:
        resposta = requests.get(url)
        df = pd.read_excel(BytesIO(resposta.content), engine='openpyxl')
    except Exception as e:
        # Se falhar, tenta ler localmente (caso você esteja testando no computador)
        try:
            df = pd.read_excel('caixas.xlsx', engine='openpyxl')
        except:
            st.error("🚨 Não foi possível carregar os dados. Verifique o ID do Google Drive e as permissões.")
            st.stop()

    df.columns = df.columns.str.strip()
    if 'Endereco' in df.columns:
        df = df.rename(columns={'Endereco': 'Endereço'})

    df = df.dropna(subset=['Endereço'])
    df[['Câmara', 'Estante', 'Caixa']] = df['Endereço'].str.extract(r'([A-Z])\[(\d+)\]\[(\d+)\]')

    df = df.dropna(subset=['Câmara', 'Estante', 'Caixa'])
    df['Estante'] = df['Estante'].astype(int)
    df['Caixa'] = df['Caixa'].astype(int)

    # 🎯 MODIFICAÇÃO: Calcula a quantidade de amostras contando as repetições de cada endereço
    df['Amostras'] = df.groupby('Endereço')['Endereço'].transform('count')

    # Remove duplicadas de endereço para que o gráfico plote apenas um ponto por caixa
    df = df.drop_duplicates(subset=['Endereço'])

    return df


df_dados = carregar_dados()

# ----------------------------------------------------
# 3. INTERFACE LATERAL (FILTROS)
# ----------------------------------------------------
st.sidebar.header("📍 Filtros de Busca")

# Cria a lista de gêneros disponíveis (removendo vazios e ordenando)
generos_disponiveis = df_dados['Gênero'].dropna().unique().tolist()
generos_disponiveis.sort()
generos_disponiveis.insert(0, "Todos os Gêneros")  # Adiciona opção para ver tudo

# Filtro 1: Escolha do Gênero
genero_selecionado = st.sidebar.selectbox("1️⃣ Escolha o Gênero (Prioridade)", generos_disponiveis)

# Lógica inteligente para o Filtro 2: Câmara
if genero_selecionado != "Todos os Gêneros":
    # Isola apenas as linhas do gênero escolhido
    df_gen_isolado = df_dados[df_dados['Gênero'] == genero_selecionado]
    # Descobre em quais câmaras ele está presente
    camaras_com_genero = sorted(df_gen_isolado['Câmara'].unique())

    # Exibe resumo na tela principal
    st.success(
        f"🔎 O gênero **{genero_selecionado}** está presente em **{len(camaras_com_genero)} câmara(s)**: {', '.join(camaras_com_genero)}")

    with st.expander("Ver lista exata de localizações (Endereços)"):
        # Mostra a tabela formatada e limpa
        tabela_enderecos = df_gen_isolado[['Endereço', 'Câmara', 'Estante', 'Caixa']].sort_values(
            by=['Câmara', 'Estante', 'Caixa'])
        st.dataframe(tabela_enderecos, use_container_width=True, hide_index=True)
else:
    # Se "Todos os Gêneros" for selecionado, mostra todas as câmaras
    camaras_com_genero = sorted(df_dados['Câmara'].unique())
    st.markdown("Navegue pela visualização completa da câmara selecionada.")

# Se por acaso um gênero estiver cadastrado mas sem câmara válida
if not camaras_com_genero:
    st.warning("Nenhuma câmara encontrada com este gênero.")
    st.stop()

# Filtro 2: Escolha da Câmara (As opções dependem do Gênero escolhido)
camara_selecionada = st.sidebar.selectbox("2️⃣ Escolha a Câmara", camaras_com_genero)

# Filtramos os dados finais que vão para o gráfico baseado apenas na câmara escolhida
df_filtrado = df_dados[df_dados['Câmara'] == camara_selecionada]

# ----------------------------------------------------
# 4. CRIANDO O MOLDE PANORÂMICO
# ----------------------------------------------------
max_estantes = max(79, df_filtrado['Estante'].max() if not df_filtrado.empty else 79)
combinacoes = list(itertools.product(range(1, max_estantes + 1), range(1, 36)))
df_grid = pd.DataFrame(combinacoes, columns=['Estante', 'Caixa'])

# 🎯 MODIFICAÇÃO: Trazendo a coluna 'Amostras' para o cruzamento de dados (merge)
df_plot = pd.merge(df_grid, df_filtrado[['Estante', 'Caixa', 'Gênero', 'Amostras']], on=['Estante', 'Caixa'], how='left')
df_plot['Gênero'] = df_plot['Gênero'].fillna('Vazio (Livre)')

# Se a caixa estiver livre, define a quantidade de amostras como 0
df_plot['Amostras'] = df_plot['Amostras'].fillna(0).astype(int)

df_plot['Posição (Y)'] = 36 - df_plot['Caixa']
df_plot['Endereço Completo'] = f"{camara_selecionada}[" + df_plot['Estante'].apply(lambda x: f"{x:02d}") + "][" + \
                               df_plot['Caixa'].apply(lambda x: f"{x:02d}") + "]"

# ----------------------------------------------------
# 5. LÓGICA DE CORES (O "EFEITO HOLOFOTE")
# ----------------------------------------------------
if genero_selecionado != "Todos os Gêneros":
    # Se ele buscou um gênero, vamos destacar ele no mapa!
    def classificar_destaque(g):
        if g == 'Vazio (Livre)': return g
        if g == genero_selecionado: return '🎯 ' + g  # Coloca um emoji para destacar na legenda
        return 'Outros Gêneros'


    df_plot['Destaque'] = df_plot['Gênero'].apply(classificar_destaque)
    coluna_cor = 'Destaque'
    mapa_de_cores = {
        'Vazio (Livre)': '#f0f0f0',  # Cinza bem claro (fundo)
        'Outros Gêneros': '#c0c0c0',  # Cinza médio (ocupado, mas não é o que buscou)
        f'🎯 {genero_selecionado}': '#ff4b4b'  # Vermelho brilhante (O gênero buscado)
    }
else:
    # Se estiver vendo tudo, colore tudo normalmente
    coluna_cor = 'Gênero'
    mapa_de_cores = {'Vazio (Livre)': '#e8e8e8'}

# ----------------------------------------------------
# 6. DESENHANDO O GRÁFICO PANORÂMICO
# ----------------------------------------------------
st.subheader(f"🏢 Mapa da Câmara {camara_selecionada}")

fig = px.scatter(
    df_plot,
    x="Estante",
    y="Posição (Y)",
    color=coluna_cor,
    hover_name="Gênero",  # Ao passar o mouse, sempre mostra o nome verdadeiro do gênero!
    # 🎯 MODIFICAÇÃO: Incluída a linha '"Amostras": True' para mostrar a contagem gerada no balão
    hover_data={"Estante": False, "Posição (Y)": False, "Endereço Completo": True, "Amostras": True, "Caixa": False, coluna_cor: False},
    color_discrete_map=mapa_de_cores,
    height=750
)

fig.update_traces(marker=dict(symbol='square', size=13, line=dict(width=0.5, color='gray')))

valores_eixo_y = [36 - i for i in range(1, 36)]
textos_eixo_y = [str(i) for i in range(1, 36)]

fig.update_layout(
    xaxis=dict(title="<b>Número da Estante ➡️</b>", tickmode='linear', dtick=2, showgrid=False),
    yaxis=dict(title="<b>⬅️ Número da Caixa</b>", tickmode='array', tickvals=valores_eixo_y, ticktext=textos_eixo_y,
               showgrid=False),
    plot_bgcolor='white',
    legend_title_text='Legenda',
    margin=dict(l=20, r=20, t=30, b=20)
)

st.plotly_chart(fig, use_container_width=True)
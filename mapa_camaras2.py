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

    if 'Gênero' in df.columns:
        df['Gênero'] = df['Gênero'].astype(str).str.strip()

    # 🎯 MODIFICAÇÃO CIRÚRGICA: Lógica para mapear Caixas Mistas e listar os gêneros contidos
    # 1. Conta a quantidade de amostras total por caixa
    df['Amostras'] = df.groupby('Endereço')['Endereço'].transform('count')
    
    # 2. Agrupa e cria uma string combinando todos os gêneros únicos de cada caixa
    generos_por_endereco = df.groupby('Endereço')['Gênero'].transform(lambda x: ", ".join(sorted(x.unique())))
    
    # 3. Se houver mais de um gênero único no mesmo endereço, classifica como Misto
    df['Gênero_Original'] = df['Gênero'] # Salva o original para os filtros laterais funcionarem
    df['Gênero'] = df.groupby('Endereço')['Gênero'].transform(lambda x: "Misto (Vários Gêneros)" if x.nunique() > 1 else x)
    
    # 4. Guarda a lista detalhada de gêneros para exibir no hover do mouse
    df['Gêneros Contidos'] = generos_por_endereco

    # Remove duplicadas de endereço garantindo consistência para a plotagem do mapa único
    df = df.drop_duplicates(subset=['Endereço'])

    return df


df_dados = carregar_dados()

# ----------------------------------------------------
# 3. INTERFACE LATERAL (FILTROS)
# ----------------------------------------------------
st.sidebar.header("📍 Filtros de Busca")

# Cria a lista de gêneros disponíveis usando a coluna original (para manter os nomes reais na busca)
generos_disponiveis = df_dados['Gênero_Original'].dropna().unique().tolist()
if "Misto (Vários Gêneros)" in df_dados['Gênero'].unique():
    generos_disponiveis.append("Misto (Vários Gêneros)")
generos_disponiveis.sort()
generos_disponiveis.insert(0, "Todos os Gêneros")

# Filtro 1: Escolha do Gênero
genero_selecionado = st.sidebar.selectbox("1️⃣ Escolha o Gênero (Prioridade)", generos_disponiveis)

# Lógica inteligente para o Filtro 2: Câmara
if genero_selecionado != "Todos os Gêneros":
    # Isola as linhas usando o gênero original ou a marcação de Misto
    if genero_selecionado == "Misto (Vários Gêneros)":
        df_gen_isolado = df_dados[df_dados['Gênero'] == "Misto (Vários Gêneros)"]
    else:
        df_gen_isolado = df_dados[df_dados['Gênero_Original'] == genero_selecionado]
        
    camaras_com_genero = sorted(df_gen_isolado['Câmara'].unique())

    st.success(
        f"🔎 O grupo/gênero **{genero_selecionado}** está presente em **{len(camaras_com_genero)} câmara(s)**: {', '.join(camaras_com_genero)}")

    with st.expander("Ver lista exata de localizações (Endereços)"):
        tabela_enderecos = df_gen_isolado[['Endereço', 'Câmara', 'Estante', 'Caixa', 'Gêneros Contidos']].sort_values(
            by=['Câmara', 'Estante', 'Caixa'])
        st.dataframe(tabela_enderecos, use_container_width=True, hide_index=True)
else:
    camaras_com_genero = sorted(df_dados['Câmara'].unique())
    st.markdown("Navegue pela visualização completa da câmara selecionada.")

if not camaras_com_genero:
    st.warning("Nenhuma câmara encontrada com este gênero.")
    st.stop()

# Filtro 2: Escolha da Câmara
camara_selecionada = st.sidebar.selectbox("2️⃣ Escolha a Câmara", camaras_com_genero)

df_filtrado = df_dados[df_dados['Câmara'] == camara_selecionada]

# ----------------------------------------------------
# 4. CRIANDO O MOLDE PANORÂMICO
# ----------------------------------------------------
max_estantes = max(79, df_filtrado['Estante'].max() if not df_filtrado.empty else 79)
combinacoes = list(itertools.product(range(1, max_estantes + 1), range(1, 36)))
df_grid = pd.DataFrame(combinacoes, columns=['Estante', 'Caixa'])

# Trazendo as novas colunas estruturadas para o cruzamento de dados (merge)
df_plot = pd.merge(df_grid, df_filtrado[['Estante', 'Caixa', 'Gênero', 'Amostras', 'Gêneros Contidos']], on=['Estante', 'Caixa'], how='left')
df_plot['Gênero'] = df_plot['Gênero'].fillna('Vazio (Livre)')
df_plot['Gêneros Contidos'] = df_plot['Gêneros Contidos'].fillna('Nenhum (Livre)')
df_plot['Amostras'] = df_plot['Amostras'].fillna(0).astype(int)

df_plot['Posição (Y)'] = 36 - df_plot['Caixa']
df_plot['Endereço Completo'] = f"{camara_selecionada}[" + df_plot['Estante'].apply(lambda x: f"{x:02d}") + "][" + \
                               df_plot['Caixa'].apply(lambda x: f"{x:02d}") + "]"

# ----------------------------------------------------
# 5. LÓGICA DE CORES (O "EFEITO HOLOFOTE")
# ----------------------------------------------------
if genero_selecionado != "Todos os Gêneros":
    def classificar_destaque(g):
        if g == 'Vazio (Livre)': return g
        if g == genero_selecionado: return '🎯 ' + g
        return 'Outros Gêneros'

    df_plot['Destaque'] = df_plot['Gênero'].apply(classificar_destaque)
    coluna_cor = 'Destaque'
    mapa_de_cores = {
        'Vazio (Livre)': '#f0f0f0',
        'Outros Gêneros': '#c0c0c0',
        f'🎯 {genero_selecionado}': '#ff4b4b'
    }
else:
    coluna_cor = 'Gênero'
    mapa_de_cores = {'Vazio (Livre)': '#e8e8e8'}
    # 🎯 Se houver caixas mistas na visão geral, garante uma cor de destaque para elas (ex: roxo escuro)
    if "Misto (Vários Gêneros)" in df_plot['Gênero'].unique():
        mapa_de_cores["Misto (Vários Gêneros)"] = "#8e44ad"

# ----------------------------------------------------
# 6. DESENHANDO O GRÁFICO PANORÂMICO
# ----------------------------------------------------
st.subheader(f"🏢 Mapa da Câmara {camara_selecionada}")

fig = px.scatter(
    df_plot,
    x="Estante",
    y="Posição (Y)",
    color=coluna_cor,
    hover_name="Gênero",  
    # 🎯 ADICIONADO NO HOVER: Mostra a lista exata dos 'Gêneros Contidos' dentro daquela caixa mista
    hover_data={
        "Estante": False, 
        "Posição (Y)": False, 
        "Endereço Completo": True, 
        "Amostras": True, 
        "Gêneros Contidos": True, 
        "Caixa": False, 
        coluna_cor: False
    },
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

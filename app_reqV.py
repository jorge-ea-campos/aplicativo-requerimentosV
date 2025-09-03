import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(
    page_title="Sistema de Conferência de Requerimentos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado ---
st.markdown("""
<style>
    /* Estilo do cabeçalho principal */
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #1f77b4;
        margin-bottom: 2rem;
    }
    /* Estilo dos cartões de métricas */
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# --- Funções de Processamento de Dados ---

def load_data(uploaded_file):
    """Tenta ler um arquivo como Excel e, se falhar, tenta como CSV."""
    try:
        df = pd.read_excel(uploaded_file)
        return df
    except Exception:
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file)
            return df
        except Exception:
            st.error(f"Falha ao ler o arquivo '{uploaded_file.name}'. Verifique se o formato é Excel (.xlsx) ou CSV (.csv).")
            return None

def find_and_rename_nusp_column(df):
    """Encontra e renomeia colunas padrão para facilitar o processamento."""
    rename_map = {
        'nusp': ['nusp', 'numero usp', 'número usp', 'n° usp', 'n usp'],
        'problema': ['problema'],
        'Nome completo': ['nome completo'],
        'parecer_sg': ['parecer do serviço de graduação', 'parecer serviço de graduação'],
        'obs_sg': ['observação do sg', 'observacao sg', 'observação sg'],
        'link_requerimento': ['links pedidos requerimento'],
        'link_plano_estudos': ['link plano de estudos'],
        'link_plano_presenca': ['link plano de presença']
    }

    actual_renames = {}
    for col in df.columns:
        normalized_col = str(col).lower().strip()
        for standard_name, variations in rename_map.items():
            if normalized_col in variations:
                actual_renames[col] = standard_name
                break
    
    if actual_renames:
        df.rename(columns=actual_renames, inplace=True)

    if 'nusp' not in df.columns:
        raise ValueError(f"Coluna de Número USP não encontrada. Colunas disponíveis: {', '.join(df.columns.tolist())}")
    
    return df


def validate_dataframes(df_consolidado, df_requerimentos):
    """Valida se os dataframes contêm as colunas necessárias."""
    required_cols_consolidado = ['nusp', 'disciplina', 'Ano', 'Semestre', 'problema', 'parecer']
    required_cols_requerimentos = ['nusp', 'Nome completo', 'problema']
    
    missing_consolidado = [col for col in required_cols_consolidado if col not in df_consolidado.columns]
    missing_requerimentos = [col for col in required_cols_requerimentos if col not in df_requerimentos.columns]
    
    errors = []
    if missing_consolidado: errors.append(f"Arquivo consolidado: colunas faltando - {', '.join(missing_consolidado)}")
    if missing_requerimentos: errors.append(f"Arquivo requerimentos: colunas faltando - {', '.join(missing_requerimentos)}")
    if errors: raise ValueError("\n".join(errors))

def preprocess_data(df, file_name):
    """Converte NUSP para numérico e remove nulos."""
    df["nusp"] = pd.to_numeric(df["nusp"], errors='coerce')
    nulos_antes = df["nusp"].isna().sum()
    df.dropna(subset=["nusp"], inplace=True)
    if nulos_antes > 0:
        st.warning(f"⚠️ Removidos {nulos_antes} registros com NUSP inválido do arquivo '{file_name}'")
    df["nusp"] = df["nusp"].astype(int)
    return df

# --- Funções de Formatação e Exportação ---

def format_parecer(parecer):
    """Formata o parecer para exibição com ícones."""
    if pd.isna(parecer): return "📝 Pendente"
    parecer_str = str(parecer).lower()
    if "negado" in parecer_str or "indeferido" in parecer_str: return f"❌ {parecer}"
    if "aprovado" in parecer_str: return f"✅ {parecer}"
    return f"📝 {parecer}"

def format_problem_type(problem):
    """Formata o tipo de problema para exibição com ícones."""
    if pd.isna(problem): return "⚪ Não especificado"
    problem = str(problem).upper()
    if problem == "QR": return "🔴 Quebra de Requisito"
    if problem == "CH": return "🟡 Conflito de Horário"
    return f"⚪ {problem}"

@st.cache_data
def to_excel(df):
    """Converte um DataFrame para um arquivo Excel em memória."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
        workbook = writer.book
        worksheet = writer.sheets['Relatorio']
        header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BD', 'border': 1})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        for i, col in enumerate(df.columns):
            column_width = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
            worksheet.set_column(i, i, min(column_width, 50))
    return output.getvalue()

def download_button(df, file_name_prefix, export_format):
    """Gera um botão de download para um DataFrame."""
    file_name = f"{file_name_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if export_format == "Excel":
        data = to_excel(df)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        st.download_button("📥 Baixar como Excel", data, f"{file_name}.xlsx", mime)
    else:
        data = df.to_csv(index=False).encode('utf-8')
        mime = "text/csv"
        st.download_button("📥 Baixar como CSV", data, f"{file_name}.csv", mime)

# --- Funções de Exibição (Componentes da UI) ---

def display_overview(df_requerimentos, alunos_com_historico, df_novos):
    """Exibe as métricas principais e gráficos na aba 'Visão Geral'."""
    st.markdown("### 📊 Métricas Principais")
    
    total_req = len(df_requerimentos)
    alunos_unicos_com_hist = alunos_com_historico["nusp"].nunique()
    total_alunos_req = df_requerimentos["nusp"].nunique()
    percentual_historico = (alunos_unicos_com_hist / total_alunos_req * 100) if total_alunos_req > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Requerimentos", total_req, help="Total de pedidos no semestre atual")
    with col2:
        st.metric("Alunos com Histórico", alunos_unicos_com_hist, f"{percentual_historico:.1f}% do total", help="Alunos que já fizeram pedidos anteriormente")
    with col3:
        st.metric("Alunos Novos", df_novos['nusp'].nunique(), help="Alunos fazendo requerimento pela primeira vez")

    st.markdown("---")

    if not alunos_com_historico.empty:
        st.markdown("### 📈 Análise Gráfica dos Alunos com Histórico")
        
        pareceres = alunos_com_historico['parecer_historico'].str.lower()
        aprovados = pareceres.str.contains('aprovado', na=False) & ~pareceres.str.contains('indeferido|negado', na=False)
        negados = pareceres.str.contains('indeferido|negado', na=False)
        taxa_aprovacao = (aprovados.sum() / (aprovados.sum() + negados.sum()) * 100) if (aprovados.sum() + negados.sum()) > 0 else 0
        total_qr = (alunos_com_historico["problema_historico"].str.upper() == "QR").sum()
        total_ch = (alunos_com_historico["problema_historico"].str.upper() == "CH").sum()
        
        col_metric1, col_metric2, col_metric3 = st.columns(3)
        with col_metric1: st.metric("Quebras de Requisito (Hist.)", total_qr)
        with col_metric2: st.metric("Conflitos de Horário (Hist.)", total_ch)
        with col_metric3: st.metric("Taxa de Aprovação (Hist.)", f"{taxa_aprovacao:.1f}%")

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("##### 📚 Top 5 Disciplinas com Histórico")
            top_disciplinas = alunos_com_historico['disciplina_historico'].value_counts().nlargest(5)
            if not top_disciplinas.empty:
                fig = px.bar(top_disciplinas, x=top_disciplinas.values, y=top_disciplinas.index, orientation='h', labels={'x': 'Nº de Pedidos', 'y': 'Disciplina'}, text=top_disciplinas.values)
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
        
        with col_chart2:
            st.markdown("##### 🗓️ Pedidos por Período")
            if 'Ano_historico' in alunos_com_historico.columns and 'Semestre_historico' in alunos_com_historico.columns:
                alunos_com_historico['periodo'] = alunos_com_historico['Ano_historico'].astype(str) + '/' + alunos_com_historico['Semestre_historico'].astype(str)
                dist_temporal = alunos_com_historico['periodo'].value_counts().sort_index()
                if not dist_temporal.empty:
                    fig2 = px.line(dist_temporal, x=dist_temporal.index, y=dist_temporal.values, labels={'x': 'Período', 'y': 'Nº de Pedidos'}, markers=True)
                    st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Não há dados históricos para gerar gráficos.")

def display_students_with_history(alunos_com_historico, export_format):
    """Exibe a lista filtrável de alunos com histórico e seus detalhes."""
    if alunos_com_historico.empty:
        st.success("✅ Nenhum aluno do semestre atual foi encontrado no histórico de pedidos.")
        return

    st.markdown("### 🔍 Filtrar e Pesquisar Alunos com Histórico")
    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("Pesquisar por Nome ou NUSP", placeholder="Digite para buscar...", key="search_hist")
    with col2:
        problem_types = ['Todos'] + sorted(alunos_com_historico['problema_atual'].dropna().unique().tolist())
        problem_filter = st.selectbox("Filtrar por Problema Atual", options=problem_types)

    df_filtered = alunos_com_historico.copy()
    if search_query:
        df_filtered = df_filtered[
            df_filtered['Nome completo'].str.lower().str.contains(search_query.lower()) |
            df_filtered['nusp'].astype(str).str.contains(search_query)
        ]
    if problem_filter != 'Todos':
        df_filtered = df_filtered[df_filtered['problema_atual'] == problem_filter]

    st.markdown("---")
    st.info(f"Exibindo {df_filtered['nusp'].nunique()} de {alunos_com_historico['nusp'].nunique()} alunos. Clique no nome para ver os detalhes.")

    alunos_unicos = df_filtered[['nusp', 'Nome completo']].drop_duplicates().sort_values('Nome completo')
    for _, aluno in alunos_unicos.iterrows():
        with st.expander(f"👤 {aluno['Nome completo']} (NUSP: {aluno['nusp']})"):
            historico_aluno = df_filtered[df_filtered['nusp'] == aluno['nusp']].copy()
            
            st.write("##### 📌 Requerimento(s) no Semestre Atual:")
            req_atual_cols = ['problema_atual']
            if 'parecer_sg_atual' in historico_aluno.columns: req_atual_cols.append('parecer_sg_atual')
            if 'obs_sg_atual' in historico_aluno.columns: req_atual_cols.append('obs_sg_atual')
            if 'link_requerimento_atual' in historico_aluno.columns: req_atual_cols.append('link_requerimento_atual')
            if 'link_plano_estudos_atual' in historico_aluno.columns: req_atual_cols.append('link_plano_estudos_atual')
            if 'link_plano_presenca_atual' in historico_aluno.columns: req_atual_cols.append('link_plano_presenca_atual')

            requerimentos_atuais = historico_aluno[req_atual_cols].drop_duplicates().fillna('')
            requerimentos_atuais.rename(columns={
                'problema_atual': 'Problema',
                'parecer_sg_atual': 'Parecer SG',
                'obs_sg_atual': 'Observação SG',
                'link_requerimento_atual': 'Link Requerimento',
                'link_plano_estudos_atual': 'Link Plano de Estudos',
                'link_plano_presenca_atual': 'Link Plano de Presença'
            }, inplace=True)
            
            column_config = {
                "Link Requerimento": st.column_config.LinkColumn("Requerimento", display_text="Abrir"),
                "Link Plano de Estudos": st.column_config.LinkColumn("Plano de Estudos", display_text="Abrir"),
                "Link Plano de Presença": st.column_config.LinkColumn("Plano de Presença", display_text="Abrir"),
            }
            final_config = {k: v for k, v in column_config.items() if k in requerimentos_atuais.columns}
            st.dataframe(requerimentos_atuais, hide_index=True, use_container_width=True, column_config=final_config)
            st.write("---")

            st.write("##### 📜 Histórico Completo de Pedidos:")
            historico_aluno['problema_formatado'] = historico_aluno['problema_historico'].apply(format_problem_type)
            historico_aluno['parecer_formatado'] = historico_aluno['parecer_historico'].apply(format_parecer)
            cols_hist = ['disciplina_historico', 'Ano_historico', 'Semestre_historico', 'problema_formatado', 'parecer_formatado']
            st.dataframe(historico_aluno[cols_hist].rename(columns=lambda c: c.replace('_historico', '').replace('_formatado','')).reset_index(drop=True), use_container_width=True)

    st.markdown("---")
    st.markdown("### 📥 Exportar Relatório de Alunos com Histórico")
    download_button(df_filtered, "relatorio_com_historico", export_format)

def display_new_students(df_novos, export_format):
    """Exibe a lista de alunos sem histórico de pedidos."""
    if df_novos.empty:
        st.info("✅ Todos os alunos do semestre atual já possuem algum histórico de pedidos.")
        return

    st.markdown(f"### ✨ Encontrados {len(df_novos['nusp'].unique())} alunos fazendo requerimento pela primeira vez")
    
    display_cols = ['nusp', 'Nome completo', 'problema_atual']
    if 'parecer_sg_atual' in df_novos.columns: display_cols.append('parecer_sg_atual')
    if 'obs_sg_atual' in df_novos.columns: display_cols.append('obs_sg_atual')
    if 'link_requerimento_atual' in df_novos.columns: display_cols.append('link_requerimento_atual')
    if 'link_plano_estudos_atual' in df_novos.columns: display_cols.append('link_plano_estudos_atual')
    if 'link_plano_presenca_atual' in df_novos.columns: display_cols.append('link_plano_presenca_atual')
    
    df_display = df_novos[display_cols].drop_duplicates().fillna('')
    df_display.rename(columns={
        'problema_atual': 'Problema Atual',
        'parecer_sg_atual': 'Parecer SG',
        'obs_sg_atual': 'Observação SG',
        'link_requerimento_atual': 'Link Requerimento',
        'link_plano_estudos_atual': 'Link Plano de Estudos',
        'link_plano_presenca_atual': 'Link Plano de Presença'
    }, inplace=True)
    
    column_config = {
        "Link Requerimento": st.column_config.LinkColumn("Requerimento", display_text="Abrir"),
        "Link Plano de Estudos": st.column_config.LinkColumn("Plano de Estudos", display_text="Abrir"),
        "Link Plano de Presença": st.column_config.LinkColumn("Plano de Presença", display_text="Abrir"),
    }
    final_config = {k: v for k, v in column_config.items() if k in df_display.columns}
    st.dataframe(df_display, hide_index=True, use_container_width=True, column_config=final_config)
    
    st.markdown("---")
    st.markdown("### 📥 Exportar Relatório de Alunos Novos")
    download_button(df_novos, "relatorio_alunos_novos", export_format)


# --- Função Principal da Aplicação ---
def run_app():
    st.markdown('<h1 class="main-header">📋 Sistema de Conferência de Requerimentos de Matrícula</h1>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("📁 Upload de Arquivos")
        st.markdown("---")
        file_consolidado = st.file_uploader("**Histórico de Pedidos (consolidado)**", type=["xlsx", "csv"])
        file_requerimentos = st.file_uploader("**Pedidos do Semestre Atual (requerimentos)**", type=["xlsx", "csv"])
        st.markdown("---")
        st.info("💡 **Dica:** Os arquivos devem conter colunas com 'NUSP', 'problema', e outras conforme o modelo.")
        with st.expander("⚙️ Configurações Avançadas"):
            show_debug = st.checkbox("Mostrar informações de debug", value=False)
            export_format = st.selectbox("Formato de exportação", ["Excel", "CSV"])

    if not (file_consolidado and file_requerimentos):
        st.markdown("### 🚀 Bem-vindo! Para começar, faça o upload dos dois arquivos na barra lateral.")
        with st.expander("📋 Estrutura esperada dos arquivos"):
            st.markdown("""
            - **Arquivo Consolidado:** `nusp`, `disciplina`, `Ano`, `Semestre`, `problema`, `parecer`
            - **Arquivo de Requerimentos:** `nusp`, `Nome completo`, `problema`
            - **(Opcional em Requerimentos):** `Parecer do serviço de graduação`, `Observação SG`, `Links Pedidos Requerimento`, `Link Plano de estudos`, `link plano de presença`
            """)
        return

    try:
        with st.spinner("Processando arquivos... Por favor, aguarde."):
            df_consolidado = load_data(file_consolidado)
            df_requerimentos = load_data(file_requerimentos)

            if df_consolidado is None or df_requerimentos is None: st.stop()
            
            df_consolidado = find_and_rename_nusp_column(df_consolidado)
            df_requerimentos = find_and_rename_nusp_column(df_requerimentos)
            
            if show_debug:
                with st.expander("🔍 Debug - Colunas após renomear"):
                    st.write("**Consolidado:**", df_consolidado.columns.tolist())
                    st.write("**Requerimentos:**", df_requerimentos.columns.tolist())
            
            validate_dataframes(df_consolidado, df_requerimentos)

            if 'Nome completo' in df_consolidado.columns:
                df_consolidado = df_consolidado.drop(columns=['Nome completo'])
            
            df_consolidado = preprocess_data(df_consolidado, file_consolidado.name)
            df_requerimentos = preprocess_data(df_requerimentos, file_requerimentos.name)

            cols_to_rename_hist = {c: f"{c}_historico" for c in ['disciplina', 'Ano', 'Semestre', 'problema', 'parecer']}
            df_consolidado.rename(columns=cols_to_rename_hist, inplace=True)
            
            req_rename_map = {'problema': 'problema_atual'}
            if 'parecer_sg' in df_requerimentos.columns: req_rename_map['parecer_sg'] = 'parecer_sg_atual'
            if 'obs_sg' in df_requerimentos.columns: req_rename_map['obs_sg'] = 'obs_sg_atual'
            if 'link_requerimento' in df_requerimentos.columns: req_rename_map['link_requerimento'] = 'link_requerimento_atual'
            if 'link_plano_estudos' in df_requerimentos.columns: req_rename_map['link_plano_estudos'] = 'link_plano_estudos_atual'
            if 'link_plano_presenca' in df_requerimentos.columns: req_rename_map['link_plano_presenca'] = 'link_plano_presenca_atual'
            df_requerimentos.rename(columns=req_rename_map, inplace=True)
            
            alunos_com_historico = df_requerimentos.merge(df_consolidado, on="nusp", how="inner")
            nusps_com_historico = set(alunos_com_historico['nusp'])
            df_novos = df_requerimentos[~df_requerimentos['nusp'].isin(nusps_com_historico)]

        tab_overview, tab_with_history, tab_new_students = st.tabs([
            f"📊 Visão Geral ({df_requerimentos['nusp'].nunique()} Alunos)",
            f"👤 Alunos com Histórico ({len(nusps_com_historico)})",
            f"✨ Alunos Novos ({df_novos['nusp'].nunique()})"
        ])

        with tab_overview:
            display_overview(df_requerimentos, alunos_com_historico, df_novos)
        with tab_with_history:
            display_students_with_history(alunos_com_historico, export_format)
        with tab_new_students:
            display_new_students(df_novos, export_format)

    except ValueError as e:
        st.error(f"❌ **Erro de Validação:**\n\n{e}\n\nPor favor, verifique a estrutura dos seus arquivos.")
    except Exception as e:
        st.error(f"❌ **Ocorreu um erro inesperado:**\n\n{e}\n\nVerifique o formato dos arquivos.")
        if show_debug: st.exception(e)

# --- Ponto de Entrada e Autenticação ---
def login_form():
    """Exibe o formulário de login e gerencia o estado da sessão."""
    st.title("🔒 Acesso Restrito")
    st.write("Por favor, insira a senha para acessar o sistema.")
    
    try:
        correct_password = st.secrets["passwords"]["senha_mestra"]
    except (AttributeError, KeyError):
        correct_password = "admin" 
        st.warning("Usando senha padrão. Para produção, configure a senha via st.secrets.")

    with st.form("login_form"):
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

        if submitted:
            if password == correct_password:
                st.session_state["password_correct"] = True
                st.rerun() 
            else:
                st.error("Senha incorreta. Tente novamente.")

# --- Lógica Principal ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    login_form()
else:
    run_app()


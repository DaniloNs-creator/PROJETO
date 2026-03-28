import streamlit as st
import pandas as pd
import sqlite3
import os
import time

# Configuração da página para ocupar toda a tela
st.set_page_config(page_title="Gestor de Dados BI", layout="wide")

# Nome do arquivo do banco de dados (será criado na mesma pasta do app)
DB_NAME = "banco_de_dados_bi.sqlite"

def get_db_connection():
    """Cria a conexão com o SQLite e aplica otimizações de superprocessamento."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Ativa o modo WAL (Write-Ahead Logging) para concorrência e velocidade
    cursor.execute("PRAGMA journal_mode = WAL;")
    # Otimiza a sincronização com o disco para gravações mais rápidas
    cursor.execute("PRAGMA synchronous = NORMAL;")
    # Aumenta o cache em memória (aprox. 64MB)
    cursor.execute("PRAGMA cache_size = -64000;")
    return conn

def process_and_save_excel(uploaded_file, table_name):
    """Lê o arquivo Excel gigante e salva no SQLite em lotes."""
    try:
        conn = get_db_connection()
        
        # Lendo o Excel usando o motor 'calamine' (Extremamente rápido para arquivos grandes)
        st.info("Lendo a planilha (isso pode levar alguns instantes dependendo do tamanho)...")
        start_time = time.time()
        
        # pyarrow como backend de dados economiza muita RAM
        df = pd.read_excel(
            uploaded_file, 
            engine="calamine", 
            dtype_backend="pyarrow"
        )
        
        read_time = time.time() - start_time
        st.success(f"Planilha lida em {read_time:.2f} segundos. Linhas totais: {len(df)}")
        
        # Salvando no SQLite em blocos (chunks) para não estourar a memória
        st.info("Gravando no banco de dados SQLite...")
        start_write = time.time()
        
        df.to_sql(
            name=table_name, 
            con=conn, 
            if_exists="append", # Anexa aos dados existentes; mude para 'replace' se quiser substituir
            index=False,
            chunksize=15000 # Grava de 15 mil em 15 mil linhas
        )
        
        write_time = time.time() - start_write
        conn.close()
        
        st.success(f"Dados salvos com sucesso na tabela '{table_name}' em {write_time:.2f} segundos!")
        return True
        
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return False

# ==========================================
# INTERFACE DO USUÁRIO (STREAMLIT)
# ==========================================

st.title("🚀 Pipeline de Dados: Excel para SQLite")
st.markdown("Faça o upload de planilhas pesadas para armazenamento de longo prazo e integração futura com o Power BI.")

# Área de Upload
uploaded_file = st.file_uploader("Selecione sua planilha Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # Pega o nome do arquivo sem a extensão para usar como sugestão de nome da tabela
    default_table_name = os.path.splitext(uploaded_file.name)[0].replace(" ", "_").lower()
    
    col1, col2 = st.columns(2)
    with col1:
        table_name = st.text_input("Nome da tabela no banco de dados:", value=default_table_name)
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True) # Espaçamento
        if st.button("Processar e Salvar no Banco", type="primary"):
            with st.spinner("Processamento em supercapacidade ativado. Aguarde..."):
                process_and_save_excel(uploaded_file, table_name)

st.divider()

# Área de Administração do Banco
st.subheader("📊 Resumo do Banco de Dados")
if os.path.exists(DB_NAME):
    try:
        conn = get_db_connection()
        # Consulta para descobrir quais tabelas existem e quantas linhas têm
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
        
        if not tables.empty:
            st.write("Tabelas armazenadas atualmente:")
            for index, row in tables.iterrows():
                t_name = row['name']
                count_df = pd.read_sql_query(f"SELECT COUNT(*) as qtd FROM {t_name}", conn)
                qtd_linhas = count_df['qtd'][0]
                st.markdown(f"- **{t_name}**: `{qtd_linhas:,}` linhas cadastradas.")
        else:
            st.write("O banco existe, mas ainda não possui tabelas.")
        conn.close()
    except Exception as e:
        st.error("Erro ao ler o banco de dados.")
else:
    st.info("O banco de dados será criado automaticamente no primeiro upload.")

import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import random
from typing import List, Tuple, Optional, Dict, Any
import io
import contextlib
import chardet
from io import BytesIO
import base64
import time
import xml.etree.ElementTree as ET
import os
import hashlib
import xml.dom.minidom
import traceback
from pathlib import Path
import numpy as np
import fitz  # PyMuPDF
import pdfplumber
import re
from lxml import etree
import tempfile
import logging
import gc

# ==============================================================================
# CONFIGURAÇÃO AUTOMÁTICA DO SERVIDOR STREAMLIT (Para PDFs gigantes)
# ==============================================================================
def setup_streamlit_config():
    """Cria o config.toml automaticamente para liberar uploads pesados."""
    try:
        os.makedirs(".streamlit", exist_ok=True)
        config_path = os.path.join(".streamlit", "config.toml")
        if not os.path.exists(config_path):
            with open(config_path, "w", encoding="utf-8") as f:
                f.write("[server]\n")
                f.write("maxUploadSize = 1000\n")
                f.write("maxMessageSize = 1000\n")
    except Exception as e:
        pass

setup_streamlit_config()

# ==============================================================================
# CONFIGURAÇÃO INICIAL
# ==============================================================================
st.set_page_config(
    page_title="Sistema de Processamento Unificado 2026",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Namespaces para CT-e
CTE_NAMESPACES = {
    'cte': 'http://www.portalfiscal.inf.br/cte'
}

# Inicialização do estado da sessão
if 'selected_xml' not in st.session_state:
    st.session_state.selected_xml = None
if 'cte_data' not in st.session_state:
    st.session_state.cte_data = None
if "parsed_duimp" not in st.session_state:
    st.session_state["parsed_duimp"] = None
if "parsed_sigraweb" not in st.session_state:
    st.session_state["parsed_sigraweb"] = None
if "merged_df" not in st.session_state:
    st.session_state["merged_df"] = None

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# ANIMAÇÕES DE CARREGAMENTO
# ==============================================================================
def show_loading_animation(message="Processando..."):
    with st.spinner(message):
        progress_bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)
        progress_bar.empty()

def show_processing_animation(message="Analisando dados..."):
    placeholder = st.empty()
    with placeholder.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(f"⏳ {message}")
            spinner_placeholder = st.empty()
            spinner_chars = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
            for i in range(20):
                spinner_placeholder.markdown(
                    f"<div style='text-align: center; font-size: 24px;'>{spinner_chars[i % 8]}</div>",
                    unsafe_allow_html=True
                )
                time.sleep(0.1)
    placeholder.empty()

def show_success_animation(message="Concluído!"):
    success_placeholder = st.empty()
    with success_placeholder.container():
        st.success(f"✅ {message}")
        time.sleep(1.5)
    success_placeholder.empty()

# ==============================================================================
# CSS E CONFIGURAÇÃO DE ESTILO
# ==============================================================================
def load_css():
    st.markdown("""
    <style>
        .cover-container {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ed 100%);
            padding: 3rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            text-align: center;
        }
        .cover-logo {
            max-width: 300px;
            margin-bottom: 1.5rem;
        }
        .cover-title {
            font-size: 2.8rem;
            font-weight: 800;
            margin-bottom: 1rem;
            background: linear-gradient(90deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .cover-subtitle {
            font-size: 1.2rem;
            color: #7f8c8d;
            margin-bottom: 0;
        }
        .header {
            font-size: 1.8rem;
            font-weight: 700;
            margin: 1.5rem 0 1rem 0;
            padding-left: 10px;
            border-left: 5px solid #2c3e50;
        }
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            padding: 1.8rem;
            margin-bottom: 1.8rem;
        }
        .stButton>button {
            width: 100%;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .spinner {
            animation: spin 2s linear infinite;
            display: inline-block;
            font-size: 24px;
        }
        .main-header {
            font-size: 2.5rem;
            color: #1E3A8A;
            font-weight: bold;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.5rem;
            color: #2563EB;
            margin-top: 1.5rem;
            border-bottom: 2px solid #E5E7EB;
        }
        .section-card {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
            border: 1px solid #E5E7EB;
        }
        .success-box {
            background-color: #d1fae5;
            color: #065f46;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .info-box {
            background-color: #dbeafe;
            color: #1e40af;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .warning-box {
            background-color: #fef3c7;
            color: #92400e;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .stButton>button {
            width: 100%;
            border-radius: 5px;
            font-weight: bold;
        }
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-left: 4px solid #3498db;
            margin-bottom: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# PARTE 1: PROCESSADOR DE ARQUIVOS TXT
# ==============================================================================
def processador_txt():
    st.title("📄 Processador de Arquivos TXT")
    st.markdown("""
    <div class="card">
        Remova linhas indesejadas de arquivos TXT. Carregue seu arquivo e defina os padrões a serem removidos.
    </div>
    """, unsafe_allow_html=True)

    def detectar_encoding(conteudo):
        resultado = chardet.detect(conteudo)
        return resultado['encoding']

    def processar_arquivo(conteudo, padroes):
        try:
            substituicoes = {
                "IMPOSTO IMPORTACAO": "IMP IMPORT",
                "TAXA SICOMEX": "TX SISCOMEX",
                "FRETE INTERNACIONAL": "FRET INTER",
                "SEGURO INTERNACIONAL": "SEG INTERN"
            }
            encoding = detectar_encoding(conteudo)
            try:
                texto = conteudo.decode(encoding)
            except UnicodeDecodeError:
                texto = conteudo.decode('latin-1')
            linhas = texto.splitlines()
            linhas_processadas = []
            for linha in linhas:
                linha = linha.strip()
                if not any(padrao in linha for padrao in padroes):
                    for original, substituto in substituicoes.items():
                        linha = linha.replace(original, substituto)
                    linhas_processadas.append(linha)
            return "\n".join(linhas_processadas), len(linhas)
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {str(e)}")
            return None, 0

    padroes_default = ["-------", "SPED EFD-ICMS/IPI"]
    arquivo = st.file_uploader("Selecione o arquivo TXT", type=['txt'])

    with st.expander("⚙️ Configurações avançadas", expanded=False):
        padroes_adicionais = st.text_input(
            "Padrões adicionais para remoção (separados por vírgula)",
            help="Exemplo: padrão1, padrão2, padrão3"
        )
        padroes = padroes_default + [
            p.strip() for p in padroes_adicionais.split(",") if p.strip()
        ] if padroes_adicionais else padroes_default

    if arquivo is not None:
        if st.button("🔄 Processar Arquivo TXT"):
            try:
                show_loading_animation("Analisando arquivo TXT...")
                conteudo = arquivo.read()
                show_processing_animation("Processando linhas...")
                resultado, total_linhas = processar_arquivo(conteudo, padroes)
                if resultado is not None:
                    show_success_animation("Arquivo processado com sucesso!")
                    linhas_processadas = len(resultado.splitlines())
                    st.success(f"""
                    **Processamento concluído!** ✔️ Linhas originais: {total_linhas}
                    ✔️ Linhas processadas: {linhas_processadas}
                    ✔️ Linhas removidas: {total_linhas - linhas_processadas}
                    """)
                    st.subheader("Prévia do resultado")
                    st.text_area("Conteúdo processado", resultado, height=300)
                    buffer = BytesIO()
                    buffer.write(resultado.encode('utf-8'))
                    buffer.seek(0)
                    st.download_button(
                        label="⬇️ Baixar arquivo processado",
                        data=buffer,
                        file_name=f"processado_{arquivo.name}",
                        mime="text/plain"
                    )
            except Exception as e:
                st.error(f"Erro inesperado: {str(e)}")
                st.info("Tente novamente ou verifique o arquivo.")

# ==============================================================================
# PARTE 2: PROCESSADOR CT-E COM EXTRAÇÃO DO PESO BRUTO E PESO BASE DE CÁLCULO
# ==============================================================================
class CTeProcessorDirect:
    def __init__(self):
        self.processed_data = []

    def extract_nfe_number_from_key(self, chave_acesso):
        if not chave_acesso or len(chave_acesso) != 44:
            return None
        try:
            numero_nfe = chave_acesso[25:34]
            return numero_nfe
        except Exception:
            return None

    def extract_peso_bruto(self, root):
        try:
            tipos_peso = ['PESO BRUTO', 'PESO BASE DE CALCULO', 'PESO BASE CÁLCULO', 'PESO']
            for prefix, uri in CTE_NAMESPACES.items():
                infQ_elements = root.findall(f'.//{{{uri}}}infQ')
                for infQ in infQ_elements:
                    tpMed = infQ.find(f'{{{uri}}}tpMed')
                    qCarga = infQ.find(f'{{{uri}}}qCarga')
                    if tpMed is not None and tpMed.text and qCarga is not None and qCarga.text:
                        for tipo_peso in tipos_peso:
                            if tipo_peso in tpMed.text.upper():
                                peso = float(qCarga.text)
                                return peso, tipo_peso
            infQ_elements = root.findall('.//infQ')
            for infQ in infQ_elements:
                tpMed = infQ.find('tpMed')
                qCarga = infQ.find('qCarga')
                if tpMed is not None and tpMed.text and qCarga is not None and qCarga.text:
                    for tipo_peso in tipos_peso:
                        if tipo_peso in tpMed.text.upper():
                            peso = float(qCarga.text)
                            return peso, tipo_peso
            return 0.0, "Não encontrado"
        except Exception as e:
            st.warning(f"Não foi possível extrair o peso: {str(e)}")
            return 0.0, "Erro na extração"

    def extract_cte_data(self, xml_content, filename):
        try:
            root = ET.fromstring(xml_content)
            for prefix, uri in CTE_NAMESPACES.items():
                ET.register_namespace(prefix, uri)

            def find_text(element, xpath):
                try:
                    for prefix, uri in CTE_NAMESPACES.items():
                        full_xpath = xpath.replace('cte:', f'{{{uri}}}')
                        found = element.find(full_xpath)
                        if found is not None and found.text:
                            return found.text
                    found = element.find(xpath.replace('cte:', ''))
                    if found is not None and found.text:
                        return found.text
                    return None
                except Exception:
                    return None

            nCT = find_text(root, './/cte:nCT')
            dhEmi = find_text(root, './/cte:dhEmi')
            cMunIni = find_text(root, './/cte:cMunIni')
            UFIni = find_text(root, './/cte:UFIni')
            cMunFim = find_text(root, './/cte:cMunFim')
            UFFim = find_text(root, './/cte:UFFim')
            emit_xNome = find_text(root, './/cte:emit/cte:xNome')
            vTPrest = find_text(root, './/cte:vTPrest')
            rem_xNome = find_text(root, './/cte:rem/cte:xNome')
            dest_xNome = find_text(root, './/cte:dest/cte:xNome')
            dest_CNPJ = find_text(root, './/cte:dest/cte:CNPJ')
            dest_CPF = find_text(root, './/cte:dest/cte:CPF')
            documento_destinatario = dest_CNPJ or dest_CPF or 'N/A'
            dest_xLgr = find_text(root, './/cte:dest/cte:enderDest/cte:xLgr')
            dest_nro = find_text(root, './/cte:dest/cte:enderDest/cte:nro')
            dest_xBairro = find_text(root, './/cte:dest/cte:enderDest/cte:xBairro')
            dest_cMun = find_text(root, './/cte:dest/cte:enderDest/cte:cMun')
            dest_xMun = find_text(root, './/cte:dest/cte:enderDest/cte:xMun')
            dest_CEP = find_text(root, './/cte:dest/cte:enderDest/cte:CEP')
            dest_UF = find_text(root, './/cte:dest/cte:enderDest/cte:UF')
            endereco_destinatario = ""
            if dest_xLgr:
                endereco_destinatario += f"{dest_xLgr}"
                if dest_nro:
                    endereco_destinatario += f", {dest_nro}"
                if dest_xBairro:
                    endereco_destinatario += f" - {dest_xBairro}"
                if dest_xMun:
                    endereco_destinatario += f", {dest_xMun}"
                if dest_UF:
                    endereco_destinatario += f"/{dest_UF}"
                if dest_CEP:
                    endereco_destinatario += f" - CEP: {dest_CEP}"
            if not endereco_destinatario:
                endereco_destinatario = "N/A"
            infNFe_chave = find_text(root, './/cte:infNFe/cte:chave')
            numero_nfe = self.extract_nfe_number_from_key(infNFe_chave) if infNFe_chave else None
            peso_bruto, tipo_peso_encontrado = self.extract_peso_bruto(root)
            data_formatada = None
            if dhEmi:
                try:
                    try:
                        data_obj = datetime.strptime(dhEmi[:10], '%Y-%m-%d')
                    except:
                        try:
                            data_obj = datetime.strptime(dhEmi[:10], '%d/%m/%Y')
                        except:
                            data_obj = datetime.strptime(dhEmi[:10], '%d/%m/%y')
                    data_formatada = data_obj.strftime('%d/%m/%y')
                except:
                    data_formatada = dhEmi[:10]
            try:
                vTPrest = float(vTPrest) if vTPrest else 0.0
            except (ValueError, TypeError):
                vTPrest = 0.0
            return {
                'Arquivo': filename,
                'nCT': nCT or 'N/A',
                'Data Emissão': data_formatada or dhEmi or 'N/A',
                'Código Município Início': cMunIni or 'N/A',
                'UF Início': UFIni or 'N/A',
                'Código Município Fim': cMunFim or 'N/A',
                'UF Fim': UFFim or 'N/A',
                'Emitente': emit_xNome or 'N/A',
                'Valor Prestação': vTPrest,
                'Peso Bruto (kg)': peso_bruto,
                'Tipo de Peso Encontrado': tipo_peso_encontrado,
                'Remetente': rem_xNome or 'N/A',
                'Destinatário': dest_xNome or 'N/A',
                'Documento Destinatário': documento_destinatario,
                'Endereço Destinatário': endereco_destinatario,
                'Município Destino': dest_xMun or 'N/A',
                'UF Destino': dest_UF or 'N/A',
                'Chave NFe': infNFe_chave or 'N/A',
                'Número NFe': numero_nfe or 'N/A',
                'Data Processamento': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            }
        except Exception as e:
            st.error(f"Erro ao extrair dados do CT-e {filename}: {str(e)}")
            return None

    def process_single_file(self, uploaded_file):
        try:
            file_content = uploaded_file.getvalue()
            filename = uploaded_file.name
            if not filename.lower().endswith('.xml'):
                return False, "Arquivo não é XML"
            content_str = file_content.decode('utf-8', errors='ignore')
            if 'CTe' not in content_str and 'conhecimento' not in content_str.lower():
                return False, "Arquivo não parece ser um CT-e"
            cte_data = self.extract_cte_data(content_str, filename)
            if cte_data:
                self.processed_data.append(cte_data)
                return True, f"CT-e {filename} processado com sucesso!"
            else:
                return False, f"Erro ao processar CT-e {filename}"
        except Exception as e:
            return False, f"Erro ao processar arquivo {filename}: {str(e)}"

    def process_multiple_files(self, uploaded_files):
        results = {'success': 0, 'errors': 0, 'messages': []}
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Processando {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
            progress_bar.progress((i + 1) / len(uploaded_files))
            success, message = self.process_single_file(uploaded_file)
            if success:
                results['success'] += 1
            else:
                results['errors'] += 1
            results['messages'].append(message)
        progress_bar.empty()
        status_text.empty()
        return results

    def get_dataframe(self):
        if self.processed_data:
            return pd.DataFrame(self.processed_data)
        return pd.DataFrame()

    def clear_data(self):
        self.processed_data = []


def processador_cte():
    processor = CTeProcessorDirect()
    st.title("🚚 Processador de CT-e para Power BI")
    st.markdown("### Processa arquivos XML de CT-e e gera planilha para análise")

    with st.expander("ℹ️ Informações sobre a extração do Peso", expanded=True):
        st.markdown("""
        **Extração do Peso - Busca Inteligente:**

        O sistema busca o peso em **múltiplos campos** na seguinte ordem de prioridade:

        1. **PESO BRUTO** - Campo principal
        2. **PESO BASE DE CALCULO** - Campo alternativo 1
        3. **PESO BASE CÁLCULO** - Campo alternativo 2
        4. **PESO** - Campo genérico
        """)

    tab1, tab2, tab3 = st.tabs(["📤 Upload", "👀 Visualizar Dados", "📥 Exportar"])

    with tab1:
        st.header("Upload de CT-es")
        upload_option = st.radio("Selecione o tipo de upload:", ["Upload Individual", "Upload em Lote"])
        if upload_option == "Upload Individual":
            uploaded_file = st.file_uploader("Selecione um arquivo XML de CT-e", type=['xml'], key="single_cte")
            if uploaded_file and st.button("📊 Processar CT-e", key="process_single"):
                show_loading_animation("Analisando estrutura do XML...")
                show_processing_animation("Extraindo dados do CT-e...")
                success, message = processor.process_single_file(uploaded_file)
                if success:
                    show_success_animation("CT-e processado com sucesso!")
                    df = processor.get_dataframe()
                    if not df.empty:
                        ultimo_cte = df.iloc[-1]
                        st.info(f"""
                        **Extração bem-sucedida:**
                        - **Peso encontrado:** {ultimo_cte['Peso Bruto (kg)']} kg
                        - **Tipo de peso:** {ultimo_cte['Tipo de Peso Encontrado']}
                        """)
                else:
                    st.error(message)
        else:
            uploaded_files = st.file_uploader(
                "Selecione múltiplos arquivos XML de CT-e",
                type=['xml'], accept_multiple_files=True, key="multiple_cte"
            )
            if uploaded_files and st.button("📊 Processar Todos", key="process_multiple"):
                show_loading_animation(f"Iniciando processamento de {len(uploaded_files)} arquivos...")
                results = processor.process_multiple_files(uploaded_files)
                show_success_animation("Processamento em lote concluído!")
                st.success(f"""
                **Processamento concluído!** ✅ Sucessos: {results['success']}
                ❌ Erros: {results['errors']}
                """)
                df = processor.get_dataframe()
                if not df.empty:
                    tipos_peso = df['Tipo de Peso Encontrado'].value_counts()
                    peso_total = df['Peso Bruto (kg)'].sum()
                    st.info(f"""
                    **Estatísticas de extração:**
                    - Peso bruto total: {peso_total:,.2f} kg
                    - Peso médio por CT-e: {df['Peso Bruto (kg)'].mean():,.2f} kg
                    """)
                    for tipo, quantidade in tipos_peso.items():
                        st.write(f"  - **{tipo}**: {quantidade} CT-e(s)")
                if results['errors'] > 0:
                    with st.expander("Ver mensagens detalhadas"):
                        for msg in results['messages']:
                            st.write(f"- {msg}")

        if st.button("🗑️ Limpar Dados Processados", type="secondary"):
            processor.clear_data()
            st.success("Dados limpos com sucesso!")
            time.sleep(1)
            st.rerun()

    with tab2:
        st.header("Dados Processados")
        df = processor.get_dataframe()
        if not df.empty:
            st.write(f"Total de CT-es processados: {len(df)}")
            col1, col2, col3 = st.columns(3)
            with col1:
                uf_filter = st.multiselect("Filtrar por UF Início", options=df['UF Início'].unique())
            with col2:
                uf_destino_filter = st.multiselect("Filtrar por UF Destino", options=df['UF Destino'].unique())
            with col3:
                tipo_peso_filter = st.multiselect("Filtrar por Tipo de Peso", options=df['Tipo de Peso Encontrado'].unique())
            st.subheader("Filtro por Peso Bruto")
            peso_min = float(df['Peso Bruto (kg)'].min())
            peso_max = float(df['Peso Bruto (kg)'].max())
            peso_filter = st.slider("Selecione a faixa de peso (kg)", peso_min, peso_max, (peso_min, peso_max))
            filtered_df = df.copy()
            if uf_filter:
                filtered_df = filtered_df[filtered_df['UF Início'].isin(uf_filter)]
            if uf_destino_filter:
                filtered_df = filtered_df[filtered_df['UF Destino'].isin(uf_destino_filter)]
            if tipo_peso_filter:
                filtered_df = filtered_df[filtered_df['Tipo de Peso Encontrado'].isin(tipo_peso_filter)]
            filtered_df = filtered_df[
                (filtered_df['Peso Bruto (kg)'] >= peso_filter[0]) &
                (filtered_df['Peso Bruto (kg)'] <= peso_filter[1])
            ]
            colunas_principais = [
                'Arquivo', 'nCT', 'Data Emissão', 'Emitente', 'Remetente',
                'Destinatário', 'UF Início', 'UF Destino', 'Peso Bruto (kg)',
                'Tipo de Peso Encontrado', 'Valor Prestação'
            ]
            st.dataframe(filtered_df[colunas_principais], use_container_width=True)
            with st.expander("📋 Ver todos os campos detalhados"):
                st.dataframe(filtered_df, use_container_width=True)
            st.subheader("📈 Estatísticas")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Valor Prestação", f"R$ {filtered_df['Valor Prestação'].sum():,.2f}")
            col2.metric("Peso Bruto Total", f"{filtered_df['Peso Bruto (kg)'].sum():,.2f} kg")
            col3.metric("Média Peso/CT-e", f"{filtered_df['Peso Bruto (kg)'].mean():,.2f} kg")
            col4.metric("Tipos de Peso", f"{filtered_df['Tipo de Peso Encontrado'].nunique()}")
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.subheader("📊 Distribuição por Tipo de Peso")
                if not filtered_df.empty:
                    tipo_counts = filtered_df['Tipo de Peso Encontrado'].value_counts()
                    fig_tipo = px.pie(
                        values=tipo_counts.values, names=tipo_counts.index,
                        title="Distribuição por Tipo de Peso Encontrado"
                    )
                    st.plotly_chart(fig_tipo, use_container_width=True)
            with col_chart2:
                st.subheader("📈 Relação Peso x Valor")
                if not filtered_df.empty:
                    fig_relacao = px.scatter(
                        filtered_df, x='Peso Bruto (kg)', y='Valor Prestação',
                        title="Relação entre Peso Bruto e Valor da Prestação",
                        color='Tipo de Peso Encontrado'
                    )
                    try:
                        x = filtered_df['Peso Bruto (kg)'].values
                        y = filtered_df['Valor Prestação'].values
                        mask = ~np.isnan(x) & ~np.isnan(y)
                        x_clean = x[mask]
                        y_clean = y[mask]
                        if len(x_clean) > 1:
                            coefficients = np.polyfit(x_clean, y_clean, 1)
                            polynomial = np.poly1d(coefficients)
                            x_trend = np.linspace(x_clean.min(), x_clean.max(), 100)
                            y_trend = polynomial(x_trend)
                            fig_relacao.add_trace(go.Scatter(
                                x=x_trend, y=y_trend, mode='lines',
                                name='Linha de Tendência',
                                line=dict(color='red', dash='dash'), opacity=0.7
                            ))
                    except Exception:
                        pass
                    st.plotly_chart(fig_relacao, use_container_width=True)
        else:
            st.info("Nenhum CT-e processado ainda. Faça upload de arquivos na aba 'Upload'.")

    with tab3:
        st.header("Exportar para Excel")
        df = processor.get_dataframe()
        if not df.empty:
            st.success(f"Pronto para exportar {len(df)} registros")
            export_option = st.radio("Formato de exportação:", ["Excel (.xlsx)", "CSV (.csv)"])
            st.subheader("Selecionar Colunas para Exportação")
            todas_colunas = df.columns.tolist()
            colunas_selecionadas = st.multiselect(
                "Selecione as colunas para exportar:", options=todas_colunas, default=todas_colunas
            )
            df_export = df[colunas_selecionadas] if colunas_selecionadas else df
            if export_option == "Excel (.xlsx)":
                show_processing_animation("Gerando arquivo Excel...")
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, sheet_name='Dados_CTe', index=False)
                output.seek(0)
                st.download_button(
                    label="📥 Baixar Planilha Excel", data=output,
                    file_name="dados_cte.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                show_processing_animation("Gerando arquivo CSV...")
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar Arquivo CSV", data=csv,
                    file_name="dados_cte.csv", mime="text/csv"
                )
            with st.expander("📋 Prévia dos dados a serem exportados"):
                st.dataframe(df_export.head(10))
        else:
            st.warning("Nenhum dado disponível para exportação.")


# ==============================================================================
# PARTE 3: PARSER SIGRAWEB (SUBSTITUI HAFELE/EXTRATO DUIMP APP2)
# ==============================================================================
class SigrawebPDFParser:
    """
    Parser dedicado para o layout de exportação do Sigraweb
    (Conferência do Processo Detalhado).
    Extrai cabeçalho global e todas as adições com tributos por item.
    """

    def __init__(self):
        self.documento = {
            'cabecalho': {},
            'itens': [],
            'totais': {}
        }

    @staticmethod
    def _parse_valor(valor_str: str) -> float:
        try:
            if not valor_str:
                return 0.0
            limpo = valor_str.strip().replace('.', '').replace(',', '.')
            return float(limpo)
        except:
            return 0.0

    @staticmethod
    def _fmt_date_to_yyyymmdd(date_str: str) -> str:
        """Converte datas como 17/04/2026 → 20260417"""
        try:
            d = datetime.strptime(date_str.strip(), '%d/%m/%Y')
            return d.strftime('%Y%m%d')
        except:
            return date_str.replace('/', '').replace('-', '')[:8]

    def parse_pdf(self, pdf_path: str) -> Dict:
        try:
            logger.info(f"Iniciando parsing Sigraweb: {pdf_path}")

            text_chunks = []
            progress_text = st.empty()
            progress_bar = st.progress(0)

            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    progress_text.text(f"Lendo página {i+1} de {total_pages} do Sigraweb...")
                    progress_bar.progress((i + 1) / total_pages)
                    text = page.extract_text(layout=False)
                    if text:
                        text_chunks.append(text)

            progress_text.empty()
            progress_bar.empty()

            full_text = "\n".join(text_chunks)
            self._extract_header(text_chunks[0] if text_chunks else "", text_chunks[1] if len(text_chunks) > 1 else "")
            self._extract_items(full_text)
            self._calculate_totals()

            del text_chunks
            del full_text
            gc.collect()

            return self.documento

        except Exception as e:
            logger.error(f"Erro CRÍTICO no parsing Sigraweb: {str(e)}")
            st.error(f"Erro ao ler o arquivo PDF Sigraweb: {str(e)}")
            return self.documento

    def _extract_header(self, page1_text: str, page2_text: str):
        """Extrai todos os dados do cabeçalho do processo da página 1 e 2."""
        h = {}

        def _find(pattern, text, group=1, default=''):
            m = re.search(pattern, text)
            return m.group(group).strip() if m else default

        # --- Página 1 ---
        h['numeroDI']        = _find(r'Número DI:\s*([\w]+)', page1_text)
        h['sigraweb']        = _find(r'SIGRAWEB:\s*([\w]+)', page1_text)
        h['identificacao']   = _find(r'Identificação:\s*([\w]+)', page1_text)
        h['cnpj']            = _find(r'CNPJ:\s*([\d\.\/\-]+)', page1_text)
        h['nomeImportador']  = _find(r'Nome da Empresa:\s*(.+?)(?:\n|CNPJ)', page1_text)
        h['dataRegistro']    = _find(r'Data Registro:([\d\-T:\.+]+)', page1_text)
        if h['dataRegistro']:
            h['dataRegistro'] = h['dataRegistro'][:10].replace('-', '')

        h['pesoBruto']       = _find(r'Peso Bruto:([\d\.,]+)', page1_text)
        h['pesoLiquido']     = _find(r'Peso Líquido:([\d\.,]+)', page1_text)
        h['volumes']         = _find(r'Volumes:([\d]+)', page1_text)
        h['embalagem']       = _find(r'Embalagem:(\w+)', page1_text)

        h['urf']             = _find(r'URF de Entrada:\s*(\d+)', page1_text, default='0917900')
        h['urfDespacho']     = _find(r'URF de Despacho:\s*(\d+)', page1_text, default='0917900')
        h['urfNome']         = _find(r'URF de Entrada:\s*\d+\s*(.+?)(?:\n|URF)', page1_text, default='ALF - CURITIBA')
        h['modalidade']      = _find(r'Modalidade de Despacho:\s*(.+?)(?:\n)', page1_text, default='Normal')
        h['viaTransporte']   = _find(r'Via Transporte:\s*(.+?)(?:\n)', page1_text, default='Aéreo')

        # País procedência (remove código numérico e lixo)
        pais_raw = _find(r'País de Procedência:\s*\d+\s*(.+?)(?:\n|Local|Incoterms)', page1_text)
        h['paisProcedencia'] = pais_raw.strip() if pais_raw else 'Alemanha'

        h['localEmbarque']   = _find(r'Local de Embarque:\s*(.+?)(?:\n|Data)', page1_text)
        h['dataEmbarque']    = _find(r'Data de Embarque:\s*([\d\/]+)', page1_text)
        h['dataChegada']     = _find(r'Data de Chegada no Brasil:\s*([\d\/]+)', page1_text)
        h['incoterms']       = _find(r'Incoterms:\s*(\w+)', page1_text, default='FCA')
        h['recinto']         = _find(r'Recinto:\s*(\d+)\s*(.+?)(?:\n)', page1_text, default='9991101')

        h['idtConhecimento'] = _find(r'IDT\. Conhecimento:\s*([\w]+)', page1_text)
        h['idtMaster']       = _find(r'IDT\. Master:\s*([\w]+)', page1_text)

        h['transportador']   = _find(r'Transportador:\s*(.+?)(?:\n|Agente)', page1_text)
        h['agenteCarga']     = _find(r'Agente de Carga:\s*(.+?)(?:\n|CE)', page1_text)

        # Valores financeiros (página 1 e 2)
        combined = page1_text + "\n" + page2_text

        h['taxaEUR']         = _find(r'Taxa EUR:\s*([\d\.,]+)', combined)
        h['taxaDolar']       = _find(r'Taxa do Dólar:\s*([\d\.,]+)', combined)
        h['fobEUR']          = _find(r'FOB:\s*([\d\.,]+)\s*\(EUR\)', combined)
        h['fobUSD']          = _find(r'FOB:.*?\(EUR\)\s*;\s*([\d\.,]+)\s*\(USD\)', combined)
        h['fobBRL']          = _find(r'FOB:.*?\(USD\);\s*([\d\.,]+)\s*\(BRL\)', combined)
        h['freteEUR']        = _find(r'Frete:\s*([\d\.,]+)\s*\(EUR\)', combined)
        h['freteUSD']        = _find(r'Frete:.*?\(EUR\)\s*;\s*([\d\.,]+)\s*\(USD\)', combined)
        h['freteBRL']        = _find(r'Frete:.*?\(USD\);\s*([\d\.,]+)\s*\(BRL\)', combined)
        h['seguroUSD']       = _find(r'Seguro:\s*([\d\.,]+)\s*\(USD\)', combined)
        h['seguroBRL']       = _find(r'Seguro:.*?;\s*([\d\.,]+)\s*\(BRL\)', combined)
        h['cifUSD']          = _find(r'CIF:\s*([\d\.,]+)\s*\(USD\)', combined)
        h['cifBRL']          = _find(r'CIF:.*?;\s*([\d\.,]+)\s*\(BRL\)', combined)
        h['valorAduaneiroUSD'] = _find(r'Valor Aduaneiro:\s*([\d\.,]+)\s*\(USD\)', combined)
        h['valorAduaneiroBRL'] = _find(r'Valor Aduaneiro:.*?;\s*([\d\.,]+)\s*\(BRL\)', combined)

        # Tributos totais
        h['totalII']         = _find(r'II\s+([\d\.,]+)\s+[\d\.,]+\s+[\d\.,]+\s+[\d\.,]+\s+[\d\.,]+\s+Itau', page1_text)
        # Simplificado: pegar da tabela de cabeçalho
        trib_m = re.search(
            r'([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+Itau\s+(\d+)\s+([\d\-]+)',
            page1_text
        )
        if trib_m:
            h['totalII']     = trib_m.group(1)
            h['totalIPI']    = trib_m.group(2)
            h['totalPIS']    = trib_m.group(3)
            h['totalCOFINS'] = trib_m.group(4)
            h['totalSiscomex'] = trib_m.group(5)
            h['banco']       = 'Itau'
            h['agencia']     = trib_m.group(6)
            h['conta']       = trib_m.group(7)
        else:
            h['totalII'] = h['totalIPI'] = h['totalPIS'] = h['totalCOFINS'] = '0'
            h['totalSiscomex'] = '0'
            h['banco']   = _find(r'Banco:\s*(\w+)', page2_text, default='Itau')
            h['agencia'] = _find(r'Agência:\s*([\d]+)', page2_text, default='3715')
            h['conta']   = _find(r'Conta Corrente:\s*([\w\-]+)', page2_text, default='')

        # Converter datas para yyyymmdd
        h['dataEmbarqueISO'] = self._fmt_date_to_yyyymmdd(h['dataEmbarque']) if h['dataEmbarque'] else ''
        h['dataChegadaISO']  = self._fmt_date_to_yyyymmdd(h['dataChegada']) if h['dataChegada'] else ''

        self.documento['cabecalho'] = h

    def _extract_items(self, full_text: str):
        """Extrai cada adição com seus dados fiscais."""
        # Divide o texto completo em blocos por adição
        chunks = re.split(r'Informações da Adição Nº:\s*(\d+)', full_text)
        items_found = []

        if len(chunks) <= 1:
            st.warning("⚠️ Nenhuma adição encontrada no PDF Sigraweb. Verifique o formato do arquivo.")
            self.documento['itens'] = []
            return

        for i in range(1, len(chunks), 2):
            num_str = chunks[i].strip()
            content  = chunks[i + 1] if (i + 1) < len(chunks) else ''
            item = self._parse_item_block(num_str, content)
            if item:
                items_found.append(item)

        self.documento['itens'] = items_found

    def _parse_item_block(self, num_str: str, text: str) -> Optional[Dict]:
        """Extrai todos os campos de uma adição."""
        try:
            pv = self._parse_valor

            item = {
                'numero_item': int(num_str),
                'numeroAdicao': num_str.zfill(3),

                # Identificação
                'ncm':             '',
                'codigo_interno':  '',
                'descricao':       '',
                'paisOrigem':      '',
                'fornecedor_raw':  'HAFELE SE & CO KG',
                'endereco_raw':    '',

                # Quantidades
                'quantidade':            0.0,   # Qnt. Estatística
                'quantidade_comercial':  0.0,   # Quantidade na linha do item
                'unidade':               'PECA',

                # Valores
                'pesoLiq':      '0',
                'valorTotal':   '0',   # FOB em EUR (string para formatar no XML)
                'valorUnit':    '0',
                'valorAduaneiroReal': 0.0,   # Valor Aduaneiro em BRL (float)
                'valorAduaneiroUSD':  0.0,   # Valor Aduaneiro em USD (float)
                'moeda':        'EURO/COM.EUROPEIA',

                # Frete e Seguro (em USD e BRL)
                'freteUSD':     0.0,
                'freteReal':    0.0,
                'seguroUSD':    0.0,
                'seguroReal':   0.0,
                'frete_internacional': 0.0,
                'seguro_internacional': 0.0,
                'aduaneiro_reais': 0.0,   # Alias direto para o merge

                # Tributos
                'ii_aliquota':      0.0,
                'ii_base_calculo':  0.0,
                'ii_valor_devido':  0.0,

                'ipi_aliquota':     0.0,
                'ipi_base_calculo': 0.0,
                'ipi_valor_devido': 0.0,

                'pis_aliquota':     0.0,
                'pis_base_calculo': 0.0,
                'pis_valor_devido': 0.0,

                'cofins_aliquota':     0.0,
                'cofins_base_calculo': 0.0,
                'cofins_valor_devido': 0.0,
            }

            # --- NCM ---
            ncm_m = re.search(r'NR NCM:\s*(\d+)', text)
            if ncm_m:
                item['ncm'] = ncm_m.group(1)

            # --- Part Number e Descrição ---
            pn_m = re.search(
                r'Part Number:\s*([\S]+)\s*\|\s*Descrição:\s*(.+?)(?=\nFabricante:|$)',
                text, re.DOTALL
            )
            if pn_m:
                item['codigo_interno'] = pn_m.group(1).strip()
                item['descricao'] = re.sub(r'\s+', ' ', pn_m.group(2).strip())
            else:
                # Tenta captura alternativa apenas pela descrição
                desc_m = re.search(r'Descrição:\s*(.+?)(?=\nFabricante:|$)', text, re.DOTALL)
                if desc_m:
                    item['descricao'] = re.sub(r'\s+', ' ', desc_m.group(1).strip())

            # --- Peso Líquido ---
            peso_m = re.search(r'Peso Líquido:\s*([\d\.,]+)', text)
            if peso_m:
                item['pesoLiq'] = peso_m.group(1)

            # --- Quantidade Estatística (Destaque) ---
            qtd_est_m = re.search(r'Qnt\. Estatística:\s*([\d\.,]+)', text)
            if qtd_est_m:
                item['quantidade'] = qtd_est_m.group(1)

            # --- Quantidade Comercial (linha "Quantidade: X Unidade:") ---
            qtd_com_m = re.search(r'Quantidade:\s*([\d\.,]+)\s+Unidade:', text)
            if qtd_com_m:
                item['quantidade_comercial'] = qtd_com_m.group(1)
            else:
                item['quantidade_comercial'] = item['quantidade']

            # --- Unidade ---
            un_m = re.search(r'Unidade:\s*(\S+)', text)
            if un_m:
                item['unidade'] = un_m.group(1).upper()

            # --- Valor FOB em EUR (usado como valorTotal para o XML) ---
            fob_eur_m = re.search(r'Valor FOB:\s*([\d\.,]+)\s+EUR', text)
            if fob_eur_m:
                item['valorTotal'] = fob_eur_m.group(1)

            # --- Valor Aduaneiro USD ---
            vad_usd_m = re.search(r'Valor Aduaneiro USD:\s*([\d\.,]+)', text)
            if vad_usd_m:
                item['valorAduaneiroUSD'] = pv(vad_usd_m.group(1))

            # --- Valor Aduaneiro Real (BRL) — base de cálculo do II ---
            vad_m = re.search(r'Valor Aduaneiro Real:\s*([\d\.,]+)', text)
            if vad_m:
                item['valorAduaneiroReal'] = pv(vad_m.group(1))   # float
                item['aduaneiro_reais']    = pv(vad_m.group(1))   # alias p/ merge
                item['ii_base_calculo']    = pv(vad_m.group(1))   # base II

            # --- Valor Unitário ---
            vunit_m = re.search(r'Valor Unitário:\s*([\d\.,]+)', text)
            if vunit_m:
                item['valorUnit'] = vunit_m.group(1)

            # --- Frete ---
            frete_usd_m = re.search(r'Valor Frete:\s*([\d\.,]+)\s+USD', text)
            if frete_usd_m:
                item['freteUSD'] = pv(frete_usd_m.group(1))
            frete_real_m = re.search(r'Valor Frete Real:\s*([\d\.,]+)', text)
            if frete_real_m:
                item['freteReal']          = pv(frete_real_m.group(1))
                item['frete_internacional'] = item['freteReal']

            # --- Seguro ---
            seg_usd_m = re.search(r'Valor Seguro:\s*([\d\.,]+)\s+USD', text)
            if seg_usd_m:
                item['seguroUSD'] = pv(seg_usd_m.group(1))
            seg_real_m = re.search(r'Valor Seguro Real:\s*([\d\.,]+)', text)
            if seg_real_m:
                item['seguroReal']          = pv(seg_real_m.group(1))
                item['seguro_internacional'] = item['seguroReal']

            # --- Moeda ---
            moeda_m = re.search(r'Moeda LI:\s*(.+?)(?:\n|Valor)', text)
            if moeda_m:
                item['moeda'] = moeda_m.group(1).strip()

            # --- País Origem ---
            pais_m = re.search(r'País Origem:\s*(.+?)(?:\n|Fabricante)', text)
            if pais_m:
                item['paisOrigem'] = pais_m.group(1).strip()

            # --- Fornecedor ---
            forn_m = re.search(r'Fornecedor:\s*(.+?)(?:\n|País)', text)
            if forn_m:
                item['fornecedor_raw'] = forn_m.group(1).strip()

            # ==================================================================
            # TABELA DE TRIBUTOS
            # Estrutura do Sigraweb:
            #  II:     Aliq(7cols) grupo(1)=aliq, grupo(6)=base, grupo(7)=valor
            #  IPI:    6cols       grupo(1)=aliq, grupo(5)=base, grupo(6)=valor
            #  PIS:    6cols       grupo(1)=aliq, grupo(5)=base, grupo(6)=valor
            #  COFINS: 6cols       grupo(1)=aliq, grupo(5)=base, grupo(6)=valor
            # ==================================================================

            # II  — 7 colunas: AliqAdVal | VlAliq | AliqRed | VlRed | %Red | Base | Valor
            ii_m = re.search(
                r'^II\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)',
                text, re.MULTILINE
            )
            if ii_m:
                item['ii_aliquota']     = pv(ii_m.group(1))
                item['ii_base_calculo'] = pv(ii_m.group(6))
                item['ii_valor_devido'] = pv(ii_m.group(7))

            # IPI — 6 colunas: AliqAdVal | VlAliq | AliqRed | %Red | Base | Valor
            ipi_m = re.search(
                r'^IPI\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)',
                text, re.MULTILINE
            )
            if ipi_m:
                item['ipi_aliquota']     = pv(ipi_m.group(1))
                item['ipi_base_calculo'] = pv(ipi_m.group(5))
                item['ipi_valor_devido'] = pv(ipi_m.group(6))

            # PIS — 6 colunas: AliqAdVal | VlAliq | AliqRed | %Red | Base | Valor
            pis_m = re.search(
                r'^PIS\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)',
                text, re.MULTILINE
            )
            if pis_m:
                item['pis_aliquota']     = pv(pis_m.group(1))
                item['pis_base_calculo'] = pv(pis_m.group(5))
                item['pis_valor_devido'] = pv(pis_m.group(6))

            # COFINS — 6 colunas
            cof_m = re.search(
                r'^COFINS\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)',
                text, re.MULTILINE
            )
            if cof_m:
                item['cofins_aliquota']     = pv(cof_m.group(1))
                item['cofins_base_calculo'] = pv(cof_m.group(5))
                item['cofins_valor_devido'] = pv(cof_m.group(6))

            # Totais calculados
            item['total_impostos'] = (
                item['ii_valor_devido'] + item['ipi_valor_devido'] +
                item['pis_valor_devido'] + item['cofins_valor_devido']
            )
            item['valor_total_com_impostos'] = pv(str(item['valorTotal'])) + item['total_impostos']

            return item

        except Exception as e:
            logger.error(f"Erro item {num_str}: {e}")
            return None

    def _calculate_totals(self):
        if self.documento['itens']:
            itens = self.documento['itens']
            pv = self._parse_valor
            self.documento['totais'] = {
                'valor_total_fob':         sum(pv(str(i.get('valorTotal', 0))) for i in itens),
                'peso_liquido_total':       sum(pv(str(i.get('pesoLiq', 0))) for i in itens),
                'total_valor_aduaneiro':   sum(i.get('aduaneiro_reais', i.get('valorAduaneiroReal', 0)) for i in itens),
                'total_ii':                sum(i.get('ii_valor_devido', 0) for i in itens),
                'total_ipi':               sum(i.get('ipi_valor_devido', 0) for i in itens),
                'total_pis':               sum(i.get('pis_valor_devido', 0) for i in itens),
                'total_cofins':            sum(i.get('cofins_valor_devido', 0) for i in itens),
                'total_frete':             sum(i.get('frete_internacional', 0) for i in itens),
                'total_seguro':            sum(i.get('seguro_internacional', 0) for i in itens),
                'quantidade_adicoes':      len(itens),
            }


# ==============================================================================
# PARTE 4: PARSER APP 1 (DUIMP) E FUNÇÕES AUXILIARES
# ==============================================================================
def montar_descricao_final(desc_complementar, codigo_extra, detalhamento):
    """
    Concatena: Descrição Complementar - Código - Detalhamento
    """
    parte1 = str(desc_complementar).strip()
    parte2 = str(codigo_extra).strip()
    parte3 = str(detalhamento).strip()
    return f"{parte1} - {parte2} - {parte3}"


class DuimpPDFParser:
    """Parser do App 1 (Mantido original + Correção Leitura Qtd Comercial e Memória)"""

    def __init__(self, file_stream):
        self.doc = fitz.open(stream=file_stream, filetype="pdf")
        self.full_text = ""
        self.header = {}
        self.items = []

    def preprocess(self):
        clean_lines = []
        for page in self.doc:
            text = page.get_text("text")
            lines = text.split('\n')
            for line in lines:
                l_strip = line.strip()
                if "Extrato da DUIMP" in l_strip:
                    continue
                if "Data, hora e responsável" in l_strip:
                    continue
                if re.match(r'^\d+\s*/\s*\d+$', l_strip):
                    continue
                clean_lines.append(line)
        self.full_text = "\n".join(clean_lines)
        self.doc.close()
        gc.collect()

    def extract_header(self):
        txt = self.full_text
        self.header["numeroDUIMP"]    = self._regex(r"Extrato da Duimp\s+([\w\-\/]+)", txt)
        self.header["cnpj"]           = self._regex(r"CNPJ do importador:\s*([\d\.\/\-]+)", txt)
        self.header["nomeImportador"] = self._regex(r"Nome do importador:\s*\n?(.+)", txt)
        self.header["pesoBruto"]      = self._regex(r"Peso Bruto \(kg\):\s*([\d\.,]+)", txt)
        self.header["pesoLiquido"]    = self._regex(r"Peso Liquido \(kg\):\s*([\d\.,]+)", txt)
        self.header["urf"]            = self._regex(r"Unidade de despacho:\s*([\d]+)", txt)
        self.header["paisProcedencia"] = self._regex(r"País de Procedência:\s*\n?(.+)", txt)

    def extract_items(self):
        chunks = re.split(r"Item\s+(\d+)", self.full_text)
        if len(chunks) > 1:
            for i in range(1, len(chunks), 2):
                num     = chunks[i]
                content = chunks[i + 1]
                item    = {"numeroAdicao": num}

                item["ncm"]        = self._regex(r"NCM:\s*([\d\.]+)", content)
                item["paisOrigem"] = self._regex(r"País de origem:\s*\n?(.+)", content)

                item["quantidade"]           = self._regex(r"Quantidade na unidade estatística:\s*([\d\.,]+)", content)
                item["quantidade_comercial"] = self._regex(r"Quantidade na unidade comercializada:\s*([\d\.,]+)", content)

                item["unidade"]    = self._regex(r"Unidade estatística:\s*(.+)", content)
                item["pesoLiq"]    = self._regex(r"Peso líquido \(kg\):\s*([\d\.,]+)", content)
                item["valorUnit"]  = self._regex(r"Valor unitário na condição de venda:\s*([\d\.,]+)", content)
                item["valorTotal"] = self._regex(r"Valor total na condição de venda:\s*([\d\.,]+)", content)
                item["moeda"]      = self._regex(r"Moeda negociada:\s*(.+)", content)

                exp_match = re.search(
                    r"Código do Exportador Estrangeiro:\s*(.+?)(?=\n\s*(?:Endereço|Dados))", content, re.DOTALL
                )
                item["fornecedor_raw"] = exp_match.group(1).strip() if exp_match else ""

                addr_match = re.search(
                    r"Endereço:\s*(.+?)(?=\n\s*(?:Dados da Mercadoria|Aplicação))", content, re.DOTALL
                )
                item["endereco_raw"] = addr_match.group(1).strip() if addr_match else ""

                desc_match = re.search(
                    r"Detalhamento do Produto:\s*(.+?)(?=\n\s*(?:Número de Identificação|Versão|Código de Class|Descrição complementar))",
                    content, re.DOTALL
                )
                item["descricao"] = desc_match.group(1).strip() if desc_match else ""

                compl_match = re.search(
                    r"Descrição complementar da mercadoria:\s*(.+?)(?=\n|$)", content, re.DOTALL
                )
                item["desc_complementar"] = compl_match.group(1).strip() if compl_match else ""

                self.items.append(item)

    def _regex(self, pattern, text):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""


# ==============================================================================
# PARTE 5: XML BUILDER E CONSTANTES
# ==============================================================================

ADICAO_FIELDS_ORDER = [
    {"tag": "acrescimo", "type": "complex", "children": [
        {"tag": "codigoAcrescimo", "default": "17"},
        {"tag": "denominacao", "default": "OUTROS ACRESCIMOS AO VALOR ADUANEIRO"},
        {"tag": "moedaNegociadaCodigo", "default": "978"},
        {"tag": "moedaNegociadaNome", "default": "EURO/COM.EUROPEIA"},
        {"tag": "valorMoedaNegociada", "default": "000000000000000"},
        {"tag": "valorReais", "default": "000000000000000"}
    ]},
    {"tag": "cideValorAliquotaEspecifica", "default": "00000000000"},
    {"tag": "cideValorDevido", "default": "000000000000000"},
    {"tag": "cideValorRecolher", "default": "000000000000000"},
    {"tag": "codigoRelacaoCompradorVendedor", "default": "3"},
    {"tag": "codigoVinculoCompradorVendedor", "default": "1"},
    {"tag": "cofinsAliquotaAdValorem", "default": "00965"},
    {"tag": "cofinsAliquotaEspecificaQuantidadeUnidade", "default": "000000000"},
    {"tag": "cofinsAliquotaEspecificaValor", "default": "0000000000"},
    {"tag": "cofinsAliquotaReduzida", "default": "00000"},
    {"tag": "cofinsAliquotaValorDevido", "default": "000000000000000"},
    {"tag": "cofinsAliquotaValorRecolher", "default": "000000000000000"},
    {"tag": "condicaoVendaIncoterm", "default": "FCA"},
    {"tag": "condicaoVendaLocal", "default": ""},
    {"tag": "condicaoVendaMetodoValoracaoCodigo", "default": "01"},
    {"tag": "condicaoVendaMetodoValoracaoNome", "default": "METODO 1 - ART. 1 DO ACORDO (DECRETO 92930/86)"},
    {"tag": "condicaoVendaMoedaCodigo", "default": "978"},
    {"tag": "condicaoVendaMoedaNome", "default": "EURO/COM.EUROPEIA"},
    {"tag": "condicaoVendaValorMoeda", "default": "000000000000000"},
    {"tag": "condicaoVendaValorReais", "default": "000000000000000"},
    {"tag": "dadosCambiaisCoberturaCambialCodigo", "default": "1"},
    {"tag": "dadosCambiaisCoberturaCambialNome", "default": "COM COBERTURA CAMBIAL E PAGAMENTO FINAL A PRAZO DE ATE' 180"},
    {"tag": "dadosCambiaisInstituicaoFinanciadoraCodigo", "default": "00"},
    {"tag": "dadosCambiaisInstituicaoFinanciadoraNome", "default": "N/I"},
    {"tag": "dadosCambiaisMotivoSemCoberturaCodigo", "default": "00"},
    {"tag": "dadosCambiaisMotivoSemCoberturaNome", "default": "N/I"},
    {"tag": "dadosCambiaisValorRealCambio", "default": "000000000000000"},
    {"tag": "dadosCargaPaisProcedenciaCodigo", "default": "000"},
    {"tag": "dadosCargaUrfEntradaCodigo", "default": "0000000"},
    {"tag": "dadosCargaViaTransporteCodigo", "default": "01"},
    {"tag": "dadosCargaViaTransporteNome", "default": "MARÍTIMA"},
    {"tag": "dadosMercadoriaAplicacao", "default": "REVENDA"},
    {"tag": "dadosMercadoriaCodigoNaladiNCCA", "default": "0000000"},
    {"tag": "dadosMercadoriaCodigoNaladiSH", "default": "00000000"},
    {"tag": "dadosMercadoriaCodigoNcm", "default": "00000000"},
    {"tag": "dadosMercadoriaCondicao", "default": "NOVA"},
    {"tag": "dadosMercadoriaDescricaoTipoCertificado", "default": "Sem Certificado"},
    {"tag": "dadosMercadoriaIndicadorTipoCertificado", "default": "1"},
    {"tag": "dadosMercadoriaMedidaEstatisticaQuantidade", "default": "00000000000000"},
    {"tag": "dadosMercadoriaMedidaEstatisticaUnidade", "default": "UNIDADE"},
    {"tag": "dadosMercadoriaNomeNcm", "default": "DESCRIÇÃO PADRÃO NCM"},
    {"tag": "dadosMercadoriaPesoLiquido", "default": "000000000000000"},
    {"tag": "dcrCoeficienteReducao", "default": "00000"},
    {"tag": "dcrIdentificacao", "default": "00000000"},
    {"tag": "dcrValorDevido", "default": "000000000000000"},
    {"tag": "dcrValorDolar", "default": "000000000000000"},
    {"tag": "dcrValorReal", "default": "000000000000000"},
    {"tag": "dcrValorRecolher", "default": "000000000000000"},
    {"tag": "fornecedorCidade", "default": ""},
    {"tag": "fornecedorLogradouro", "default": ""},
    {"tag": "fornecedorNome", "default": ""},
    {"tag": "fornecedorNumero", "default": ""},
    {"tag": "freteMoedaNegociadaCodigo", "default": "978"},
    {"tag": "freteMoedaNegociadaNome", "default": "EURO/COM.EUROPEIA"},
    {"tag": "freteValorMoedaNegociada", "default": "000000000000000"},
    {"tag": "freteValorReais", "default": "000000000000000"},
    {"tag": "iiAcordoTarifarioTipoCodigo", "default": "0"},
    {"tag": "iiAliquotaAcordo", "default": "00000"},
    {"tag": "iiAliquotaAdValorem", "default": "00000"},
    {"tag": "iiAliquotaPercentualReducao", "default": "00000"},
    {"tag": "iiAliquotaReduzida", "default": "00000"},
    {"tag": "iiAliquotaValorCalculado", "default": "000000000000000"},
    {"tag": "iiAliquotaValorDevido", "default": "000000000000000"},
    {"tag": "iiAliquotaValorRecolher", "default": "000000000000000"},
    {"tag": "iiAliquotaValorReduzido", "default": "000000000000000"},
    {"tag": "iiBaseCalculo", "default": "000000000000000"},
    {"tag": "iiFundamentoLegalCodigo", "default": "00"},
    {"tag": "iiMotivoAdmissaoTemporariaCodigo", "default": "00"},
    {"tag": "iiRegimeTributacaoCodigo", "default": "1"},
    {"tag": "iiRegimeTributacaoNome", "default": "RECOLHIMENTO INTEGRAL"},
    {"tag": "ipiAliquotaAdValorem", "default": "00000"},
    {"tag": "ipiAliquotaEspecificaCapacidadeRecipciente", "default": "00000"},
    {"tag": "ipiAliquotaEspecificaQuantidadeUnidadeMedida", "default": "000000000"},
    {"tag": "ipiAliquotaEspecificaTipoRecipienteCodigo", "default": "00"},
    {"tag": "ipiAliquotaEspecificaValorUnidadeMedida", "default": "0000000000"},
    {"tag": "ipiAliquotaNotaComplementarTIPI", "default": "00"},
    {"tag": "ipiAliquotaReduzida", "default": "00000"},
    {"tag": "ipiAliquotaValorDevido", "default": "000000000000000"},
    {"tag": "ipiAliquotaValorRecolher", "default": "000000000000000"},
    {"tag": "ipiRegimeTributacaoCodigo", "default": "4"},
    {"tag": "ipiRegimeTributacaoNome", "default": "SEM BENEFICIO"},
    {"tag": "mercadoria", "type": "complex", "children": [
        {"tag": "descricaoMercadoria", "default": ""},
        {"tag": "numeroSequencialItem", "default": "01"},
        {"tag": "quantidade", "default": "00000000000000"},
        {"tag": "unidadeMedida", "default": "UNIDADE"},
        {"tag": "valorUnitario", "default": "00000000000000000000"}
    ]},
    {"tag": "numeroAdicao", "default": "001"},
    {"tag": "numeroDUIMP", "default": ""},
    {"tag": "numeroLI", "default": "0000000000"},
    {"tag": "paisAquisicaoMercadoriaCodigo", "default": "000"},
    {"tag": "paisAquisicaoMercadoriaNome", "default": ""},
    {"tag": "paisOrigemMercadoriaCodigo", "default": "000"},
    {"tag": "paisOrigemMercadoriaNome", "default": ""},
    {"tag": "pisCofinsBaseCalculoAliquotaICMS", "default": "00000"},
    {"tag": "pisCofinsBaseCalculoFundamentoLegalCodigo", "default": "00"},
    {"tag": "pisCofinsBaseCalculoPercentualReducao", "default": "00000"},
    {"tag": "pisCofinsBaseCalculoValor", "default": "000000000000000"},
    {"tag": "pisCofinsFundamentoLegalReducaoCodigo", "default": "00"},
    {"tag": "pisCofinsRegimeTributacaoCodigo", "default": "1"},
    {"tag": "pisCofinsRegimeTributacaoNome", "default": "RECOLHIMENTO INTEGRAL"},
    {"tag": "pisPasepAliquotaAdValorem", "default": "00000"},
    {"tag": "pisPasepAliquotaEspecificaQuantidadeUnidade", "default": "000000000"},
    {"tag": "pisPasepAliquotaEspecificaValor", "default": "0000000000"},
    {"tag": "pisPasepAliquotaReduzida", "default": "00000"},
    {"tag": "pisPasepAliquotaValorDevido", "default": "000000000000000"},
    {"tag": "pisPasepAliquotaValorRecolher", "default": "000000000000000"},
    {"tag": "icmsBaseCalculoValor", "default": "000000000000000"},
    {"tag": "icmsBaseCalculoAliquota", "default": "00000"},
    {"tag": "icmsBaseCalculoValorImposto", "default": "00000000000000"},
    {"tag": "icmsBaseCalculoValorDiferido", "default": "00000000000000"},
    {"tag": "cbsIbsCst", "default": "000"},
    {"tag": "cbsIbsClasstrib", "default": "000001"},
    {"tag": "cbsBaseCalculoValor", "default": "000000000000000"},
    {"tag": "cbsBaseCalculoAliquota", "default": "00000"},
    {"tag": "cbsBaseCalculoAliquotaReducao", "default": "00000"},
    {"tag": "cbsBaseCalculoValorImposto", "default": "00000000000000"},
    {"tag": "ibsBaseCalculoValor", "default": "000000000000000"},
    {"tag": "ibsBaseCalculoAliquota", "default": "00000"},
    {"tag": "ibsBaseCalculoAliquotaReducao", "default": "00000"},
    {"tag": "ibsBaseCalculoValorImposto", "default": "00000000000000"},
    {"tag": "relacaoCompradorVendedor", "default": "Fabricante é desconhecido"},
    {"tag": "seguroMoedaNegociadaCodigo", "default": "220"},
    {"tag": "seguroMoedaNegociadaNome", "default": "DOLAR DOS EUA"},
    {"tag": "seguroValorMoedaNegociada", "default": "000000000000000"},
    {"tag": "seguroValorReais", "default": "000000000000000"},
    {"tag": "sequencialRetificacao", "default": "00"},
    {"tag": "valorMultaARecolher", "default": "000000000000000"},
    {"tag": "valorMultaARecolherAjustado", "default": "000000000000000"},
    {"tag": "valorReaisFreteInternacional", "default": "000000000000000"},
    {"tag": "valorReaisSeguroInternacional", "default": "000000000000000"},
    {"tag": "valorTotalCondicaoVenda", "default": "00000000000"},
    {"tag": "vinculoCompradorVendedor", "default": "Não há vinculação entre comprador e vendedor."}
]

FOOTER_TAGS = {
    "armazem": {"tag": "nomeArmazem", "default": "TCP"},
    "armazenamentoRecintoAduaneiroCodigo": "9801303",
    "armazenamentoRecintoAduaneiroNome": "TCP - TERMINAL",
    "armazenamentoSetor": "002",
    "canalSelecaoParametrizada": "001",
    "caracterizacaoOperacaoCodigoTipo": "1",
    "caracterizacaoOperacaoDescricaoTipo": "Importação Própria",
    "cargaDataChegada": "20251120",
    "cargaNumeroAgente": "N/I",
    "cargaPaisProcedenciaCodigo": "386",
    "cargaPaisProcedenciaNome": "",
    "cargaPesoBruto": "000000000000000",
    "cargaPesoLiquido": "000000000000000",
    "cargaUrfEntradaCodigo": "0917800",
    "cargaUrfEntradaNome": "PORTO DE PARANAGUA",
    "conhecimentoCargaEmbarqueData": "20251025",
    "conhecimentoCargaEmbarqueLocal": "EXTERIOR",
    "conhecimentoCargaId": "CE123456",
    "conhecimentoCargaIdMaster": "CE123456",
    "conhecimentoCargaTipoCodigo": "12",
    "conhecimentoCargaTipoNome": "HBL - House Bill of Lading",
    "conhecimentoCargaUtilizacao": "1",
    "conhecimentoCargaUtilizacaoNome": "Total",
    "dataDesembaraco": "20251124",
    "dataRegistro": "20251124",
    "documentoChegadaCargaCodigoTipo": "1",
    "documentoChegadaCargaNome": "Manifesto da Carga",
    "documentoChegadaCargaNumero": "1625502058594",
    "embalagem": [
        {"tag": "codigoTipoEmbalagem", "default": "60"},
        {"tag": "nomeEmbalagem", "default": "PALLETS"},
        {"tag": "quantidadeVolume", "default": "00001"}
    ],
    "freteCollect": "000000000000000",
    "freteEmTerritorioNacional": "000000000000000",
    "freteMoedaNegociadaCodigo": "978",
    "freteMoedaNegociadaNome": "EURO/COM.EUROPEIA",
    "fretePrepaid": "000000000000000",
    "freteTotalDolares": "000000000000000",
    "freteTotalMoeda": "000000000000000",
    "freteTotalReais": "000000000000000",
    "icms": [
        {"tag": "agenciaIcms", "default": "00000"},
        {"tag": "codigoTipoRecolhimentoIcms", "default": "3"},
        {"tag": "nomeTipoRecolhimentoIcms", "default": "Exoneração do ICMS"},
        {"tag": "numeroSequencialIcms", "default": "001"},
        {"tag": "ufIcms", "default": "PR"},
        {"tag": "valorTotalIcms", "default": "000000000000000"}
    ],
    "importadorCodigoTipo": "1",
    "importadorCpfRepresentanteLegal": "00000000000",
    "importadorEnderecoBairro": "CENTRO",
    "importadorEnderecoCep": "00000000",
    "importadorEnderecoComplemento": "",
    "importadorEnderecoLogradouro": "RUA PRINCIPAL",
    "importadorEnderecoMunicipio": "CIDADE",
    "importadorEnderecoNumero": "00",
    "importadorEnderecoUf": "PR",
    "importadorNome": "",
    "importadorNomeRepresentanteLegal": "REPRESENTANTE",
    "importadorNumero": "",
    "importadorNumeroTelefone": "0000000000",
    "informacaoComplementar": "Informações extraídas do Sigraweb.",
    "localDescargaTotalDolares": "000000000000000",
    "localDescargaTotalReais": "000000000000000",
    "localEmbarqueTotalDolares": "000000000000000",
    "localEmbarqueTotalReais": "000000000000000",
    "modalidadeDespachoCodigo": "1",
    "modalidadeDespachoNome": "Normal",
    "numeroDUIMP": "",
    "operacaoFundap": "N",
    "pagamento": [],
    "seguroMoedaNegociadaCodigo": "220",
    "seguroMoedaNegociadaNome": "DOLAR DOS EUA",
    "seguroTotalDolares": "000000000000000",
    "seguroTotalMoedaNegociada": "000000000000000",
    "seguroTotalReais": "000000000000000",
    "sequencialRetificacao": "00",
    "situacaoEntregaCarga": "ENTREGA CONDICIONADA",
    "tipoDeclaracaoCodigo": "01",
    "tipoDeclaracaoNome": "CONSUMO",
    "totalAdicoes": "000",
    "urfDespachoCodigo": "0917800",
    "urfDespachoNome": "PORTO DE PARANAGUA",
    "valorTotalMultaARecolherAjustado": "000000000000000",
    "viaTransporteCodigo": "01",
    "viaTransporteMultimodal": "N",
    "viaTransporteNome": "MARÍTIMA",
    "viaTransporteNomeTransportador": "MAERSK A/S",
    "viaTransporteNomeVeiculo": "MAERSK",
    "viaTransportePaisTransportadorCodigo": "741",
    "viaTransportePaisTransportadorNome": "CINGAPURA"
}


class DataFormatter:
    @staticmethod
    def clean_text(text):
        if not text:
            return ""
        text = text.replace('\n', ' ').replace('\r', '')
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def format_number(value, length=15):
        if not value:
            return "0" * length
        clean = re.sub(r'\D', '', str(value))
        if not clean:
            return "0" * length
        return clean.zfill(length)

    @staticmethod
    def format_ncm(value):
        if not value:
            return "00000000"
        return re.sub(r'\D', '', value)[:8]

    @staticmethod
    def format_input_fiscal(value, length=15, is_percent=False):
        try:
            if isinstance(value, str):
                value = value.replace('.', '')
                value = value.replace(',', '.')
            val_float = float(value)
            val_int = int(round(val_float * 100))
            return str(val_int).zfill(length)
        except:
            return "0" * length

    @staticmethod
    def format_high_precision(value, length=15):
        try:
            if isinstance(value, str):
                value = value.replace('.', '')
                value = value.replace(',', '.')
            val_float = float(value)
            val_int = int(round(val_float * 10000000))
            return str(val_int).zfill(length)
        except:
            return "0" * length

    @staticmethod
    def format_quantity(value, length=14):
        try:
            if isinstance(value, str):
                value = value.replace('.', '')
                value = value.replace(',', '.')
            val_float = float(value)
            val_int = int(round(val_float * 100000))
            return str(val_int).zfill(length)
        except:
            return "0" * length

    @staticmethod
    def calculate_cbs_ibs(base_xml_string):
        try:
            base_int = int(base_xml_string)
            base_float = base_int / 100.0
            cbs_val = base_float * 0.009
            cbs_str = str(int(round(cbs_val * 100))).zfill(14)
            ibs_val = base_float * 0.001
            ibs_str = str(int(round(ibs_val * 100))).zfill(14)
            return cbs_str, ibs_str
        except:
            return "0".zfill(14), "0".zfill(14)

    @staticmethod
    def parse_supplier_info(raw_name, raw_addr):
        data = {
            "fornecedorNome": "",
            "fornecedorLogradouro": "",
            "fornecedorNumero": "S/N",
            "fornecedorCidade": ""
        }
        if raw_name:
            parts = raw_name.split('-', 1)
            data["fornecedorNome"] = parts[-1].strip() if len(parts) > 1 else raw_name.strip()
        if raw_addr:
            clean_addr = DataFormatter.clean_text(raw_addr)
            parts_dash = clean_addr.rsplit('-', 1)
            if len(parts_dash) > 1:
                data["fornecedorCidade"] = parts_dash[1].strip()
                street_part = parts_dash[0].strip()
            else:
                data["fornecedorCidade"] = "EXTERIOR"
                street_part = clean_addr
            comma_split = street_part.rsplit(',', 1)
            if len(comma_split) > 1:
                data["fornecedorLogradouro"] = comma_split[0].strip()
                num_match = re.search(r'\d+', comma_split[1])
                if num_match:
                    data["fornecedorNumero"] = num_match.group(0)
            else:
                data["fornecedorLogradouro"] = street_part
        return data


class XMLBuilder:
    def __init__(self, parser, edited_items=None):
        self.p = parser
        self.items_to_use = edited_items if edited_items else self.p.items
        self.root = etree.Element("ListaDeclaracoes")
        self.duimp = etree.SubElement(self.root, "duimp")

    def build(self, user_inputs=None):
        h = self.p.header
        duimp_fmt = h.get("numeroDUIMP", "").split("/")[0].replace("-", "").replace(".", "")

        totals = {"frete": 0.0, "seguro": 0.0, "ii": 0.0, "ipi": 0.0, "pis": 0.0, "cofins": 0.0}

        def get_float(val):
            try:
                if isinstance(val, str):
                    val = val.replace('.', '').replace(',', '.')
                return float(val)
            except:
                return 0.0

        for it in self.items_to_use:
            totals["frete"]  += get_float(it.get("Frete (R$)"))
            totals["seguro"] += get_float(it.get("Seguro (R$)"))
            totals["ii"]     += get_float(it.get("II (R$)"))
            totals["ipi"]    += get_float(it.get("IPI (R$)"))
            totals["pis"]    += get_float(it.get("PIS (R$)"))
            totals["cofins"] += get_float(it.get("COFINS (R$)"))

        for it in self.items_to_use:
            adicao = etree.SubElement(self.duimp, "adicao")

            input_number  = str(it.get("NUMBER", "")).strip()
            original_desc = DataFormatter.clean_text(it.get("descricao", ""))
            desc_compl    = DataFormatter.clean_text(it.get("desc_complementar", ""))
            final_desc    = montar_descricao_final(desc_compl, input_number, original_desc)

            val_total_venda_fmt = DataFormatter.format_high_precision(it.get("valorTotal", "0"), 11)
            val_unit_fmt        = DataFormatter.format_high_precision(it.get("valorUnit", "0"), 20)

            qtd_comercial_raw = it.get("quantidade_comercial")
            if not qtd_comercial_raw:
                qtd_comercial_raw = it.get("quantidade")
            qtd_comercial_fmt  = DataFormatter.format_quantity(qtd_comercial_raw, 14)
            qtd_estatistica_fmt = DataFormatter.format_quantity(it.get("quantidade"), 14)

            peso_liq_fmt          = DataFormatter.format_quantity(it.get("pesoLiq"), 15)
            base_total_reais_fmt  = DataFormatter.format_input_fiscal(it.get("valorTotal", "0"), 15)

            raw_frete     = get_float(it.get("Frete (R$)", 0))
            raw_seguro    = get_float(it.get("Seguro (R$)", 0))
            raw_aduaneiro = get_float(it.get("Aduaneiro (R$)", 0))

            frete_fmt     = DataFormatter.format_input_fiscal(raw_frete)
            seguro_fmt    = DataFormatter.format_input_fiscal(raw_seguro)
            aduaneiro_fmt = DataFormatter.format_input_fiscal(raw_aduaneiro)

            ii_base_fmt = DataFormatter.format_input_fiscal(it.get("II Base (R$)", 0))
            ii_aliq_fmt = DataFormatter.format_input_fiscal(it.get("II Alíq. (%)", 0), 5, True)
            ii_val_fmt  = DataFormatter.format_input_fiscal(get_float(it.get("II (R$)", 0)))

            ipi_aliq_fmt = DataFormatter.format_input_fiscal(it.get("IPI Alíq. (%)", 0), 5, True)
            ipi_val_fmt  = DataFormatter.format_input_fiscal(get_float(it.get("IPI (R$)", 0)))

            pis_base_fmt = DataFormatter.format_input_fiscal(it.get("PIS Base (R$)", 0))
            pis_aliq_fmt = DataFormatter.format_input_fiscal(it.get("PIS Alíq. (%)", 0), 5, True)
            pis_val_fmt  = DataFormatter.format_input_fiscal(get_float(it.get("PIS (R$)", 0)))

            cofins_aliq_fmt = DataFormatter.format_input_fiscal(it.get("COFINS Alíq. (%)", 0), 5, True)
            cofins_val_fmt  = DataFormatter.format_input_fiscal(get_float(it.get("COFINS (R$)", 0)))

            icms_base_valor = ii_base_fmt if int(ii_base_fmt) > 0 else base_total_reais_fmt
            cbs_imposto, ibs_imposto = DataFormatter.calculate_cbs_ibs(icms_base_valor)

            supplier_data = DataFormatter.parse_supplier_info(
                it.get("fornecedor_raw"), it.get("endereco_raw")
            )

            extracted_map = {
                "numeroAdicao": str(it["numeroAdicao"])[-3:],
                "numeroDUIMP": duimp_fmt,
                "dadosMercadoriaCodigoNcm": DataFormatter.format_ncm(it.get("ncm")),
                "dadosMercadoriaMedidaEstatisticaQuantidade": qtd_estatistica_fmt,
                "dadosMercadoriaMedidaEstatisticaUnidade": it.get("unidade", "").upper(),
                "dadosMercadoriaPesoLiquido": peso_liq_fmt,
                "condicaoVendaMoedaNome": it.get("moeda", "").upper(),
                "valorTotalCondicaoVenda": val_total_venda_fmt,
                "valorUnitario": val_unit_fmt,
                "condicaoVendaValorMoeda": base_total_reais_fmt,
                "condicaoVendaValorReais": aduaneiro_fmt if int(aduaneiro_fmt) > 0 else base_total_reais_fmt,
                "paisOrigemMercadoriaNome": it.get("paisOrigem", "").upper(),
                "paisAquisicaoMercadoriaNome": it.get("paisOrigem", "").upper(),
                "descricaoMercadoria": final_desc,
                "quantidade": qtd_comercial_fmt,
                "unidadeMedida": it.get("unidade", "").upper(),
                "dadosCargaUrfEntradaCodigo": h.get("urf", "0917800"),
                "fornecedorNome": supplier_data["fornecedorNome"][:60],
                "fornecedorLogradouro": supplier_data["fornecedorLogradouro"][:60],
                "fornecedorNumero": supplier_data["fornecedorNumero"][:10],
                "fornecedorCidade": supplier_data["fornecedorCidade"][:30],
                "freteValorReais": frete_fmt,
                "seguroValorReais": seguro_fmt,
                "iiBaseCalculo": ii_base_fmt,
                "iiAliquotaAdValorem": ii_aliq_fmt,
                "iiAliquotaValorCalculado": ii_val_fmt,
                "iiAliquotaValorDevido": ii_val_fmt,
                "iiAliquotaValorRecolher": ii_val_fmt,
                "ipiAliquotaAdValorem": ipi_aliq_fmt,
                "ipiAliquotaValorDevido": ipi_val_fmt,
                "ipiAliquotaValorRecolher": ipi_val_fmt,
                "pisCofinsBaseCalculoValor": pis_base_fmt,
                "pisPasepAliquotaAdValorem": pis_aliq_fmt,
                "pisPasepAliquotaValorDevido": pis_val_fmt,
                "pisPasepAliquotaValorRecolher": pis_val_fmt,
                "cofinsAliquotaAdValorem": cofins_aliq_fmt,
                "cofinsAliquotaValorDevido": cofins_val_fmt,
                "cofinsAliquotaValorRecolher": cofins_val_fmt,
                "icmsBaseCalculoValor": icms_base_valor,
                "icmsBaseCalculoAliquota": "01800",
                "cbsIbsClasstrib": "000001",
                "cbsBaseCalculoValor": icms_base_valor,
                "cbsBaseCalculoAliquota": "00090",
                "cbsBaseCalculoValorImposto": cbs_imposto,
                "ibsBaseCalculoValor": icms_base_valor,
                "ibsBaseCalculoAliquota": "00010",
                "ibsBaseCalculoValorImposto": ibs_imposto
            }

            for field in ADICAO_FIELDS_ORDER:
                tag_name = field["tag"]
                if field.get("type") == "complex":
                    parent = etree.SubElement(adicao, tag_name)
                    for child in field["children"]:
                        c_tag = child["tag"]
                        val = extracted_map.get(c_tag, child["default"])
                        etree.SubElement(parent, c_tag).text = val
                else:
                    val = extracted_map.get(tag_name, field["default"])
                    etree.SubElement(adicao, tag_name).text = val

        peso_bruto_fmt     = DataFormatter.format_quantity(h.get("pesoBruto"), 15)
        peso_liq_total_fmt = DataFormatter.format_quantity(h.get("pesoLiquido"), 15)

        footer_map = {
            "numeroDUIMP": duimp_fmt,
            "importadorNome": h.get("nomeImportador", ""),
            "importadorNumero": DataFormatter.format_number(h.get("cnpj"), 14),
            "cargaPesoBruto": peso_bruto_fmt,
            "cargaPesoLiquido": peso_liq_total_fmt,
            "cargaPaisProcedenciaNome": h.get("paisProcedencia", "").upper(),
            "totalAdicoes": str(len(self.items_to_use)).zfill(3),
            "freteTotalReais": DataFormatter.format_input_fiscal(totals["frete"]),
            "seguroTotalReais": DataFormatter.format_input_fiscal(totals["seguro"]),
        }

        if user_inputs:
            footer_map["cargaDataChegada"]               = user_inputs.get("cargaDataChegada", "20251120")
            footer_map["dataDesembaraco"]                = user_inputs.get("dataDesembaraco", "20251124")
            footer_map["dataRegistro"]                   = user_inputs.get("dataRegistro", "20251124")
            footer_map["conhecimentoCargaEmbarqueData"]  = user_inputs.get("conhecimentoCargaEmbarqueData", "20251025")
            footer_map["cargaPesoBruto"]                 = user_inputs.get("cargaPesoBruto", peso_bruto_fmt)
            footer_map["cargaPesoLiquido"]               = user_inputs.get("cargaPesoLiquido", peso_liq_total_fmt)
            footer_map["localDescargaTotalDolares"]      = user_inputs.get("localDescargaTotalDolares", "000000000000000")
            footer_map["localDescargaTotalReais"]        = user_inputs.get("localDescargaTotalReais", "000000000000000")
            footer_map["localEmbarqueTotalDolares"]      = user_inputs.get("localEmbarqueTotalDolares", "000000000000000")
            footer_map["localEmbarqueTotalReais"]        = user_inputs.get("localEmbarqueTotalReais", "000000000000000")

        receita_codes = [
            {"code": "0086", "val": totals["ii"]},
            {"code": "1038", "val": totals["ipi"]},
            {"code": "5602", "val": totals["pis"]},
            {"code": "5629", "val": totals["cofins"]}
        ]
        if user_inputs and user_inputs.get("valorReceita7811", "0") != "0":
            receita_codes.append({"code": "7811", "val": float(user_inputs.get("valorReceita7811"))})

        for tag, default_val in FOOTER_TAGS.items():
            if tag == "embalagem" and user_inputs:
                parent = etree.SubElement(self.duimp, tag)
                for subfield in default_val:
                    val_to_use = subfield["default"]
                    if subfield["tag"] == "quantidadeVolume":
                        val_to_use = user_inputs.get("quantidadeVolume", val_to_use)
                    etree.SubElement(parent, subfield["tag"]).text = val_to_use
                continue

            if tag == "pagamento":
                agencia = "3715"
                banco   = "341"
                if user_inputs:
                    agencia = user_inputs.get("agenciaPagamento", "3715")
                    banco   = user_inputs.get("bancoPagamento", "341")
                for rec in receita_codes:
                    if rec["val"] > 0:
                        pag = etree.SubElement(self.duimp, "pagamento")
                        etree.SubElement(pag, "agenciaPagamento").text = agencia
                        etree.SubElement(pag, "bancoPagamento").text = banco
                        etree.SubElement(pag, "codigoReceita").text = rec["code"]
                        if rec["code"] == "7811" and user_inputs:
                            etree.SubElement(pag, "valorReceita").text = user_inputs.get("valorReceita7811").zfill(15)
                        else:
                            etree.SubElement(pag, "valorReceita").text = DataFormatter.format_input_fiscal(rec["val"])
                continue

            if tag in footer_map:
                val = footer_map[tag]
                etree.SubElement(self.duimp, tag).text = val
                continue

            if user_inputs and tag in user_inputs:
                etree.SubElement(self.duimp, tag).text = user_inputs[tag]
                continue

            if isinstance(default_val, list):
                parent = etree.SubElement(self.duimp, tag)
                for subfield in default_val:
                    etree.SubElement(parent, subfield["tag"]).text = subfield["default"]
            elif isinstance(default_val, dict):
                parent = etree.SubElement(self.duimp, tag)
                etree.SubElement(parent, default_val["tag"]).text = default_val["default"]
            else:
                val = footer_map.get(tag, default_val)
                etree.SubElement(self.duimp, tag).text = val

        xml_content = etree.tostring(self.root, pretty_print=True, encoding="UTF-8", xml_declaration=False)
        header_bytes = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        return header_bytes + xml_content


# ==============================================================================
# PARTE 6: SISTEMA INTEGRADO DUIMP (COM SIGRAWEB NO LUGAR DO APP2)
# ==============================================================================
def sistema_integrado_duimp():
    st.markdown(
        '<div class="main-header">Sistema Integrado DUIMP 2026 (Versão Final Restaurada)</div>',
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["📂 Upload e Vinculação", "📋 Conferência Detalhada", "💾 Exportar XML"])

    # ==========================================================================
    # TAB 1 — UPLOAD
    # ==========================================================================
    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.info("**Passo 1:** Carregue o Extrato DUIMP (Siscomex)")
            file_duimp = st.file_uploader("Arquivo DUIMP (.pdf)", type="pdf", key="u1")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.info("**Passo 2:** Carregue o Relatório Sigraweb (Conferência Detalhada)")
            file_sigraweb = st.file_uploader("Arquivo Sigraweb (.pdf)", type="pdf", key="u2")
            st.markdown('</div>', unsafe_allow_html=True)

        # ------------------------------------------------------------------
        # Processamento DUIMP (APP 1)
        # ------------------------------------------------------------------
        if file_duimp:
            if st.session_state["parsed_duimp"] is None or \
               file_duimp.name != getattr(st.session_state.get("last_duimp"), "name", ""):
                try:
                    p = DuimpPDFParser(file_duimp.read())
                    p.preprocess()
                    p.extract_header()
                    p.extract_items()
                    st.session_state["parsed_duimp"] = p
                    st.session_state["last_duimp"] = file_duimp

                    df = pd.DataFrame(p.items)
                    cols_fiscais = [
                        "NUMBER", "Frete (R$)", "Seguro (R$)",
                        "II (R$)", "II Base (R$)", "II Alíq. (%)",
                        "IPI (R$)", "IPI Base (R$)", "IPI Alíq. (%)",
                        "PIS (R$)", "PIS Base (R$)", "PIS Alíq. (%)",
                        "COFINS (R$)", "COFINS Base (R$)", "COFINS Alíq. (%)",
                        "Aduaneiro (R$)"
                    ]
                    for col in cols_fiscais:
                        df[col] = 0.00 if col != "NUMBER" else ""
                    st.session_state["merged_df"] = df

                    st.markdown(
                        f'<div class="success-box">✅ DUIMP Lida com Sucesso! '
                        f'{len(p.items)} adições encontradas.</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"Erro ao ler DUIMP: {e}")

        # ------------------------------------------------------------------
        # Processamento Sigraweb (APP 2 — NOVO)
        # ------------------------------------------------------------------
        if file_sigraweb and st.session_state["parsed_sigraweb"] is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(file_sigraweb.getvalue())
                tmp_path = tmp.name

            try:
                parser_sgw = SigrawebPDFParser()
                doc_sgw = parser_sgw.parse_pdf(tmp_path)
                st.session_state["parsed_sigraweb"] = doc_sgw

                qtd_itens = len(doc_sgw['itens'])
                cab = doc_sgw['cabecalho']

                if qtd_itens > 0:
                    st.markdown(
                        f'<div class="success-box">✅ Sigraweb Lido com Sucesso! '
                        f'{qtd_itens} adições encontradas.</div>',
                        unsafe_allow_html=True
                    )

                    # Exibe resumo do cabeçalho do Sigraweb
                    with st.expander("📋 Dados do Processo (Sigraweb)", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Número DI", cab.get('numeroDI', 'N/A'))
                            st.metric("CNPJ", cab.get('cnpj', 'N/A'))
                            st.metric("Adições", qtd_itens)
                        with c2:
                            st.metric("Peso Bruto (kg)", cab.get('pesoBruto', 'N/A'))
                            st.metric("Peso Líquido (kg)", cab.get('pesoLiquido', 'N/A'))
                            st.metric("Volumes", cab.get('volumes', 'N/A'))
                        with c3:
                            st.metric("Data Embarque", cab.get('dataEmbarque', 'N/A'))
                            st.metric("Data Chegada", cab.get('dataChegada', 'N/A'))
                            st.metric("Via Transporte", cab.get('viaTransporte', 'N/A'))

                        # Totais financeiros
                        st.subheader("Resumo Financeiro do Processo")
                        cf1, cf2, cf3, cf4 = st.columns(4)
                        tot = doc_sgw.get('totais', {})
                        cf1.metric("II Total (R$)",     f"R$ {tot.get('total_ii', 0):,.2f}")
                        cf2.metric("IPI Total (R$)",    f"R$ {tot.get('total_ipi', 0):,.2f}")
                        cf3.metric("PIS Total (R$)",    f"R$ {tot.get('total_pis', 0):,.2f}")
                        cf4.metric("COFINS Total (R$)", f"R$ {tot.get('total_cofins', 0):,.2f}")

                        cf5, cf6, cf7, cf8 = st.columns(4)
                        cf5.metric("Valor Aduaneiro Total (R$)", f"R$ {tot.get('total_valor_aduaneiro', 0):,.2f}")
                        cf6.metric("Frete Total (R$)",  f"R$ {tot.get('total_frete', 0):,.2f}")
                        cf7.metric("Seguro Total (R$)", f"R$ {tot.get('total_seguro', 0):,.2f}")
                        cf8.metric("Peso Líq. Total (kg)", f"{tot.get('peso_liquido_total', 0):,.2f}")

                        cf9, cf10, cf11, cf12 = st.columns(4)
                        cf9.metric("FOB Total EUR",          cab.get('fobEUR', 'N/A'))
                        cf10.metric("FOB Total BRL",         f"R$ {cab.get('fobBRL', '0')}")
                        cf11.metric("Vlr Aduaneiro USD (header)", f"$ {cab.get('valorAduaneiroUSD', '0')}")
                        cf12.metric("Vlr Aduaneiro BRL (header)", f"R$ {cab.get('valorAduaneiroBRL', '0')}")
                else:
                    st.warning(
                        "O PDF Sigraweb foi lido, mas nenhuma adição 'Informações da Adição Nº' "
                        "foi detectada. Verifique se o arquivo está no formato de "
                        "Conferência Detalhada do Sigraweb."
                    )

            except Exception as e:
                st.error(f"Erro ao ler Sigraweb: {e}")
                st.code(traceback.format_exc())
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass

        # Botão para limpar os parsers se necessário
        col_reset1, col_reset2 = st.columns(2)
        with col_reset1:
            if st.button("🔄 Recarregar DUIMP", type="secondary"):
                st.session_state["parsed_duimp"] = None
                st.session_state["merged_df"] = None
                st.rerun()
        with col_reset2:
            if st.button("🔄 Recarregar Sigraweb", type="secondary"):
                st.session_state["parsed_sigraweb"] = None
                st.rerun()

        st.divider()

        # ------------------------------------------------------------------
        # Vinculação automática DUIMP x Sigraweb
        # ------------------------------------------------------------------
        if st.button("🔗 VINCULAR DADOS (Cruzamento Automático)", type="primary", use_container_width=True):
            if st.session_state["merged_df"] is not None and st.session_state["parsed_sigraweb"] is not None:
                try:
                    df_dest = st.session_state["merged_df"].copy()
                    doc_sgw = st.session_state["parsed_sigraweb"]

                    # Monta mapa: numero_item → dados do Sigraweb
                    src_map: Dict[int, Dict] = {}
                    for item in doc_sgw['itens']:
                        try:
                            idx = int(item['numero_item'])
                            src_map[idx] = item
                        except:
                            pass

                    count = 0
                    not_found = []
                    for idx, row in df_dest.iterrows():
                        try:
                            raw_num  = str(row['numeroAdicao']).strip()
                            item_num = int(raw_num)

                            if item_num in src_map:
                                src = src_map[item_num]

                                # Código interno (Part Number do Sigraweb)
                                df_dest.at[idx, 'NUMBER']          = src.get('codigo_interno', '')

                                # Frete, Seguro e Valor Aduaneiro em BRL
                                df_dest.at[idx, 'Frete (R$)']      = src.get('frete_internacional', 0.0)
                                df_dest.at[idx, 'Seguro (R$)']     = src.get('seguro_internacional', 0.0)
                                # CORREÇÃO PRINCIPAL: Valor Aduaneiro Real (BRL) do Sigraweb
                                df_dest.at[idx, 'Aduaneiro (R$)']  = src.get('aduaneiro_reais', src.get('valorAduaneiroReal', 0.0))

                                # II — base = Valor Aduaneiro Real
                                df_dest.at[idx, 'II (R$)']         = src.get('ii_valor_devido', 0.0)
                                df_dest.at[idx, 'II Base (R$)']    = src.get('ii_base_calculo',
                                                                              src.get('aduaneiro_reais',
                                                                              src.get('valorAduaneiroReal', 0.0)))
                                df_dest.at[idx, 'II Alíq. (%)']    = src.get('ii_aliquota', 0.0)

                                # IPI
                                df_dest.at[idx, 'IPI (R$)']        = src.get('ipi_valor_devido', 0.0)
                                df_dest.at[idx, 'IPI Base (R$)']   = src.get('ipi_base_calculo', 0.0)
                                df_dest.at[idx, 'IPI Alíq. (%)']   = src.get('ipi_aliquota', 0.0)

                                # PIS
                                df_dest.at[idx, 'PIS (R$)']        = src.get('pis_valor_devido', 0.0)
                                df_dest.at[idx, 'PIS Base (R$)']   = src.get('pis_base_calculo', 0.0)
                                df_dest.at[idx, 'PIS Alíq. (%)']   = src.get('pis_aliquota', 0.0)

                                # COFINS
                                df_dest.at[idx, 'COFINS (R$)']     = src.get('cofins_valor_devido', 0.0)
                                df_dest.at[idx, 'COFINS Base (R$)'] = src.get('cofins_base_calculo', 0.0)
                                df_dest.at[idx, 'COFINS Alíq. (%)'] = src.get('cofins_aliquota', 0.0)

                                count += 1
                            else:
                                not_found.append(item_num)
                        except Exception as e_row:
                            continue

                    st.session_state["merged_df"] = df_dest
                    st.success(f"✅ Sucesso! **{count}** adições vinculadas.")

                    if not_found:
                        st.warning(
                            f"⚠️ {len(not_found)} adição(ões) do DUIMP não encontrada(s) no Sigraweb: "
                            f"{not_found}"
                        )

                    # Resumo dos valores vinculados
                    with st.expander("📊 Resumo dos Valores Vinculados"):
                        df_res = df_dest.copy()
                        rv1, rv2, rv3, rv4 = st.columns(4)
                        rv1.metric("Total II (R$)",     f"R$ {pd.to_numeric(df_res['II (R$)'], errors='coerce').sum():,.2f}")
                        rv2.metric("Total IPI (R$)",    f"R$ {pd.to_numeric(df_res['IPI (R$)'], errors='coerce').sum():,.2f}")
                        rv3.metric("Total PIS (R$)",    f"R$ {pd.to_numeric(df_res['PIS (R$)'], errors='coerce').sum():,.2f}")
                        rv4.metric("Total COFINS (R$)", f"R$ {pd.to_numeric(df_res['COFINS (R$)'], errors='coerce').sum():,.2f}")

                        rf1, rf2 = st.columns(2)
                        rf1.metric("Total Frete (R$)",  f"R$ {pd.to_numeric(df_res['Frete (R$)'], errors='coerce').sum():,.2f}")
                        rf2.metric("Total Seguro (R$)", f"R$ {pd.to_numeric(df_res['Seguro (R$)'], errors='coerce').sum():,.2f}")

                except Exception as e:
                    st.error(f"Erro na vinculação: {e}")
                    st.code(traceback.format_exc())
            else:
                st.warning("Carregue os dois arquivos (DUIMP e Sigraweb) antes de vincular.")

    # ==========================================================================
    # TAB 2 — CONFERÊNCIA DETALHADA
    # ==========================================================================
    with tab2:
        st.subheader("Conferência e Edição dos Dados Vinculados")

        if st.session_state["parsed_sigraweb"] is not None:
            doc_sgw = st.session_state["parsed_sigraweb"]
            cab     = doc_sgw['cabecalho']

            # Resumo do cabeçalho
            with st.expander("📋 Dados do Processo Sigraweb", expanded=False):
                dados_cab = {
                    "Campo": [
                        "Número DI", "SIGRAWEB ID", "Empresa Importadora", "CNPJ",
                        "URF Entrada", "Via Transporte", "País Procedência",
                        "Incoterms", "IDT Conhecimento", "IDT Master",
                        "Data Embarque", "Data Chegada Brasil", "Data Registro",
                        "Peso Bruto (kg)", "Peso Líquido (kg)", "Volumes", "Embalagem",
                        "Banco", "Agência", "Taxa EUR", "Taxa USD",
                        "FOB EUR", "FOB BRL", "Frete USD", "Frete BRL",
                        "Seguro USD", "Seguro BRL", "CIF USD", "CIF BRL",
                        "Valor Aduaneiro USD", "Valor Aduaneiro BRL"
                    ],
                    "Valor": [
                        cab.get('numeroDI', ''), cab.get('sigraweb', ''),
                        cab.get('nomeImportador', ''), cab.get('cnpj', ''),
                        cab.get('urf', ''), cab.get('viaTransporte', ''),
                        cab.get('paisProcedencia', ''), cab.get('incoterms', ''),
                        cab.get('idtConhecimento', ''), cab.get('idtMaster', ''),
                        cab.get('dataEmbarque', ''), cab.get('dataChegada', ''),
                        cab.get('dataRegistro', ''),
                        cab.get('pesoBruto', ''), cab.get('pesoLiquido', ''),
                        cab.get('volumes', ''), cab.get('embalagem', ''),
                        cab.get('banco', ''), cab.get('agencia', ''),
                        cab.get('taxaEUR', ''), cab.get('taxaDolar', ''),
                        cab.get('fobEUR', ''), cab.get('fobBRL', ''),
                        cab.get('freteUSD', ''), cab.get('freteBRL', ''),
                        cab.get('seguroUSD', ''), cab.get('seguroBRL', ''),
                        cab.get('cifUSD', ''), cab.get('cifBRL', ''),
                        cab.get('valorAduaneiroUSD', ''), cab.get('valorAduaneiroBRL', '')
                    ]
                }
                st.dataframe(pd.DataFrame(dados_cab), use_container_width=True, hide_index=True)

            # Tabela das adições do Sigraweb
            with st.expander("📑 Adições Extraídas do Sigraweb", expanded=False):
                itens_sgw = doc_sgw['itens']
                if itens_sgw:
                    df_sgw = pd.DataFrame([{
                        'Adição':          it['numeroAdicao'],
                        'Part Number':     it.get('codigo_interno', ''),
                        'NCM':             it.get('ncm', ''),
                        'Descrição':       it.get('descricao', '')[:60],
                        'País Origem':     it.get('paisOrigem', ''),
                        'Qtd Estat.':      it.get('quantidade', 0),
                        'Qtd Comerc.':     it.get('quantidade_comercial', 0),
                        'Unidade':         it.get('unidade', ''),
                        'Peso Líq.(kg)':   it.get('pesoLiq', 0),
                        'FOB EUR':         it.get('valorTotal', 0),
                        'Vlr Adu. USD':    it.get('valorAduaneiroUSD', 0),
                        'Vlr Adu. BRL':    it.get('aduaneiro_reais', it.get('valorAduaneiroReal', 0)),
                        'Frete USD':       it.get('freteUSD', 0),
                        'Frete BRL':       it.get('freteReal', 0),
                        'Seguro USD':      it.get('seguroUSD', 0),
                        'Seguro BRL':      it.get('seguroReal', 0),
                        'II %':            it.get('ii_aliquota', 0),
                        'II Base R$':      it.get('ii_base_calculo', 0),
                        'II R$':           it.get('ii_valor_devido', 0),
                        'IPI %':           it.get('ipi_aliquota', 0),
                        'IPI Base R$':     it.get('ipi_base_calculo', 0),
                        'IPI R$':          it.get('ipi_valor_devido', 0),
                        'PIS %':           it.get('pis_aliquota', 0),
                        'PIS Base R$':     it.get('pis_base_calculo', 0),
                        'PIS R$':          it.get('pis_valor_devido', 0),
                        'COFINS %':        it.get('cofins_aliquota', 0),
                        'COFINS Base R$':  it.get('cofins_base_calculo', 0),
                        'COFINS R$':       it.get('cofins_valor_devido', 0),
                        'Total Impostos':  it.get('total_impostos', 0),
                    } for it in itens_sgw])
                    st.dataframe(df_sgw, use_container_width=True, height=400)

                    # Totais da tabela de adições
                    st.subheader("Totais das Adições")
                    tc1, tc2, tc3, tc4, tc5, tc6 = st.columns(6)
                    tc1.metric("Vlr Adu. BRL Total", f"R$ {df_sgw['Vlr Adu. BRL'].sum():,.2f}")
                    tc2.metric("II Total",            f"R$ {df_sgw['II R$'].sum():,.2f}")
                    tc3.metric("IPI Total",           f"R$ {df_sgw['IPI R$'].sum():,.2f}")
                    tc4.metric("PIS Total",           f"R$ {df_sgw['PIS R$'].sum():,.2f}")
                    tc5.metric("COFINS Total",        f"R$ {df_sgw['COFINS R$'].sum():,.2f}")
                    tc6.metric("Total Impostos",      f"R$ {df_sgw['Total Impostos'].sum():,.2f}")
                else:
                    st.info("Nenhum item extraído do Sigraweb.")

        if st.session_state["merged_df"] is not None:
            st.subheader("Grade de Edição — Dados DUIMP + Sigraweb Vinculados")

            col_config = {
                "numeroAdicao": st.column_config.TextColumn("Item", width="small", disabled=True),
                "NUMBER": st.column_config.TextColumn("Part Number (Sigraweb)", width="medium"),
                "ncm": st.column_config.TextColumn("NCM", width="small", disabled=True),
                "descricao": st.column_config.TextColumn("Descrição", width="large", disabled=True),
                "quantidade": st.column_config.TextColumn("Qtd Estat.", disabled=True),
                "quantidade_comercial": st.column_config.TextColumn("Qtd Comerc.", disabled=True),
                "unidade": st.column_config.TextColumn("Unidade", disabled=True),
                "pesoLiq": st.column_config.TextColumn("Peso Líq.", disabled=True),
                "valorTotal": st.column_config.TextColumn("FOB EUR", disabled=True),
                "Frete (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                "Seguro (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Aduaneiro (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "II Base (R$)":  st.column_config.NumberColumn(label="II Base", format="R$ %.2f"),
                "II Alíq. (%)":  st.column_config.NumberColumn(label="II %", format="%.4f"),
                "II (R$)":       st.column_config.NumberColumn(label="II R$", format="R$ %.2f"),
                "IPI Base (R$)": st.column_config.NumberColumn(label="IPI Base", format="R$ %.2f"),
                "IPI Alíq. (%)": st.column_config.NumberColumn(label="IPI %", format="%.4f"),
                "IPI (R$)":      st.column_config.NumberColumn(label="IPI R$", format="R$ %.2f"),
                "PIS Base (R$)": st.column_config.NumberColumn(label="PIS Base", format="R$ %.2f"),
                "PIS Alíq. (%)": st.column_config.NumberColumn(label="PIS %", format="%.4f"),
                "PIS (R$)":      st.column_config.NumberColumn(label="PIS R$", format="R$ %.2f"),
                "COFINS Base (R$)": st.column_config.NumberColumn(label="COFINS Base", format="R$ %.2f"),
                "COFINS Alíq. (%)": st.column_config.NumberColumn(label="COFINS %", format="%.4f"),
                "COFINS (R$)":      st.column_config.NumberColumn(label="COFINS R$", format="R$ %.2f"),
            }

            edited_df = st.data_editor(
                st.session_state["merged_df"],
                hide_index=True,
                column_config=col_config,
                use_container_width=True,
                height=600
            )

            # Recalcular valores de impostos automaticamente quando base/alíquota mudam
            taxes = ['II', 'IPI', 'PIS', 'COFINS']
            for tax in taxes:
                base_col = f"{tax} Base (R$)"
                aliq_col = f"{tax} Alíq. (%)"
                val_col  = f"{tax} (R$)"
                if base_col in edited_df.columns and aliq_col in edited_df.columns:
                    edited_df[base_col] = pd.to_numeric(edited_df[base_col], errors='coerce').fillna(0.0)
                    edited_df[aliq_col] = pd.to_numeric(edited_df[aliq_col], errors='coerce').fillna(0.0)
                    edited_df[val_col]  = edited_df[base_col] * (edited_df[aliq_col] / 100.0)

            st.session_state["merged_df"] = edited_df

            # Totais rápidos
            st.subheader("📊 Totais da Grade")
            t1, t2, t3, t4, t5, t6 = st.columns(6)
            t1.metric("II Total",     f"R$ {pd.to_numeric(edited_df['II (R$)'], errors='coerce').sum():,.2f}")
            t2.metric("IPI Total",    f"R$ {pd.to_numeric(edited_df['IPI (R$)'], errors='coerce').sum():,.2f}")
            t3.metric("PIS Total",    f"R$ {pd.to_numeric(edited_df['PIS (R$)'], errors='coerce').sum():,.2f}")
            t4.metric("COFINS Total", f"R$ {pd.to_numeric(edited_df['COFINS (R$)'], errors='coerce').sum():,.2f}")
            t5.metric("Frete Total",  f"R$ {pd.to_numeric(edited_df['Frete (R$)'], errors='coerce').sum():,.2f}")
            t6.metric("Seguro Total", f"R$ {pd.to_numeric(edited_df['Seguro (R$)'], errors='coerce').sum():,.2f}")

        else:
            st.info("Nenhum dado para exibir. Realize o upload e a vinculação na aba 'Upload e Vinculação'.")

    # ==========================================================================
    # TAB 3 — EXPORTAR XML
    # ==========================================================================
    with tab3:
        st.subheader("Gerar XML Final (Configurações Manuais)")

        # Preenche automaticamente com dados do Sigraweb quando disponível
        cab_sgw = {}
        if st.session_state.get("parsed_sigraweb"):
            cab_sgw = st.session_state["parsed_sigraweb"].get("cabecalho", {})

        st.markdown("### Preenchimento das Tags do XML")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("**QUANTIDADE**")
            inp_qtd_volume = st.text_input(
                "Quantidade Volume",
                value=cab_sgw.get('volumes', '00001').zfill(5) if cab_sgw.get('volumes') else '00001',
                help="Preenche <quantidadeVolume>"
            )

            st.markdown("**DATAS**")
            inp_dt_chegada = st.text_input(
                "Data Chegada (YYYYMMDD)",
                value=cab_sgw.get('dataChegadaISO', '20251120') or '20251120',
                help="Preenche <cargaDataChegada>"
            )
            inp_dt_desemb = st.text_input(
                "Data Desembaraço (YYYYMMDD)",
                value=cab_sgw.get('dataRegistro', '20251124') or '20251124',
                help="Preenche <dataDesembaraco>"
            )
            inp_dt_reg = st.text_input(
                "Data Registro (YYYYMMDD)",
                value=cab_sgw.get('dataRegistro', '20251124') or '20251124',
                help="Preenche <dataRegistro>"
            )
            inp_dt_emb = st.text_input(
                "Data Embarque (YYYYMMDD)",
                value=cab_sgw.get('dataEmbarqueISO', '20251025') or '20251025',
                help="Preenche <conhecimentoCargaEmbarqueData>"
            )

        with c2:
            st.markdown("**PESO (KG) — formato XML**")
            peso_bruto_default = DataFormatter.format_quantity(
                cab_sgw.get('pesoBruto', '0'), 15
            ) if cab_sgw.get('pesoBruto') else '000000000000000'
            peso_liq_default = DataFormatter.format_quantity(
                cab_sgw.get('pesoLiquido', '0'), 15
            ) if cab_sgw.get('pesoLiquido') else '000000000000000'

            inp_peso_bruto = st.text_input(
                "Peso Bruto (formato XML)", value=peso_bruto_default,
                help="Preenche <cargaPesoBruto>"
            )
            inp_peso_liq = st.text_input(
                "Peso Líquido (formato XML)", value=peso_liq_default,
                help="Preenche <cargaPesoLiquido>"
            )

            st.markdown("**LOCAIS (Reais/Dólares)**")
            inp_loc_desc_dol = st.text_input("Local Descarga Total Dólares", value="000000000000000")
            inp_loc_desc_rea = st.text_input("Local Descarga Total Reais",   value="000000000000000")
            inp_loc_emb_dol  = st.text_input("Local Embarque Total Dólares", value="000000000000000")
            inp_loc_emb_rea  = st.text_input("Local Embarque Total Reais",   value="000000000000000")

        with c3:
            st.markdown("**PAGAMENTO / SISCOMEX**")
            inp_agencia = st.text_input(
                "Agência Pagamento",
                value=cab_sgw.get('agencia', '3715') or '3715',
                help="Preenche <agenciaPagamento>"
            )
            inp_banco = st.text_input("Banco Pagamento", value="341", help="Preenche <bancoPagamento>")

            st.markdown("---")
            st.markdown("**SISCOMEX 7811**")
            st.text("Preenche <codigoReceita>7811</codigoReceita>")
            inp_valor_7811 = st.text_input(
                "Valor Receita 7811", value="000000000000000",
                help="Preenche <valorReceita> para o código 7811"
            )

            st.markdown("---")
            st.markdown("**CONHECIMENTO DE CARGA**")
            inp_idt_conhec = st.text_input(
                "IDT Conhecimento",
                value=cab_sgw.get('idtConhecimento', 'CE123456') or 'CE123456',
                help="Preenche <conhecimentoCargaId>"
            )
            inp_idt_master = st.text_input(
                "IDT Master",
                value=cab_sgw.get('idtMaster', 'CE123456') or 'CE123456',
                help="Preenche <conhecimentoCargaIdMaster>"
            )

        user_xml_config = {
            "quantidadeVolume":              inp_qtd_volume,
            "cargaDataChegada":              inp_dt_chegada,
            "dataDesembaraco":               inp_dt_desemb,
            "dataRegistro":                  inp_dt_reg,
            "conhecimentoCargaEmbarqueData": inp_dt_emb,
            "cargaPesoBruto":                inp_peso_bruto,
            "cargaPesoLiquido":              inp_peso_liq,
            "agenciaPagamento":              inp_agencia,
            "bancoPagamento":                inp_banco,
            "valorReceita7811":              inp_valor_7811,
            "localDescargaTotalDolares":     inp_loc_desc_dol,
            "localDescargaTotalReais":       inp_loc_desc_rea,
            "localEmbarqueTotalDolares":     inp_loc_emb_dol,
            "localEmbarqueTotalReais":       inp_loc_emb_rea,
            "conhecimentoCargaId":           inp_idt_conhec,
            "conhecimentoCargaIdMaster":     inp_idt_master,
        }

        st.divider()

        if st.session_state["merged_df"] is not None:
            if st.button("⚙️ Gerar XML (Layout 8686)", type="primary", use_container_width=True):
                try:
                    p       = st.session_state["parsed_duimp"]
                    records = st.session_state["merged_df"].to_dict("records")

                    for i, item in enumerate(p.items):
                        if i < len(records):
                            item.update(records[i])

                    builder   = XMLBuilder(p)
                    xml_bytes = builder.build(user_inputs=user_xml_config)

                    duimp_num = p.header.get("numeroDUIMP", "0000").replace("/", "-")
                    file_name = f"DUIMP_{duimp_num}_INTEGRADO.xml"

                    st.download_button(
                        label="⬇️ Baixar XML",
                        data=xml_bytes,
                        file_name=file_name,
                        mime="text/xml"
                    )
                    st.success("✅ XML Gerado com sucesso!")

                    # Preview
                    with st.expander("👁️ Preview do XML (primeiros 3000 caracteres)"):
                        st.code(xml_bytes.decode('utf-8', errors='ignore')[:3000], language='xml')

                except Exception as e:
                    st.error(f"Erro na geração do XML: {e}")
                    st.code(traceback.format_exc())
        else:
            st.warning("Realize o upload dos arquivos e a vinculação antes de gerar o XML.")


# ==============================================================================
# APLICAÇÃO PRINCIPAL
# ==============================================================================
def main():
    load_css()

    st.markdown("""
    <div class="cover-container">
        <img src="https://raw.githubusercontent.com/DaniloNs-creator/final/7ea6ab2a610ef8f0c11be3c34f046e7ff2cdfc6a/haefele_logo.png"
             class="cover-logo">
        <h1 class="cover-title">Sistema de Processamento Unificado 2026</h1>
        <p class="cover-subtitle">Processamento de TXT, CT-e e DUIMP para análise de dados</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📄 Processador TXT",
        "🚚 Processador CT-e",
        "📊 Sistema Integrado DUIMP"
    ])

    with tab1:
        processador_txt()
    with tab2:
        processador_cte()
    with tab3:
        sistema_integrado_duimp()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {str(e)}")
        st.code(traceback.format_exc())

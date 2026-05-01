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
# Layout do arquivo APP2: "sigraweb" (novo) ou "extrato_duimp" (layout antigo)
if "layout_app2" not in st.session_state:
    st.session_state["layout_app2"] = "sigraweb"

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
    /* ============================================================
       DESIGN SYSTEM — Sistema de Processamento Unificado 2026
    ============================================================ */

    /* ── Tokens de design ── */
    :root {
        --c-navy:      #0F172A;
        --c-blue:      #1E3A8A;
        --c-blue-mid:  #2563EB;
        --c-blue-lt:   #3B82F6;
        --c-blue-bg:   #EFF6FF;
        --c-green:     #059669;
        --c-green-bg:  #D1FAE5;
        --c-amber:     #D97706;
        --c-amber-bg:  #FEF3C7;
        --c-red:       #DC2626;
        --c-surface:   #FFFFFF;
        --c-bg:        #F1F5F9;
        --c-border:    #E2E8F0;
        --c-text:      #0F172A;
        --c-muted:     #64748B;
        --radius-sm:   6px;
        --radius:      10px;
        --radius-lg:   16px;
        --radius-xl:   24px;
        --shadow-xs:   0 1px 2px rgba(0,0,0,.05);
        --shadow-sm:   0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.05);
        --shadow-md:   0 4px 16px rgba(0,0,0,.10);
        --shadow-lg:   0 12px 36px rgba(0,0,0,.14);
        --shadow-glow: 0 0 0 3px rgba(59,130,246,.20);
        --transition:  all .18s cubic-bezier(.4,0,.2,1);
    }

    /* ── Tipografia base ── */
    html, body, [class*="css"] {
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        -webkit-font-smoothing: antialiased;
    }

    /* ── Scrollbar elegante ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--c-bg); border-radius: 10px; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

    /* ──────────────────────────────────────────────────────────
       HERO BANNER
    ────────────────────────────────────────────────────────── */
    .hero {
        position: relative;
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #1D4ED8 100%);
        border-radius: var(--radius-xl);
        padding: 2.6rem 3rem 2.2rem;
        margin-bottom: 1.6rem;
        text-align: center;
        overflow: hidden;
    }
    /* Padrão de grade sutil no fundo */
    .hero::before {
        content: '';
        position: absolute; inset: 0;
        background-image:
            linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
    }
    /* Blob de luz direita */
    .hero::after {
        content: '';
        position: absolute;
        right: -80px; top: -80px;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(96,165,250,.18) 0%, transparent 70%);
        border-radius: 50%;
        pointer-events: none;
    }
    .hero-logo {
        max-width: 200px;
        margin-bottom: 1rem;
        filter: drop-shadow(0 4px 14px rgba(0,0,0,.35));
        position: relative; z-index: 1;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #FFFFFF;
        margin: 0 0 .4rem;
        letter-spacing: -.6px;
        line-height: 1.15;
        position: relative; z-index: 1;
    }
    .hero-sub {
        font-size: .95rem;
        color: rgba(255,255,255,.68);
        margin: 0 0 1.3rem;
        letter-spacing: .2px;
        position: relative; z-index: 1;
    }
    .hero-chips {
        display: flex;
        justify-content: center;
        gap: .5rem;
        flex-wrap: wrap;
        position: relative; z-index: 1;
    }
    .chip {
        display: inline-flex;
        align-items: center;
        gap: .3rem;
        background: rgba(255,255,255,.12);
        border: 1px solid rgba(255,255,255,.22);
        color: rgba(255,255,255,.92);
        border-radius: 20px;
        padding: .22rem .78rem;
        font-size: .76rem;
        font-weight: 600;
        letter-spacing: .3px;
        transition: var(--transition);
    }
    .chip:hover {
        background: rgba(255,255,255,.22);
        border-color: rgba(255,255,255,.4);
    }

    /* ──────────────────────────────────────────────────────────
       CARDS & CONTAINERS
    ────────────────────────────────────────────────────────── */
    .card {
        background: var(--c-surface);
        border-radius: var(--radius);
        border: 1px solid var(--c-border);
        box-shadow: var(--shadow-sm);
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
        transition: box-shadow .2s ease;
    }
    .card:hover { box-shadow: var(--shadow-md); }

    .section-card {
        background: var(--c-surface);
        border-radius: var(--radius);
        border: 1px solid var(--c-border);
        box-shadow: var(--shadow-xs);
        padding: 1.2rem 1.4rem;
        margin-bottom: .9rem;
        transition: var(--transition);
    }
    .section-card:hover {
        border-color: #BFDBFE;
        box-shadow: var(--shadow-sm);
    }

    /* Card de seleção de layout (APP2) */
    .layout-selector {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
        border: 1.5px solid #93C5FD;
        border-radius: var(--radius);
        padding: 1rem 1.3rem;
        margin-bottom: 1rem;
    }
    .layout-badge {
        display: inline-flex;
        align-items: center;
        gap: .4rem;
        background: var(--c-blue-mid);
        color: #fff;
        border-radius: var(--radius-sm);
        padding: .3rem .8rem;
        font-size: .82rem;
        font-weight: 700;
        letter-spacing: .2px;
        margin-top: .5rem;
    }
    .layout-badge.amber {
        background: var(--c-amber);
    }

    /* ──────────────────────────────────────────────────────────
       TIPOGRAFIA DE SEÇÃO
    ────────────────────────────────────────────────────────── */
    .main-header {
        font-size: 1.75rem;
        font-weight: 800;
        color: var(--c-blue);
        margin: 0 0 .8rem;
        letter-spacing: -.4px;
    }
    .section-title {
        display: flex;
        align-items: center;
        gap: .5rem;
        font-size: 1rem;
        font-weight: 700;
        color: var(--c-blue);
        padding: .5rem 0 .5rem .8rem;
        border-left: 3px solid var(--c-blue-lt);
        margin: 1.1rem 0 .7rem;
        background: linear-gradient(90deg, rgba(59,130,246,.06), transparent);
        border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    }

    /* ──────────────────────────────────────────────────────────
       ALERTAS / STATUS
    ────────────────────────────────────────────────────────── */
    .success-box {
        display: flex;
        align-items: flex-start;
        gap: .6rem;
        background: linear-gradient(135deg, #D1FAE5, #A7F3D0);
        color: #065F46;
        padding: .7rem 1rem;
        border-radius: var(--radius);
        border-left: 4px solid var(--c-green);
        margin: .5rem 0;
        font-weight: 500;
        font-size: .92rem;
    }
    .info-box {
        display: flex;
        align-items: flex-start;
        gap: .6rem;
        background: linear-gradient(135deg, #DBEAFE, #BFDBFE);
        color: #1E40AF;
        padding: .7rem 1rem;
        border-radius: var(--radius);
        border-left: 4px solid var(--c-blue-lt);
        margin: .5rem 0;
        font-size: .92rem;
    }
    .warning-box {
        display: flex;
        align-items: flex-start;
        gap: .6rem;
        background: linear-gradient(135deg, #FEF3C7, #FDE68A);
        color: #78350F;
        padding: .7rem 1rem;
        border-radius: var(--radius);
        border-left: 4px solid var(--c-amber);
        margin: .5rem 0;
        font-size: .92rem;
    }

    /* ──────────────────────────────────────────────────────────
       ABAS (TABS)
    ────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 3px;
        background: var(--c-bg);
        border-radius: var(--radius);
        padding: 4px;
        border: 1px solid var(--c-border);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-sm);
        font-weight: 600;
        font-size: .88rem;
        padding: .42rem 1rem;
        transition: var(--transition);
        color: var(--c-muted);
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--c-blue-mid);
        background: rgba(59,130,246,.08);
    }
    .stTabs [aria-selected="true"] {
        background: var(--c-surface) !important;
        color: var(--c-blue) !important;
        box-shadow: var(--shadow-sm) !important;
    }

    /* ──────────────────────────────────────────────────────────
       BOTÕES
    ────────────────────────────────────────────────────────── */
    .stButton > button {
        width: 100%;
        border-radius: var(--radius-sm);
        font-weight: 600;
        font-size: .88rem;
        letter-spacing: .1px;
        transition: var(--transition);
        border: none;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: var(--shadow-xs);
    }

    /* ──────────────────────────────────────────────────────────
       RADIO / SELECT (seletor de layout)
    ────────────────────────────────────────────────────────── */
    div[data-testid="stRadio"] > div {
        gap: .5rem;
    }
    div[data-testid="stRadio"] label {
        background: var(--c-surface);
        border: 1.5px solid var(--c-border);
        border-radius: var(--radius-sm);
        padding: .55rem .95rem;
        cursor: pointer;
        transition: var(--transition);
        font-weight: 500;
        font-size: .88rem;
    }
    div[data-testid="stRadio"] label:hover {
        border-color: var(--c-blue-lt);
        background: var(--c-blue-bg);
        color: var(--c-blue);
    }

    /* ──────────────────────────────────────────────────────────
       EXPANDERS
    ────────────────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: .92rem;
        color: var(--c-blue);
        background: var(--c-bg);
        border-radius: var(--radius-sm);
        padding: .5rem .8rem !important;
    }
    .streamlit-expanderContent {
        border-left: 3px solid var(--c-border);
        margin-left: .5rem;
        padding-left: .8rem;
    }

    /* ──────────────────────────────────────────────────────────
       MÉTRICAS
    ────────────────────────────────────────────────────────── */
    [data-testid="metric-container"] {
        background: var(--c-surface);
        border: 1px solid var(--c-border);
        border-radius: var(--radius);
        padding: .8rem 1rem;
        box-shadow: var(--shadow-xs);
        transition: var(--transition);
    }
    [data-testid="metric-container"]:hover {
        box-shadow: var(--shadow-sm);
        border-color: #BFDBFE;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        color: var(--c-blue) !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: .78rem !important;
        font-weight: 600 !important;
        color: var(--c-muted) !important;
        text-transform: uppercase;
        letter-spacing: .5px;
    }

    /* ──────────────────────────────────────────────────────────
       DATAFRAME / DATA EDITOR
    ────────────────────────────────────────────────────────── */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        border-radius: var(--radius);
        border: 1px solid var(--c-border) !important;
        overflow: hidden;
    }

    /* ──────────────────────────────────────────────────────────
       INPUTS
    ────────────────────────────────────────────────────────── */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        border-radius: var(--radius-sm) !important;
        border: 1.5px solid var(--c-border) !important;
        font-size: .88rem !important;
        transition: var(--transition);
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: var(--c-blue-lt) !important;
        box-shadow: var(--shadow-glow) !important;
    }

    /* ──────────────────────────────────────────────────────────
       SIDEBAR
    ────────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: var(--c-surface);
        border-right: 1px solid var(--c-border);
    }
    [data-testid="stSidebar"] .stButton > button {
        background: var(--c-blue-bg);
        color: var(--c-blue);
        border: 1px solid #BFDBFE;
    }

    /* ──────────────────────────────────────────────────────────
       DIVIDERS
    ────────────────────────────────────────────────────────── */
    hr {
        border: none;
        border-top: 1px solid var(--c-border);
        margin: 1rem 0;
    }

    /* ──────────────────────────────────────────────────────────
       ANIMAÇÕES
    ────────────────────────────────────────────────────────── */
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    .spinner {
        animation: spin 1.2s linear infinite;
        display: inline-block;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .fade-in { animation: fadeIn .3s ease forwards; }

    /* ──────────────────────────────────────────────────────────
       RESPONSIVIDADE
    ────────────────────────────────────────────────────────── */
    @media (max-width: 900px) {
        .hero { padding: 1.8rem 1.4rem 1.5rem; }
        .hero-title { font-size: 1.6rem; }
        .hero-sub { font-size: .85rem; }
        .hero-logo { max-width: 150px; }
        .card { padding: 1rem; }
        .section-card { padding: .9rem 1rem; }
        [data-testid="stMetricValue"] { font-size: 1.05rem !important; }
    }
    @media (max-width: 600px) {
        .hero-title { font-size: 1.35rem; }
        .hero { padding: 1.4rem 1rem 1.2rem; border-radius: var(--radius-lg); }
        .stTabs [data-baseweb="tab"] { padding: .35rem .6rem; font-size: .8rem; }
        .chip { font-size: .7rem; padding: .18rem .6rem; }
    }
    /* ──────────────────────────────────────────────────────────
       PAGE HEADER (por módulo)
    ────────────────────────────────────────────────────────── */
    .page-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 1.4rem;
        background: var(--c-surface);
        border: 1px solid var(--c-border);
        border-radius: var(--radius);
        margin-bottom: 1.2rem;
        box-shadow: var(--shadow-xs);
    }
    .page-header-icon {
        font-size: 2rem;
        line-height: 1;
        flex-shrink: 0;
    }
    .page-header-title {
        font-size: 1.3rem;
        font-weight: 800;
        color: var(--c-blue);
        line-height: 1.2;
    }
    .page-header-sub {
        font-size: .82rem;
        color: var(--c-muted);
        margin-top: .1rem;
    }

    /* ──────────────────────────────────────────────────────────
       UPLOAD ZONE
    ────────────────────────────────────────────────────────── */
    .upload-zone {
        background: var(--c-blue-bg);
        border: 2px dashed #93C5FD;
        border-radius: var(--radius);
        padding: 1rem 1.2rem;
        text-align: center;
        margin-bottom: .6rem;
        transition: var(--transition);
    }
    .upload-zone:hover {
        border-color: var(--c-blue-lt);
        background: #DBEAFE;
    }
    .upload-zone-icon  { font-size: 1.6rem; line-height: 1; }
    .upload-zone-title { font-weight: 700; color: var(--c-blue); font-size: .92rem; margin-top: .25rem; }
    .upload-zone-sub   { font-size: .78rem; color: var(--c-muted); margin-top: .1rem; }

    /* ──────────────────────────────────────────────────────────
       EMPTY STATE
    ────────────────────────────────────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: var(--c-muted);
    }
    .empty-state-icon  { font-size: 3rem; margin-bottom: .6rem; opacity: .6; }
    .empty-state-title { font-size: 1.05rem; font-weight: 700; color: #94A3B8; margin-bottom: .3rem; }
    .empty-state-sub   { font-size: .85rem; color: #CBD5E1; }

    /* ──────────────────────────────────────────────────────────
       INFO PILL
    ────────────────────────────────────────────────────────── */
    .info-pill {
        display: inline-flex;
        align-items: center;
        gap: .4rem;
        background: var(--c-blue-bg);
        border: 1px solid #BFDBFE;
        color: var(--c-blue);
        border-radius: 20px;
        padding: .25rem .9rem;
        font-size: .8rem;
        font-weight: 600;
        margin-bottom: .6rem;
    }

    /* ──────────────────────────────────────────────────────────
       FIELD LABEL
    ────────────────────────────────────────────────────────── */
    .field-label {
        font-size: .82rem;
        font-weight: 600;
        color: var(--c-muted);
        text-transform: uppercase;
        letter-spacing: .5px;
        margin-bottom: .25rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# PARTE 1: PROCESSADOR DE ARQUIVOS TXT
# ==============================================================================
def processador_txt():
    # ── Cabeçalho da página ───────────────────────────────────────────────
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon">📄</div>
        <div>
            <div class="page-header-title">Processador de Arquivos TXT</div>
            <div class="page-header-sub">Remova linhas, substitua padrões e baixe o arquivo limpo</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Lógica interna (inalterada) ───────────────────────────────────────
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

    # ── Layout em 2 colunas: upload + config ──────────────────────────────
    col_up, col_cfg = st.columns([3, 2], gap="large")

    with col_up:
        st.markdown('<p class="field-label">📁 Selecione o arquivo TXT</p>', unsafe_allow_html=True)
        arquivo = st.file_uploader("", type=['txt'], label_visibility="collapsed")

    with col_cfg:
        with st.expander("⚙️ Padrões adicionais de remoção", expanded=False):
            padroes_adicionais = st.text_input(
                "Padrões (separados por vírgula)",
                help="Ex: padrão1, padrão2",
                placeholder="Ex: TOTAL, SUBTOTAL"
            )
            padroes = padroes_default + [
                p.strip() for p in padroes_adicionais.split(",") if p.strip()
            ] if padroes_adicionais else padroes_default

        st.markdown(f"""
        <div class="info-pill">
            <span>🔍 Padrões ativos: <b>{len(padroes)}</b></span>
        </div>
        """, unsafe_allow_html=True)

    if arquivo is not None:
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        if st.button("🔄 Processar Arquivo TXT", type="primary", use_container_width=True):
            try:
                show_loading_animation("Analisando arquivo TXT...")
                conteudo = arquivo.read()
                show_processing_animation("Processando linhas...")
                resultado, total_linhas = processar_arquivo(conteudo, padroes)
                if resultado is not None:
                    show_success_animation("Arquivo processado com sucesso!")
                    linhas_processadas = len(resultado.splitlines())
                    removidas = total_linhas - linhas_processadas

                    # KPIs
                    k1, k2, k3 = st.columns(3)
                    k1.metric("📋 Linhas Originais",   total_linhas)
                    k2.metric("✅ Linhas Mantidas",    linhas_processadas)
                    k3.metric("🗑️ Linhas Removidas",   removidas,
                              delta=f"-{removidas}", delta_color="inverse")

                    st.markdown('<div class="section-title">👁️ Prévia do resultado</div>',
                                unsafe_allow_html=True)
                    st.text_area("", resultado, height=280, label_visibility="collapsed")

                    buffer = BytesIO()
                    buffer.write(resultado.encode('utf-8'))
                    buffer.seek(0)
                    st.download_button(
                        label="⬇️ Baixar arquivo processado",
                        data=buffer,
                        file_name=f"processado_{arquivo.name}",
                        mime="text/plain",
                        use_container_width=True,
                    )
            except Exception as e:
                st.error(f"Erro inesperado: {str(e)}")
                st.info("Tente novamente ou verifique o arquivo.")
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📂</div>
            <div class="empty-state-title">Nenhum arquivo carregado</div>
            <div class="empty-state-sub">Selecione um arquivo .TXT acima para começar</div>
        </div>
        """, unsafe_allow_html=True)

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

    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon">🚚</div>
        <div>
            <div class="page-header-title">Processador de CT-e</div>
            <div class="page-header-sub">Extrai dados de XML CT-e e gera planilha para Power BI</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📤  Upload", "📊  Dados & Análise", "📥  Exportar"])

    # ══════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown('<div class="section-title">Modo de Upload</div>', unsafe_allow_html=True)
        upload_option = st.radio(
            "", ["☝️ Upload Individual", "📦 Upload em Lote"],
            horizontal=True, label_visibility="collapsed"
        )

        if upload_option == "☝️ Upload Individual":
            col_up, col_info = st.columns([3, 2], gap="large")
            with col_up:
                st.markdown('<p class="field-label">Arquivo XML CT-e</p>', unsafe_allow_html=True)
                uploaded_file = st.file_uploader(
                    "", type=['xml'], key="single_cte", label_visibility="collapsed"
                )
            with col_info:
                st.markdown("""
                <div class="info-pill">🔍 Busca inteligente de peso em múltiplos campos</div>
                """, unsafe_allow_html=True)
                with st.expander("ℹ️ Campos de peso reconhecidos"):
                    st.markdown("""
                    1. **PESO BRUTO** — campo principal
                    2. **PESO BASE DE CALCULO** — alternativo 1
                    3. **PESO BASE CÁLCULO** — alternativo 2
                    4. **PESO** — genérico
                    """)

            if uploaded_file:
                if st.button("📊 Processar CT-e", key="process_single", type="primary",
                             use_container_width=True):
                    show_loading_animation("Analisando estrutura do XML...")
                    show_processing_animation("Extraindo dados do CT-e...")
                    success, message = processor.process_single_file(uploaded_file)
                    if success:
                        show_success_animation("CT-e processado com sucesso!")
                        df = processor.get_dataframe()
                        if not df.empty:
                            ultimo = df.iloc[-1]
                            r1, r2 = st.columns(2)
                            r1.metric("⚖️ Peso encontrado", f"{ultimo['Peso Bruto (kg)']} kg")
                            r2.metric("🏷️ Tipo de peso", ultimo['Tipo de Peso Encontrado'])
                    else:
                        st.error(message)
        else:
            st.markdown('<p class="field-label">Múltiplos arquivos XML CT-e</p>',
                        unsafe_allow_html=True)
            uploaded_files = st.file_uploader(
                "", type=['xml'], accept_multiple_files=True,
                key="multiple_cte", label_visibility="collapsed"
            )
            if uploaded_files:
                st.markdown(f'<div class="info-pill">📎 {len(uploaded_files)} arquivo(s) selecionado(s)</div>',
                            unsafe_allow_html=True)
                if st.button("📊 Processar Todos", key="process_multiple", type="primary",
                             use_container_width=True):
                    show_loading_animation(f"Processando {len(uploaded_files)} arquivos...")
                    results = processor.process_multiple_files(uploaded_files)
                    show_success_animation("Lote concluído!")

                    r1, r2 = st.columns(2)
                    r1.metric("✅ Sucesso", results['success'])
                    r2.metric("❌ Erros",   results['errors'])

                    df = processor.get_dataframe()
                    if not df.empty:
                        k1, k2, k3 = st.columns(3)
                        k1.metric("⚖️ Peso Total",  f"{df['Peso Bruto (kg)'].sum():,.2f} kg")
                        k2.metric("📈 Peso Médio",  f"{df['Peso Bruto (kg)'].mean():,.2f} kg")
                        k3.metric("🏷️ Tipos",       df['Tipo de Peso Encontrado'].nunique())

                    if results['errors'] > 0:
                        with st.expander("⚠️ Ver erros detalhados"):
                            for msg in results['messages']:
                                if "Erro" in msg:
                                    st.warning(msg)

        st.divider()
        if st.button("🗑️ Limpar Dados Processados", type="secondary", use_container_width=True):
            processor.clear_data()
            st.success("Dados limpos.")
            time.sleep(0.8)
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    with tab2:
        df = processor.get_dataframe()
        if not df.empty:
            # ── Filtros ──────────────────────────────────────────────────
            st.markdown('<div class="section-title">🔎 Filtros</div>', unsafe_allow_html=True)
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                uf_filter = st.multiselect("UF Início", options=df['UF Início'].unique())
            with fc2:
                uf_destino_filter = st.multiselect("UF Destino", options=df['UF Destino'].unique())
            with fc3:
                tipo_peso_filter = st.multiselect("Tipo de Peso", options=df['Tipo de Peso Encontrado'].unique())

            peso_min = float(df['Peso Bruto (kg)'].min())
            peso_max = float(df['Peso Bruto (kg)'].max())
            if peso_min < peso_max:
                peso_filter = st.slider("Faixa de Peso (kg)", peso_min, peso_max,
                                        (peso_min, peso_max), format="%.1f kg")
            else:
                peso_filter = (peso_min, peso_max)

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

            # ── KPIs ─────────────────────────────────────────────────────
            st.markdown('<div class="section-title">📊 Métricas</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Valor Total",    f"R$ {filtered_df['Valor Prestação'].sum():,.2f}")
            m2.metric("⚖️ Peso Total",     f"{filtered_df['Peso Bruto (kg)'].sum():,.2f} kg")
            m3.metric("📈 Peso Médio/CT-e",f"{filtered_df['Peso Bruto (kg)'].mean():,.2f} kg")
            m4.metric("📋 CT-es",          len(filtered_df))

            # ── Tabela ───────────────────────────────────────────────────
            st.markdown('<div class="section-title">📋 Dados</div>', unsafe_allow_html=True)
            colunas_principais = [
                'Arquivo','nCT','Data Emissão','Emitente','Remetente',
                'Destinatário','UF Início','UF Destino','Peso Bruto (kg)',
                'Tipo de Peso Encontrado','Valor Prestação'
            ]
            st.dataframe(filtered_df[colunas_principais], use_container_width=True, height=320)
            with st.expander("📋 Todos os campos"):
                st.dataframe(filtered_df, use_container_width=True)

            # ── Gráficos ─────────────────────────────────────────────────
            st.markdown('<div class="section-title">📈 Análise Visual</div>', unsafe_allow_html=True)
            g1, g2 = st.columns(2)
            with g1:
                if not filtered_df.empty:
                    tipo_counts = filtered_df['Tipo de Peso Encontrado'].value_counts()
                    fig_pie = px.pie(
                        values=tipo_counts.values, names=tipo_counts.index,
                        title="Distribuição por Tipo de Peso",
                        color_discrete_sequence=px.colors.sequential.Blues_r,
                        hole=0.4
                    )
                    fig_pie.update_layout(margin=dict(t=40,b=10,l=10,r=10),
                                          legend=dict(orientation="h",y=-0.15))
                    st.plotly_chart(fig_pie, use_container_width=True)
            with g2:
                if not filtered_df.empty:
                    fig_sc = px.scatter(
                        filtered_df, x='Peso Bruto (kg)', y='Valor Prestação',
                        title="Peso vs Valor Prestação",
                        color='Tipo de Peso Encontrado',
                        size_max=12,
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    try:
                        x = filtered_df['Peso Bruto (kg)'].values
                        y = filtered_df['Valor Prestação'].values
                        mask = ~np.isnan(x) & ~np.isnan(y)
                        x_c, y_c = x[mask], y[mask]
                        if len(x_c) > 1:
                            poly = np.poly1d(np.polyfit(x_c, y_c, 1))
                            xs = np.linspace(x_c.min(), x_c.max(), 100)
                            fig_sc.add_trace(go.Scatter(
                                x=xs, y=poly(xs), mode='lines',
                                name='Tendência', line=dict(color='#EF4444',dash='dash'), opacity=.7
                            ))
                    except Exception:
                        pass
                    fig_sc.update_layout(margin=dict(t=40,b=10,l=10,r=10),
                                         legend=dict(orientation="h",y=-0.2))
                    st.plotly_chart(fig_sc, use_container_width=True)
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">🚚</div>
                <div class="empty-state-title">Nenhum CT-e processado</div>
                <div class="empty-state-sub">Vá para a aba Upload e carregue os arquivos XML</div>
            </div>
            """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    with tab3:
        df = processor.get_dataframe()
        if not df.empty:
            st.markdown('<div class="section-title">💾 Exportar Dados</div>', unsafe_allow_html=True)
            col_fmt, col_cols = st.columns([1, 2], gap="large")
            with col_fmt:
                st.metric("📋 Registros disponíveis", len(df))
                export_option = st.radio("Formato", ["📊 Excel (.xlsx)", "📄 CSV (.csv)"])
            with col_cols:
                todas_colunas = df.columns.tolist()
                colunas_selecionadas = st.multiselect(
                    "Colunas para exportar", options=todas_colunas, default=todas_colunas
                )

            df_export = df[colunas_selecionadas] if colunas_selecionadas else df

            st.divider()
            if "Excel" in export_option:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, sheet_name='Dados_CTe', index=False)
                output.seek(0)
                st.download_button(
                    "📥 Baixar Excel", data=output, file_name="dados_cte.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Baixar CSV", data=csv, file_name="dados_cte.csv",
                    mime="text/csv", use_container_width=True
                )
            with st.expander("👁️ Prévia (10 primeiras linhas)"):
                st.dataframe(df_export.head(10), use_container_width=True)
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📥</div>
                <div class="empty-state-title">Nenhum dado para exportar</div>
                <div class="empty-state-sub">Processe CT-es na aba Upload primeiro</div>
            </div>
            """, unsafe_allow_html=True)


# ==============================================================================
# PARTE 3A: PARSER EXTRATO DUIMP — LAYOUT ANTIGO (APP2 original / HafelePDFParser)
# ==============================================================================
class HafelePDFParser:
    """
    Parser BLINDADO para o layout Extrato DUIMP (APP2 original).
    Otimizado para não travar a memória em PDFs com milhares de páginas.
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

    def parse_pdf(self, pdf_path: str) -> Dict:
        try:
            logger.info(f"Iniciando parsing Extrato DUIMP (layout antigo): {pdf_path}")
            text_chunks = []
            progress_text = st.empty()
            progress_bar = st.progress(0)

            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    progress_text.text(f"Lendo página {i+1} de {total_pages} do Extrato Detalhado...")
                    progress_bar.progress((i + 1) / total_pages)
                    text = page.extract_text(layout=False)
                    if text:
                        text_chunks.append(text)

            progress_text.empty()
            progress_bar.empty()

            full_text = "\n".join(text_chunks)
            self._process_full_text(full_text)

            del text_chunks
            del full_text
            gc.collect()

            return self.documento

        except Exception as e:
            logger.error(f"Erro CRÍTICO no parsing Extrato DUIMP: {str(e)}")
            st.error(f"Erro ao ler o arquivo PDF: {str(e)}")
            return self.documento

    def _process_full_text(self, text: str):
        chunks = re.split(r'(ITENS\s+DA\s+DUIMP\s*-\s*\d+)', text, flags=re.IGNORECASE)
        items_found = []

        if len(chunks) > 1:
            for i in range(1, len(chunks), 2):
                header  = chunks[i]
                content = chunks[i + 1] if (i + 1) < len(chunks) else ''
                item_num_match = re.search(r'(\d+)', header)
                item_num = int(item_num_match.group(1)) if item_num_match else i
                item_data = self._parse_item_block(item_num, content)
                if item_data:
                    items_found.append(item_data)
        else:
            st.warning("⚠️ O sistema não detectou o padrão 'ITENS DA DUIMP'. Verifique se o PDF está no formato correto.")

        self.documento['itens'] = items_found
        self._calculate_totals()

    def _parse_item_block(self, item_num: int, text: str) -> Dict:
        try:
            pv = self._parse_valor
            item = {
                'numero_item': item_num,
                'numeroAdicao': str(item_num).zfill(3),
                'ncm': '', 'codigo_interno': '', 'nome_produto': '',
                'quantidade': 0.0, 'quantidade_comercial': 0.0,
                'peso_liquido': 0.0, 'valor_total': 0.0,
                'ii_valor_devido': 0.0, 'ii_base_calculo': 0.0, 'ii_aliquota': 0.0,
                'ipi_valor_devido': 0.0, 'ipi_base_calculo': 0.0, 'ipi_aliquota': 0.0,
                'pis_valor_devido': 0.0, 'pis_base_calculo': 0.0, 'pis_aliquota': 0.0,
                'cofins_valor_devido': 0.0, 'cofins_base_calculo': 0.0, 'cofins_aliquota': 0.0,
                'frete_internacional': 0.0, 'seguro_internacional': 0.0,
                'local_aduaneiro': 0.0,
                # aliases para compatibilidade com o merge
                'aduaneiro_reais': 0.0,
                'valorAduaneiroReal': 0.0,
                'paisOrigem': '', 'fornecedor_raw': '', 'endereco_raw': '',
                'unidade': 'UNIDADE', 'pesoLiq': '0', 'valorTotal': '0', 'valorUnit': '0',
                'moeda': 'EURO/COM.EUROPEIA',
            }

            code_match = re.search(r'Código interno\s*([\d\.]+)', text, re.IGNORECASE)
            if code_match:
                item['codigo_interno'] = code_match.group(1).replace('.', '')

            ncm_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', text)
            if ncm_match:
                item['ncm'] = ncm_match.group(1).replace('.', '')

            qtd_com_match = re.search(r'Qtde Unid\. Comercial\s*([\d\.,]+)', text)
            if qtd_com_match:
                item['quantidade_comercial'] = pv(qtd_com_match.group(1))

            qtd_est_match = re.search(r'Qtde Unid\. Estatística\s*([\d\.,]+)', text)
            if qtd_est_match:
                item['quantidade'] = pv(qtd_est_match.group(1))
            else:
                item['quantidade'] = item['quantidade_comercial']

            val_match = re.search(r'Valor Tot\. Cond Venda\s*([\d\.,]+)', text)
            if val_match:
                item['valor_total'] = pv(val_match.group(1))
                item['valorTotal']  = val_match.group(1)

            peso_match = re.search(r'Peso Líquido \(KG\)\s*([\d\.,]+)', text, re.IGNORECASE)
            if peso_match:
                item['peso_liquido'] = pv(peso_match.group(1))
                item['pesoLiq']      = peso_match.group(1)

            frete_match = re.search(r'Frete Internac\. \(R\$\)\s*([\d\.,]+)', text)
            if frete_match:
                item['frete_internacional'] = pv(frete_match.group(1))

            seg_match = re.search(r'Seguro Internac\. \(R\$\)\s*([\d\.,]+)', text)
            if seg_match:
                item['seguro_internacional'] = pv(seg_match.group(1))

            aduana_match = re.search(r'Local Aduaneiro \(R\$\)\s*([\d\.,]+)', text)
            if aduana_match:
                item['local_aduaneiro']     = pv(aduana_match.group(1))
                item['aduaneiro_reais']     = item['local_aduaneiro']
                item['valorAduaneiroReal']  = item['local_aduaneiro']

            # Impostos via regex de padrão tabular
            tax_patterns = re.findall(
                r'Base de Cálculo.*?\(R\$\)\s*([\d\.,]+).*?% Alíquota\s*([\d\.,]+).*?Valor.*?(?:Devido|A Recolher|Calculado).*?\(R\$\)\s*([\d\.,]+)',
                text, re.DOTALL | re.IGNORECASE
            )
            for base_str, aliq_str, val_str in tax_patterns:
                base = pv(base_str); aliq = pv(aliq_str); val = pv(val_str)
                if 1.60 <= aliq <= 3.00:
                    item['pis_aliquota'] = aliq; item['pis_base_calculo'] = base; item['pis_valor_devido'] = val
                elif 7.00 <= aliq <= 12.00:
                    item['cofins_aliquota'] = aliq; item['cofins_base_calculo'] = base; item['cofins_valor_devido'] = val
                elif aliq > 12.00:
                    item['ii_aliquota'] = aliq; item['ii_base_calculo'] = base; item['ii_valor_devido'] = val
                elif aliq >= 0:
                    if item['ipi_aliquota'] == 0:
                        item['ipi_aliquota'] = aliq; item['ipi_base_calculo'] = base; item['ipi_valor_devido'] = val

            item['total_impostos'] = (item['ii_valor_devido'] + item['ipi_valor_devido'] +
                                      item['pis_valor_devido'] + item['cofins_valor_devido'])
            item['valor_total_com_impostos'] = item['valor_total'] + item['total_impostos']
            return item

        except Exception as e:
            logger.error(f"Erro item {item_num}: {e}")
            return None

    def _calculate_totals(self):
        if self.documento['itens']:
            itens = self.documento['itens']
            pv = self._parse_valor
            self.documento['totais'] = {
                'valor_total_mercadoria': sum(i['valor_total'] for i in itens),
                'total_valor_aduaneiro':  sum(i.get('aduaneiro_reais', 0) for i in itens),
                'total_ii':    sum(i['ii_valor_devido'] for i in itens),
                'total_ipi':   sum(i['ipi_valor_devido'] for i in itens),
                'total_pis':   sum(i['pis_valor_devido'] for i in itens),
                'total_cofins': sum(i['cofins_valor_devido'] for i in itens),
                'total_frete':  sum(i['frete_internacional'] for i in itens),
                'total_seguro': sum(i['seguro_internacional'] for i in itens),
                'quantidade_adicoes': len(itens),
            }


# ==============================================================================
# PARTE 3B: PARSER SIGRAWEB — LAYOUT NOVO (Conferência do Processo Detalhado)
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
# PARTE 6: SISTEMA INTEGRADO DUIMP — SUPORTE AOS DOIS LAYOUTS DE APP2
# ==============================================================================

def _merge_app2_items(df_dest: pd.DataFrame, itens: list) -> tuple:
    """
    Popula as colunas fiscais do df_dest a partir da lista de itens do APP2.
    Funciona tanto com HafelePDFParser quanto com SigrawebPDFParser,
    pois ambos produzem chaves compatíveis.
    """
    src_map: Dict[int, Dict] = {}
    for item in itens:
        try:
            src_map[int(item['numero_item'])] = item
        except Exception:
            pass

    count, not_found = 0, []
    for idx, row in df_dest.iterrows():
        try:
            item_num = int(str(row['numeroAdicao']).strip())
            if item_num not in src_map:
                not_found.append(item_num)
                continue
            src = src_map[item_num]

            df_dest.at[idx, 'NUMBER']           = src.get('codigo_interno', '')
            df_dest.at[idx, 'Frete (R$)']       = src.get('frete_internacional', 0.0)
            df_dest.at[idx, 'Seguro (R$)']      = src.get('seguro_internacional', 0.0)
            df_dest.at[idx, 'Aduaneiro (R$)']   = src.get('aduaneiro_reais',
                                                    src.get('valorAduaneiroReal',
                                                    src.get('local_aduaneiro', 0.0)))
            df_dest.at[idx, 'II (R$)']          = src.get('ii_valor_devido', 0.0)
            df_dest.at[idx, 'II Base (R$)']     = src.get('ii_base_calculo',
                                                    src.get('aduaneiro_reais',
                                                    src.get('valorAduaneiroReal', 0.0)))
            df_dest.at[idx, 'II Alíq. (%)']     = src.get('ii_aliquota', 0.0)
            df_dest.at[idx, 'IPI (R$)']         = src.get('ipi_valor_devido', 0.0)
            df_dest.at[idx, 'IPI Base (R$)']    = src.get('ipi_base_calculo', 0.0)
            df_dest.at[idx, 'IPI Alíq. (%)']    = src.get('ipi_aliquota', 0.0)
            df_dest.at[idx, 'PIS (R$)']         = src.get('pis_valor_devido', 0.0)
            df_dest.at[idx, 'PIS Base (R$)']    = src.get('pis_base_calculo', 0.0)
            df_dest.at[idx, 'PIS Alíq. (%)']    = src.get('pis_aliquota', 0.0)
            df_dest.at[idx, 'COFINS (R$)']      = src.get('cofins_valor_devido', 0.0)
            df_dest.at[idx, 'COFINS Base (R$)'] = src.get('cofins_base_calculo', 0.0)
            df_dest.at[idx, 'COFINS Alíq. (%)'] = src.get('cofins_aliquota', 0.0)
            count += 1
        except Exception:
            continue

    return df_dest, count, not_found


def _render_totais_grade(df: pd.DataFrame):
    """Renderiza métricas de totais da grade editada."""
    t1, t2, t3, t4, t5, t6 = st.columns(6)
    def _s(col): return pd.to_numeric(df[col], errors='coerce').sum() if col in df.columns else 0
    t1.metric("II Total",      f"R$ {_s('II (R$)'):,.2f}")
    t2.metric("IPI Total",     f"R$ {_s('IPI (R$)'):,.2f}")
    t3.metric("PIS Total",     f"R$ {_s('PIS (R$)'):,.2f}")
    t4.metric("COFINS Total",  f"R$ {_s('COFINS (R$)'):,.2f}")
    t5.metric("Frete Total",   f"R$ {_s('Frete (R$)'):,.2f}")
    t6.metric("Seguro Total",  f"R$ {_s('Seguro (R$)'):,.2f}")


def sistema_integrado_duimp():
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon">📊</div>
        <div>
            <div class="page-header-title">Sistema Integrado DUIMP 2026</div>
            <div class="page-header-sub">Upload · Vinculação · Conferência · Geração de XML 8686</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📂  Upload & Vinculação",
        "📋  Conferência",
        "💾  Exportar XML"
    ])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — UPLOAD E VINCULAÇÃO
    # ══════════════════════════════════════════════════════════════════════
    with tab1:

        # ── Seletor de layout ─────────────────────────────────────────────
        st.markdown('<div class="section-title">⚙️ Formato do Arquivo de Tributos (APP2)</div>',
                    unsafe_allow_html=True)

        col_radio, col_badge = st.columns([3, 1], gap="large")
        with col_radio:
            layout_choice = st.radio(
                "",
                options=[
                    "🔵  Sigraweb — Conferência do Processo Detalhado (layout novo)",
                    "🟠  Extrato DUIMP — Itens da DUIMP (layout antigo)"
                ],
                index=0 if st.session_state["layout_app2"] == "sigraweb" else 1,
                key="layout_radio",
                horizontal=False,
                label_visibility="collapsed"
            )
            novo_layout = "sigraweb" if layout_choice.startswith("🔵") else "extrato_duimp"
            if novo_layout != st.session_state["layout_app2"]:
                st.session_state["layout_app2"]     = novo_layout
                st.session_state["parsed_sigraweb"] = None
                st.session_state["merged_df"]       = None
                st.rerun()

        with col_badge:
            is_sgw = st.session_state["layout_app2"] == "sigraweb"
            badge_cls  = "layout-badge"        if is_sgw else "layout-badge amber"
            badge_text = "🔵 Sigraweb (ativo)" if is_sgw else "🟠 Extrato DUIMP (ativo)"
            st.markdown(f'<div class="{badge_cls}">{badge_text}</div>', unsafe_allow_html=True)

        st.divider()

        # ── Upload dos dois arquivos ──────────────────────────────────────
        st.markdown('<div class="section-title">📂 Carregar Arquivos</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("""
            <div class="upload-zone">
                <div class="upload-zone-icon">📄</div>
                <div class="upload-zone-title">Passo 1 — Extrato DUIMP</div>
                <div class="upload-zone-sub">Siscomex · PDF</div>
            </div>
            """, unsafe_allow_html=True)
            file_duimp = st.file_uploader("DUIMP PDF", type="pdf", key="u1",
                                          label_visibility="collapsed")

        with col2:
            label_zone = ("Sigraweb · Conferência Detalhada"
                          if st.session_state["layout_app2"] == "sigraweb"
                          else "Extrato DUIMP · Itens da DUIMP")
            label_u2 = ("Arquivo Sigraweb (.pdf)"
                        if st.session_state["layout_app2"] == "sigraweb"
                        else "Arquivo Extrato DUIMP (.pdf)")
            st.markdown(f"""
            <div class="upload-zone">
                <div class="upload-zone-icon">📑</div>
                <div class="upload-zone-title">Passo 2 — {label_zone}</div>
                <div class="upload-zone-sub">PDF</div>
            </div>
            """, unsafe_allow_html=True)
            file_app2 = st.file_uploader(label_u2, type="pdf", key="u2",
                                         label_visibility="collapsed")

        # ── Processamento APP1 ────────────────────────────────────────────
        if file_duimp:
            if (st.session_state["parsed_duimp"] is None or
                    file_duimp.name != getattr(st.session_state.get("last_duimp"), "name", "")):
                try:
                    p = DuimpPDFParser(file_duimp.read())
                    p.preprocess()
                    p.extract_header()
                    p.extract_items()
                    st.session_state["parsed_duimp"] = p
                    st.session_state["last_duimp"]   = file_duimp
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
                        f'<div class="success-box">✅ DUIMP lida — {len(p.items)} adições encontradas.</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"Erro ao ler DUIMP: {e}")

        # ── Processamento APP2 ────────────────────────────────────────────
        if file_app2 and st.session_state["parsed_sigraweb"] is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(file_app2.getvalue())
                tmp_path = tmp.name
            try:
                parser_app2 = (SigrawebPDFParser()
                               if st.session_state["layout_app2"] == "sigraweb"
                               else HafelePDFParser())
                doc_app2 = parser_app2.parse_pdf(tmp_path)
                st.session_state["parsed_sigraweb"] = doc_app2
                qtd_itens = len(doc_app2['itens'])
                if qtd_itens > 0:
                    layout_name = ("Sigraweb" if st.session_state["layout_app2"] == "sigraweb"
                                   else "Extrato DUIMP")
                    st.markdown(
                        f'<div class="success-box">✅ {layout_name} lido — {qtd_itens} itens encontrados.</div>',
                        unsafe_allow_html=True
                    )
                    # Resumo Sigraweb
                    if st.session_state["layout_app2"] == "sigraweb":
                        cab = doc_app2.get('cabecalho', {})
                        tot = doc_app2.get('totais', {})
                        with st.expander("📋 Resumo do Processo (Sigraweb)", expanded=True):
                            r1, r2, r3, r4 = st.columns(4)
                            r1.metric("Número DI",        cab.get('numeroDI','N/A'))
                            r2.metric("Adições",          qtd_itens)
                            r3.metric("Peso Bruto (kg)",  cab.get('pesoBruto','N/A'))
                            r4.metric("Via Transporte",   cab.get('viaTransporte','N/A'))
                            m1,m2,m3,m4 = st.columns(4)
                            m1.metric("II Total",         f"R$ {tot.get('total_ii',0):,.2f}")
                            m2.metric("IPI Total",        f"R$ {tot.get('total_ipi',0):,.2f}")
                            m3.metric("PIS Total",        f"R$ {tot.get('total_pis',0):,.2f}")
                            m4.metric("COFINS Total",     f"R$ {tot.get('total_cofins',0):,.2f}")
                            n1,n2,n3,n4 = st.columns(4)
                            n1.metric("Vlr Aduaneiro",    f"R$ {tot.get('total_valor_aduaneiro',0):,.2f}")
                            n2.metric("Frete Total",      f"R$ {tot.get('total_frete',0):,.2f}")
                            n3.metric("Seguro Total",     f"R$ {tot.get('total_seguro',0):,.2f}")
                            n4.metric("Peso Líq. (kg)",   f"{tot.get('peso_liquido_total',0):,.2f}")
                    else:
                        tot = doc_app2.get('totais',{})
                        with st.expander("📋 Resumo Extrato DUIMP", expanded=True):
                            e1,e2,e3,e4 = st.columns(4)
                            e1.metric("Itens",      qtd_itens)
                            e2.metric("II Total",   f"R$ {tot.get('total_ii',0):,.2f}")
                            e3.metric("PIS Total",  f"R$ {tot.get('total_pis',0):,.2f}")
                            e4.metric("COFINS Total",f"R$ {tot.get('total_cofins',0):,.2f}")
                else:
                    st.warning("Nenhum item detectado. Verifique se o layout selecionado está correto.")
            except Exception as e:
                st.error(f"Erro ao ler APP2: {e}")
                st.code(traceback.format_exc())
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        # ── Ações ─────────────────────────────────────────────────────────
        st.divider()
        st.markdown('<div class="section-title">🔗 Ações</div>', unsafe_allow_html=True)

        btn_col, reset_col = st.columns([2, 1], gap="large")
        with btn_col:
            if st.button("🔗 VINCULAR DADOS (Cruzamento Automático)",
                         type="primary", use_container_width=True):
                if st.session_state["merged_df"] is not None and \
                   st.session_state["parsed_sigraweb"] is not None:
                    try:
                        doc_app2 = st.session_state["parsed_sigraweb"]
                        df_dest  = st.session_state["merged_df"].copy()
                        df_dest, count, not_found = _merge_app2_items(df_dest, doc_app2['itens'])
                        st.session_state["merged_df"] = df_dest
                        st.success(f"✅ **{count}** adições vinculadas com sucesso.")
                        if not_found:
                            st.warning(f"⚠️ {len(not_found)} adição(ões) não encontradas: {not_found}")
                        with st.expander("📊 Resumo da Vinculação"):
                            _render_totais_grade(df_dest)
                    except Exception as e:
                        st.error(f"Erro na vinculação: {e}")
                        st.code(traceback.format_exc())
                else:
                    st.warning("Carregue os dois arquivos antes de vincular.")

        with reset_col:
            st.markdown('<div style="height:.1rem"></div>', unsafe_allow_html=True)
            rc1, rc2 = st.columns(2)
            with rc1:
                if st.button("🔄 DUIMP", type="secondary", use_container_width=True):
                    st.session_state["parsed_duimp"] = None
                    st.session_state["merged_df"]    = None
                    st.rerun()
            with rc2:
                if st.button("🔄 APP2",  type="secondary", use_container_width=True):
                    st.session_state["parsed_sigraweb"] = None
                    st.rerun()
            if st.button("🗑️ Limpar Tudo", type="secondary", use_container_width=True):
                for k in ["parsed_duimp","parsed_sigraweb","merged_df","last_duimp"]:
                    st.session_state[k] = None
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — CONFERÊNCIA
    # ══════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-title">📋 Conferência e Edição</div>',
                    unsafe_allow_html=True)

        doc_app2 = st.session_state.get("parsed_sigraweb")
        if doc_app2:
            itens_app2 = doc_app2.get('itens', [])

            # Cabeçalho Sigraweb
            if st.session_state["layout_app2"] == "sigraweb":
                cab = doc_app2.get('cabecalho', {})
                with st.expander("📄 Dados do Processo — Sigraweb", expanded=False):
                    dados_cab = {
                        "Campo": ["Número DI","SIGRAWEB ID","Empresa","CNPJ","URF Entrada",
                                  "Via Transporte","País Procedência","Incoterms",
                                  "IDT Conhecimento","IDT Master","Data Embarque",
                                  "Data Chegada","Data Registro","Peso Bruto (kg)",
                                  "Peso Líquido (kg)","Volumes","Embalagem",
                                  "Banco","Agência","Taxa EUR","Taxa USD",
                                  "FOB EUR","FOB BRL","Frete USD","Frete BRL",
                                  "Seguro USD","Seguro BRL","CIF USD","CIF BRL",
                                  "Vlr Aduaneiro USD","Vlr Aduaneiro BRL"],
                        "Valor": [
                            cab.get('numeroDI',''), cab.get('sigraweb',''),
                            cab.get('nomeImportador',''), cab.get('cnpj',''),
                            cab.get('urf',''), cab.get('viaTransporte',''),
                            cab.get('paisProcedencia',''), cab.get('incoterms',''),
                            cab.get('idtConhecimento',''), cab.get('idtMaster',''),
                            cab.get('dataEmbarque',''), cab.get('dataChegada',''),
                            cab.get('dataRegistro',''), cab.get('pesoBruto',''),
                            cab.get('pesoLiquido',''), cab.get('volumes',''),
                            cab.get('embalagem',''), cab.get('banco',''),
                            cab.get('agencia',''), cab.get('taxaEUR',''),
                            cab.get('taxaDolar',''), cab.get('fobEUR',''),
                            cab.get('fobBRL',''), cab.get('freteUSD',''),
                            cab.get('freteBRL',''), cab.get('seguroUSD',''),
                            cab.get('seguroBRL',''), cab.get('cifUSD',''),
                            cab.get('cifBRL',''), cab.get('valorAduaneiroUSD',''),
                            cab.get('valorAduaneiroBRL',''),
                        ]
                    }
                    st.dataframe(pd.DataFrame(dados_cab), use_container_width=True, hide_index=True)

            # Tabela de adições APP2
            layout_label = "Sigraweb" if st.session_state["layout_app2"]=="sigraweb" else "Extrato DUIMP"
            with st.expander(f"📑 Adições Extraídas — {layout_label}", expanded=False):
                if itens_app2:
                    df_app2_view = pd.DataFrame([{
                        'Adição':        it.get('numeroAdicao',''),
                        'Part Number':   it.get('codigo_interno',''),
                        'NCM':           it.get('ncm',''),
                        'Descrição':     str(it.get('descricao', it.get('nome_produto','')))[:60],
                        'País':          it.get('paisOrigem',''),
                        'Qtd Est.':      it.get('quantidade',0),
                        'Qtd Com.':      it.get('quantidade_comercial',0),
                        'Und':           it.get('unidade',''),
                        'Peso Líq.':     it.get('pesoLiq', it.get('peso_liquido',0)),
                        'Vlr Adu. BRL':  it.get('aduaneiro_reais', it.get('valorAduaneiroReal', it.get('local_aduaneiro',0))),
                        'Frete BRL':     it.get('frete_internacional',0),
                        'Seguro BRL':    it.get('seguro_internacional',0),
                        'II %':          it.get('ii_aliquota',0),
                        'II Base R$':    it.get('ii_base_calculo',0),
                        'II R$':         it.get('ii_valor_devido',0),
                        'IPI %':         it.get('ipi_aliquota',0),
                        'IPI R$':        it.get('ipi_valor_devido',0),
                        'PIS %':         it.get('pis_aliquota',0),
                        'PIS R$':        it.get('pis_valor_devido',0),
                        'COFINS %':      it.get('cofins_aliquota',0),
                        'COFINS R$':     it.get('cofins_valor_devido',0),
                        'Total Imp.':    it.get('total_impostos',0),
                    } for it in itens_app2])
                    st.dataframe(df_app2_view, use_container_width=True, height=360)
                    tt1,tt2,tt3,tt4,tt5 = st.columns(5)
                    tt1.metric("Vlr Adu. Total",f"R$ {df_app2_view['Vlr Adu. BRL'].sum():,.2f}")
                    tt2.metric("II Total",      f"R$ {df_app2_view['II R$'].sum():,.2f}")
                    tt3.metric("IPI Total",     f"R$ {df_app2_view['IPI R$'].sum():,.2f}")
                    tt4.metric("PIS Total",     f"R$ {df_app2_view['PIS R$'].sum():,.2f}")
                    tt5.metric("COFINS Total",  f"R$ {df_app2_view['COFINS R$'].sum():,.2f}")
                else:
                    st.info("Nenhum item extraído.")

        # Grade editável principal
        if st.session_state["merged_df"] is not None:
            st.markdown('<div class="section-title">✏️ Grade de Edição — DUIMP + APP2</div>',
                        unsafe_allow_html=True)
            col_config = {
                "numeroAdicao": st.column_config.TextColumn("Item",      width="small",  disabled=True),
                "NUMBER":       st.column_config.TextColumn("Part Number",width="medium"),
                "ncm":          st.column_config.TextColumn("NCM",       width="small",  disabled=True),
                "descricao":    st.column_config.TextColumn("Descrição", width="large",  disabled=True),
                "quantidade":   st.column_config.TextColumn("Qtd Est.",  disabled=True),
                "quantidade_comercial": st.column_config.TextColumn("Qtd Com.", disabled=True),
                "unidade":      st.column_config.TextColumn("Unidade",   disabled=True),
                "pesoLiq":      st.column_config.TextColumn("Peso Líq.", disabled=True),
                "valorTotal":   st.column_config.TextColumn("FOB",       disabled=True),
                "Frete (R$)":   st.column_config.NumberColumn(format="R$ %.2f"),
                "Seguro (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                "Aduaneiro (R$)":st.column_config.NumberColumn("Vlr Adu.",format="R$ %.2f"),
                "II Base (R$)": st.column_config.NumberColumn("II Base",  format="R$ %.2f"),
                "II Alíq. (%)": st.column_config.NumberColumn("II %",    format="%.4f"),
                "II (R$)":      st.column_config.NumberColumn("II R$",   format="R$ %.2f"),
                "IPI Base (R$)":st.column_config.NumberColumn("IPI Base", format="R$ %.2f"),
                "IPI Alíq. (%)":st.column_config.NumberColumn("IPI %",   format="%.4f"),
                "IPI (R$)":     st.column_config.NumberColumn("IPI R$",  format="R$ %.2f"),
                "PIS Base (R$)":st.column_config.NumberColumn("PIS Base", format="R$ %.2f"),
                "PIS Alíq. (%)":st.column_config.NumberColumn("PIS %",   format="%.4f"),
                "PIS (R$)":     st.column_config.NumberColumn("PIS R$",  format="R$ %.2f"),
                "COFINS Base (R$)":st.column_config.NumberColumn("COF Base",format="R$ %.2f"),
                "COFINS Alíq. (%)":st.column_config.NumberColumn("COF %", format="%.4f"),
                "COFINS (R$)":  st.column_config.NumberColumn("COF R$",  format="R$ %.2f"),
            }
            edited_df = st.data_editor(
                st.session_state["merged_df"],
                hide_index=True, column_config=col_config,
                use_container_width=True, height=560
            )
            for tax in ['II','IPI','PIS','COFINS']:
                bc = f"{tax} Base (R$)"; ac = f"{tax} Alíq. (%)"; vc = f"{tax} (R$)"
                if bc in edited_df.columns and ac in edited_df.columns:
                    edited_df[bc] = pd.to_numeric(edited_df[bc], errors='coerce').fillna(0.0)
                    edited_df[ac] = pd.to_numeric(edited_df[ac], errors='coerce').fillna(0.0)
                    edited_df[vc] = edited_df[bc] * (edited_df[ac] / 100.0)
            st.session_state["merged_df"] = edited_df
            st.markdown('<div class="section-title">📊 Totais da Grade</div>',
                        unsafe_allow_html=True)
            _render_totais_grade(edited_df)
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <div class="empty-state-title">Nenhum dado vinculado ainda</div>
                <div class="empty-state-sub">Carregue os arquivos e execute a vinculação na aba Upload</div>
            </div>
            """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — EXPORTAR XML
    # ══════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown('<div class="section-title">⚙️ Configurações do XML Final (Layout 8686)</div>',
                    unsafe_allow_html=True)

        cab_sgw = {}
        if (st.session_state.get("parsed_sigraweb") and
                st.session_state["layout_app2"] == "sigraweb"):
            cab_sgw = st.session_state["parsed_sigraweb"].get("cabecalho", {})

        with st.expander("📅 Datas, Pesos e Locais", expanded=True):
            xc1, xc2, xc3 = st.columns(3, gap="large")
            with xc1:
                st.markdown("**Quantidade & Datas**")
                _vol = cab_sgw.get('volumes', '')
                inp_qtd_volume = st.text_input("Qtd. Volume",        value=str(_vol).zfill(5) if _vol else '00001')
                inp_dt_chegada = st.text_input("Data Chegada",       value=cab_sgw.get('dataChegadaISO','20251120') or '20251120')
                inp_dt_desemb  = st.text_input("Data Desembaraço",   value=cab_sgw.get('dataRegistro','20251124') or '20251124')
                inp_dt_reg     = st.text_input("Data Registro",      value=cab_sgw.get('dataRegistro','20251124') or '20251124')
                inp_dt_emb     = st.text_input("Data Embarque",      value=cab_sgw.get('dataEmbarqueISO','20251025') or '20251025')
            with xc2:
                st.markdown("**Pesos (formato XML)**")
                _pb = DataFormatter.format_quantity(cab_sgw.get('pesoBruto','0'),15) if cab_sgw.get('pesoBruto') else '000000000000000'
                _pl = DataFormatter.format_quantity(cab_sgw.get('pesoLiquido','0'),15) if cab_sgw.get('pesoLiquido') else '000000000000000'
                inp_peso_bruto   = st.text_input("Peso Bruto (XML)",    value=_pb)
                inp_peso_liq     = st.text_input("Peso Líquido (XML)",  value=_pl)
                st.markdown("**Locais (R$ / US$)**")
                inp_loc_desc_dol = st.text_input("Descarga US$",        value="000000000000000")
                inp_loc_desc_rea = st.text_input("Descarga R$",         value="000000000000000")
                inp_loc_emb_dol  = st.text_input("Embarque US$",        value="000000000000000")
                inp_loc_emb_rea  = st.text_input("Embarque R$",         value="000000000000000")
            with xc3:
                st.markdown("**Pagamento & Conhecimento**")
                inp_agencia    = st.text_input("Agência", value=cab_sgw.get('agencia','3715') or '3715')
                inp_banco      = st.text_input("Banco",   value="341")
                inp_idt_conhec = st.text_input("IDT Conhecimento", value=cab_sgw.get('idtConhecimento','CE123456') or 'CE123456')
                inp_idt_master = st.text_input("IDT Master",       value=cab_sgw.get('idtMaster','CE123456') or 'CE123456')
                st.markdown("**Receita 7811**")
                inp_valor_7811 = st.text_input("Valor 7811", value="000000000000000")

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
                    duimp_num = p.header.get("numeroDUIMP","0000").replace("/","-")
                    file_name = f"DUIMP_{duimp_num}_INTEGRADO.xml"
                    st.download_button(
                        "⬇️ Baixar XML", data=xml_bytes, file_name=file_name,
                        mime="text/xml", use_container_width=True
                    )
                    st.success("✅ XML gerado com sucesso!")
                    with st.expander("👁️ Preview XML (3000 primeiros caracteres)"):
                        st.code(xml_bytes.decode('utf-8', errors='ignore')[:3000], language='xml')
                except Exception as e:
                    st.error(f"Erro na geração do XML: {e}")
                    st.code(traceback.format_exc())
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">💾</div>
                <div class="empty-state-title">Nenhum dado disponível</div>
                <div class="empty-state-sub">Realize o upload e a vinculação antes de gerar o XML</div>
            </div>
            """, unsafe_allow_html=True)


# ==============================================================================
# APLICAÇÃO PRINCIPAL
# ==============================================================================
def main():
    load_css()

    st.markdown("""
    <div class="hero">
        <img src="https://raw.githubusercontent.com/DaniloNs-creator/final/7ea6ab2a610ef8f0c11be3c34f046e7ff2cdfc6a/haefele_logo.png"
             class="hero-logo" alt="Häfele">
        <h1 class="hero-title">Sistema de Processamento Unificado 2026</h1>
        <p class="hero-sub">TXT · CT-e · DUIMP — Análise e geração de XML fiscal</p>
        <div class="hero-chips">
            <span class="chip">📄 TXT</span>
            <span class="chip">🚚 CT-e</span>
            <span class="chip">📊 DUIMP</span>
            <span class="chip">🔵 Sigraweb</span>
            <span class="chip">🟠 Extrato DUIMP</span>
            <span class="chip">⚙️ XML 8686</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📄  Processador TXT",
        "🚚  Processador CT-e",
        "📊  Sistema Integrado DUIMP"
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

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — UPLOAD E VINCULAÇÃO
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:

        # ── Seletor de layout do APP2 ──────────────────────────────────────
        st.markdown('<div class="section-title">⚙️ Formato do Arquivo de Tributos (APP2)</div>',
                    unsafe_allow_html=True)

        col_sel1, col_sel2 = st.columns([2, 1])
        with col_sel1:
            layout_choice = st.radio(
                "Selecione o layout do segundo arquivo (APP2):",
                options=["🔵  Sigraweb — Conferência do Processo Detalhado (layout novo)",
                         "🟠  Extrato DUIMP — Itens da DUIMP (layout antigo)"],
                index=0 if st.session_state["layout_app2"] == "sigraweb" else 1,
                key="layout_radio",
                horizontal=False,
            )
            novo_layout = "sigraweb" if layout_choice.startswith("🔵") else "extrato_duimp"
            if novo_layout != st.session_state["layout_app2"]:
                # troca de layout → limpa parser e dados vinculados
                st.session_state["layout_app2"]     = novo_layout
                st.session_state["parsed_sigraweb"] = None
                st.session_state["merged_df"]       = None
                st.rerun()

        with col_sel2:
            layout_badge = ("🔵 Sigraweb" if st.session_state["layout_app2"] == "sigraweb"
                            else "🟠 Extrato DUIMP")
            st.markdown(f"""
            <div class="layout-card layout-card-active">
                <b>Layout ativo:</b><br>
                <span style="font-size:1.15rem;font-weight:700;">{layout_badge}</span>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # ── Upload dos dois arquivos ───────────────────────────────────────
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.info("**Passo 1 —** Extrato DUIMP (Siscomex)")
            file_duimp = st.file_uploader("Arquivo DUIMP (.pdf)", type="pdf", key="u1")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if st.session_state["layout_app2"] == "sigraweb":
                st.info("**Passo 2 —** Sigraweb · Conferência Detalhada")
                label_u2 = "Arquivo Sigraweb (.pdf)"
            else:
                st.info("**Passo 2 —** Extrato DUIMP · Itens da DUIMP")
                label_u2 = "Arquivo Extrato DUIMP (.pdf)"
            file_app2 = st.file_uploader(label_u2, type="pdf", key="u2")
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Processamento APP1 (DUIMP) ────────────────────────────────────
        if file_duimp:
            if (st.session_state["parsed_duimp"] is None or
                    file_duimp.name != getattr(st.session_state.get("last_duimp"), "name", "")):
                try:
                    p = DuimpPDFParser(file_duimp.read())
                    p.preprocess()
                    p.extract_header()
                    p.extract_items()
                    st.session_state["parsed_duimp"] = p
                    st.session_state["last_duimp"]   = file_duimp

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
                        f'<div class="success-box">✅ DUIMP lida — {len(p.items)} adições encontradas.</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"Erro ao ler DUIMP: {e}")

        # ── Processamento APP2 (Sigraweb ou Extrato DUIMP) ────────────────
        if file_app2 and st.session_state["parsed_sigraweb"] is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(file_app2.getvalue())
                tmp_path = tmp.name

            try:
                if st.session_state["layout_app2"] == "sigraweb":
                    parser_app2 = SigrawebPDFParser()
                else:
                    parser_app2 = HafelePDFParser()

                doc_app2 = parser_app2.parse_pdf(tmp_path)
                st.session_state["parsed_sigraweb"] = doc_app2

                qtd_itens = len(doc_app2['itens'])
                if qtd_itens > 0:
                    layout_name = ("Sigraweb" if st.session_state["layout_app2"] == "sigraweb"
                                   else "Extrato DUIMP")
                    st.markdown(
                        f'<div class="success-box">✅ {layout_name} lido — '
                        f'{qtd_itens} itens/adições encontrados.</div>',
                        unsafe_allow_html=True
                    )

                    # Resumo rápido apenas para Sigraweb (tem cabeçalho rico)
                    if st.session_state["layout_app2"] == "sigraweb":
                        cab = doc_app2.get('cabecalho', {})
                        tot = doc_app2.get('totais', {})
                        with st.expander("📋 Resumo do Processo (Sigraweb)", expanded=True):
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Número DI",       cab.get('numeroDI', 'N/A'))
                            c2.metric("Adições",         qtd_itens)
                            c3.metric("Peso Bruto (kg)", cab.get('pesoBruto', 'N/A'))
                            c4.metric("Via Transporte",  cab.get('viaTransporte', 'N/A'))
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("II Total (R$)",       f"R$ {tot.get('total_ii', 0):,.2f}")
                            m2.metric("IPI Total (R$)",      f"R$ {tot.get('total_ipi', 0):,.2f}")
                            m3.metric("PIS Total (R$)",      f"R$ {tot.get('total_pis', 0):,.2f}")
                            m4.metric("COFINS Total (R$)",   f"R$ {tot.get('total_cofins', 0):,.2f}")
                            n1, n2, n3, n4 = st.columns(4)
                            n1.metric("Vlr Adu. Total (R$)", f"R$ {tot.get('total_valor_aduaneiro', 0):,.2f}")
                            n2.metric("Frete Total (R$)",    f"R$ {tot.get('total_frete', 0):,.2f}")
                            n3.metric("Seguro Total (R$)",   f"R$ {tot.get('total_seguro', 0):,.2f}")
                            n4.metric("Peso Líq. Total (kg)",f"{tot.get('peso_liquido_total', 0):,.2f}")
                    else:
                        # Extrato DUIMP — resumo simples
                        tot = doc_app2.get('totais', {})
                        with st.expander("📋 Resumo do Extrato DUIMP", expanded=True):
                            e1, e2, e3, e4 = st.columns(4)
                            e1.metric("Itens",            qtd_itens)
                            e2.metric("II Total (R$)",    f"R$ {tot.get('total_ii', 0):,.2f}")
                            e3.metric("PIS Total (R$)",   f"R$ {tot.get('total_pis', 0):,.2f}")
                            e4.metric("COFINS Total (R$)",f"R$ {tot.get('total_cofins', 0):,.2f}")
                else:
                    st.warning(
                        "O PDF foi lido, mas nenhum item foi detectado automaticamente. "
                        "Verifique se o layout selecionado está correto."
                    )

            except Exception as e:
                st.error(f"Erro ao ler APP2: {e}")
                st.code(traceback.format_exc())
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        # ── Botões de reset ────────────────────────────────────────────────
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            if st.button("🔄 Recarregar DUIMP", type="secondary"):
                st.session_state["parsed_duimp"] = None
                st.session_state["merged_df"]    = None
                st.rerun()
        with col_r2:
            if st.button("🔄 Recarregar APP2", type="secondary"):
                st.session_state["parsed_sigraweb"] = None
                st.rerun()
        with col_r3:
            if st.button("🗑️ Limpar Tudo", type="secondary"):
                for k in ["parsed_duimp", "parsed_sigraweb", "merged_df", "last_duimp"]:
                    st.session_state[k] = None
                st.rerun()

        st.divider()

        # ── Vinculação ─────────────────────────────────────────────────────
        if st.button("🔗 VINCULAR DADOS (Cruzamento Automático)",
                     type="primary", use_container_width=True):
            if st.session_state["merged_df"] is not None and \
               st.session_state["parsed_sigraweb"] is not None:
                try:
                    doc_app2 = st.session_state["parsed_sigraweb"]
                    df_dest  = st.session_state["merged_df"].copy()
                    df_dest, count, not_found = _merge_app2_items(df_dest, doc_app2['itens'])
                    st.session_state["merged_df"] = df_dest
                    st.success(f"✅ **{count}** adições vinculadas com sucesso.")
                    if not_found:
                        st.warning(f"⚠️ {len(not_found)} adição(ões) não encontrada(s) no APP2: {not_found}")

                    # Resumo dos valores vinculados
                    with st.expander("📊 Resumo dos Valores Vinculados", expanded=True):
                        _render_totais_grade(df_dest)
                except Exception as e:
                    st.error(f"Erro na vinculação: {e}")
                    st.code(traceback.format_exc())
            else:
                st.warning("Carregue os dois arquivos antes de vincular.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — CONFERÊNCIA DETALHADA
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-title">📋 Conferência e Edição dos Dados Vinculados</div>',
                    unsafe_allow_html=True)

        # Painel de detalhes do APP2 lido
        doc_app2 = st.session_state.get("parsed_sigraweb")
        if doc_app2:
            itens_app2 = doc_app2.get('itens', [])

            # Cabeçalho Sigraweb (rico) ou info básica Extrato DUIMP
            if st.session_state["layout_app2"] == "sigraweb":
                cab = doc_app2.get('cabecalho', {})
                with st.expander("📄 Dados do Processo — Sigraweb", expanded=False):
                    dados_cab = {
                        "Campo": ["Número DI","SIGRAWEB ID","Empresa","CNPJ","URF Entrada",
                                  "Via Transporte","País Procedência","Incoterms",
                                  "IDT Conhecimento","IDT Master","Data Embarque",
                                  "Data Chegada","Data Registro","Peso Bruto (kg)",
                                  "Peso Líquido (kg)","Volumes","Embalagem",
                                  "Banco","Agência","Taxa EUR","Taxa USD",
                                  "FOB EUR","FOB BRL","Frete USD","Frete BRL",
                                  "Seguro USD","Seguro BRL","CIF USD","CIF BRL",
                                  "Vlr Aduaneiro USD","Vlr Aduaneiro BRL"],
                        "Valor": [
                            cab.get('numeroDI',''), cab.get('sigraweb',''),
                            cab.get('nomeImportador',''), cab.get('cnpj',''),
                            cab.get('urf',''), cab.get('viaTransporte',''),
                            cab.get('paisProcedencia',''), cab.get('incoterms',''),
                            cab.get('idtConhecimento',''), cab.get('idtMaster',''),
                            cab.get('dataEmbarque',''), cab.get('dataChegada',''),
                            cab.get('dataRegistro',''), cab.get('pesoBruto',''),
                            cab.get('pesoLiquido',''), cab.get('volumes',''),
                            cab.get('embalagem',''), cab.get('banco',''),
                            cab.get('agencia',''), cab.get('taxaEUR',''),
                            cab.get('taxaDolar',''), cab.get('fobEUR',''),
                            cab.get('fobBRL',''), cab.get('freteUSD',''),
                            cab.get('freteBRL',''), cab.get('seguroUSD',''),
                            cab.get('seguroBRL',''), cab.get('cifUSD',''),
                            cab.get('cifBRL',''), cab.get('valorAduaneiroUSD',''),
                            cab.get('valorAduaneiroBRL',''),
                        ]
                    }
                    st.dataframe(pd.DataFrame(dados_cab), use_container_width=True, hide_index=True)

            # Tabela de adições do APP2
            with st.expander(
                f"📑 Adições Extraídas — "
                f"{'Sigraweb' if st.session_state['layout_app2']=='sigraweb' else 'Extrato DUIMP'}",
                expanded=False
            ):
                if itens_app2:
                    df_app2_view = pd.DataFrame([{
                        'Adição':          it.get('numeroAdicao', ''),
                        'Part Number':     it.get('codigo_interno', ''),
                        'NCM':             it.get('ncm', ''),
                        'Descrição':       str(it.get('descricao', it.get('nome_produto', '')))[:60],
                        'País Origem':     it.get('paisOrigem', ''),
                        'Qtd Estat.':      it.get('quantidade', 0),
                        'Qtd Comerc.':     it.get('quantidade_comercial', 0),
                        'Unidade':         it.get('unidade', ''),
                        'Peso Líq.(kg)':   it.get('pesoLiq', it.get('peso_liquido', 0)),
                        'Vlr Adu. BRL':    it.get('aduaneiro_reais', it.get('valorAduaneiroReal', it.get('local_aduaneiro', 0))),
                        'Frete BRL':       it.get('frete_internacional', 0),
                        'Seguro BRL':      it.get('seguro_internacional', 0),
                        'II %':            it.get('ii_aliquota', 0),
                        'II Base R$':      it.get('ii_base_calculo', 0),
                        'II R$':           it.get('ii_valor_devido', 0),
                        'IPI %':           it.get('ipi_aliquota', 0),
                        'IPI R$':          it.get('ipi_valor_devido', 0),
                        'PIS %':           it.get('pis_aliquota', 0),
                        'PIS R$':          it.get('pis_valor_devido', 0),
                        'COFINS %':        it.get('cofins_aliquota', 0),
                        'COFINS R$':       it.get('cofins_valor_devido', 0),
                        'Total Impostos':  it.get('total_impostos', 0),
                    } for it in itens_app2])
                    st.dataframe(df_app2_view, use_container_width=True, height=380)
                    # Totais rápidos da tabela APP2
                    tt1, tt2, tt3, tt4, tt5 = st.columns(5)
                    tt1.metric("Vlr Adu. BRL Total", f"R$ {df_app2_view['Vlr Adu. BRL'].sum():,.2f}")
                    tt2.metric("II Total",            f"R$ {df_app2_view['II R$'].sum():,.2f}")
                    tt3.metric("IPI Total",           f"R$ {df_app2_view['IPI R$'].sum():,.2f}")
                    tt4.metric("PIS Total",           f"R$ {df_app2_view['PIS R$'].sum():,.2f}")
                    tt5.metric("COFINS Total",        f"R$ {df_app2_view['COFINS R$'].sum():,.2f}")
                else:
                    st.info("Nenhum item extraído do APP2.")

        # ── Grade de edição principal ──────────────────────────────────────
        if st.session_state["merged_df"] is not None:
            st.markdown('<div class="section-title">✏️ Grade de Edição — DUIMP + APP2 Vinculados</div>',
                        unsafe_allow_html=True)
            col_config = {
                "numeroAdicao": st.column_config.TextColumn("Item",      width="small",  disabled=True),
                "NUMBER":       st.column_config.TextColumn("Part Number", width="medium"),
                "ncm":          st.column_config.TextColumn("NCM",       width="small",  disabled=True),
                "descricao":    st.column_config.TextColumn("Descrição", width="large",  disabled=True),
                "quantidade":   st.column_config.TextColumn("Qtd Est.",  disabled=True),
                "quantidade_comercial": st.column_config.TextColumn("Qtd Com.", disabled=True),
                "unidade":      st.column_config.TextColumn("Unidade",   disabled=True),
                "pesoLiq":      st.column_config.TextColumn("Peso Líq.", disabled=True),
                "valorTotal":   st.column_config.TextColumn("FOB",       disabled=True),
                "Frete (R$)":   st.column_config.NumberColumn(format="R$ %.2f"),
                "Seguro (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                "Aduaneiro (R$)": st.column_config.NumberColumn("Vlr Adu.(R$)", format="R$ %.2f"),
                "II Base (R$)": st.column_config.NumberColumn("II Base",  format="R$ %.2f"),
                "II Alíq. (%)": st.column_config.NumberColumn("II %",    format="%.4f"),
                "II (R$)":      st.column_config.NumberColumn("II R$",   format="R$ %.2f"),
                "IPI Base (R$)":st.column_config.NumberColumn("IPI Base", format="R$ %.2f"),
                "IPI Alíq. (%)":st.column_config.NumberColumn("IPI %",   format="%.4f"),
                "IPI (R$)":     st.column_config.NumberColumn("IPI R$",  format="R$ %.2f"),
                "PIS Base (R$)":st.column_config.NumberColumn("PIS Base", format="R$ %.2f"),
                "PIS Alíq. (%)":st.column_config.NumberColumn("PIS %",   format="%.4f"),
                "PIS (R$)":     st.column_config.NumberColumn("PIS R$",  format="R$ %.2f"),
                "COFINS Base (R$)": st.column_config.NumberColumn("COF Base", format="R$ %.2f"),
                "COFINS Alíq. (%)": st.column_config.NumberColumn("COF %",    format="%.4f"),
                "COFINS (R$)":      st.column_config.NumberColumn("COF R$",   format="R$ %.2f"),
            }
            edited_df = st.data_editor(
                st.session_state["merged_df"],
                hide_index=True, column_config=col_config,
                use_container_width=True, height=600
            )
            # Recalcular impostos em tempo real
            for tax in ['II', 'IPI', 'PIS', 'COFINS']:
                bc = f"{tax} Base (R$)"; ac = f"{tax} Alíq. (%)"; vc = f"{tax} (R$)"
                if bc in edited_df.columns and ac in edited_df.columns:
                    edited_df[bc] = pd.to_numeric(edited_df[bc], errors='coerce').fillna(0.0)
                    edited_df[ac] = pd.to_numeric(edited_df[ac], errors='coerce').fillna(0.0)
                    edited_df[vc] = edited_df[bc] * (edited_df[ac] / 100.0)
            st.session_state["merged_df"] = edited_df

            st.markdown('<div class="section-title">📊 Totais da Grade</div>', unsafe_allow_html=True)
            _render_totais_grade(edited_df)
        else:
            st.info("Realize o upload e a vinculação na aba **Upload e Vinculação**.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — EXPORTAR XML
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown('<div class="section-title">⚙️ Configurações do XML Final</div>',
                    unsafe_allow_html=True)

        # Preenche automaticamente com dados do Sigraweb quando disponível
        cab_sgw = {}
        if (st.session_state.get("parsed_sigraweb") and
                st.session_state["layout_app2"] == "sigraweb"):
            cab_sgw = st.session_state["parsed_sigraweb"].get("cabecalho", {})

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("**📦 Quantidade**")
            _vol = cab_sgw.get('volumes', '')
            inp_qtd_volume = st.text_input(
                "Quantidade Volume",
                value=str(_vol).zfill(5) if _vol else '00001',
                help="Preenche <quantidadeVolume>"
            )
            st.markdown("**📅 Datas (YYYYMMDD)**")
            inp_dt_chegada = st.text_input("Data Chegada",    value=cab_sgw.get('dataChegadaISO',  '20251120') or '20251120')
            inp_dt_desemb  = st.text_input("Data Desembaraço",value=cab_sgw.get('dataRegistro',    '20251124') or '20251124')
            inp_dt_reg     = st.text_input("Data Registro",   value=cab_sgw.get('dataRegistro',    '20251124') or '20251124')
            inp_dt_emb     = st.text_input("Data Embarque",   value=cab_sgw.get('dataEmbarqueISO', '20251025') or '20251025')

        with c2:
            st.markdown("**⚖️ Pesos (formato XML)**")
            _pb = DataFormatter.format_quantity(cab_sgw.get('pesoBruto','0'),  15) if cab_sgw.get('pesoBruto')  else '000000000000000'
            _pl = DataFormatter.format_quantity(cab_sgw.get('pesoLiquido','0'),15) if cab_sgw.get('pesoLiquido') else '000000000000000'
            inp_peso_bruto = st.text_input("Peso Bruto (XML)",   value=_pb)
            inp_peso_liq   = st.text_input("Peso Líquido (XML)", value=_pl)
            st.markdown("**📍 Locais (R$ / US$)**")
            inp_loc_desc_dol = st.text_input("Local Descarga US$", value="000000000000000")
            inp_loc_desc_rea = st.text_input("Local Descarga R$",  value="000000000000000")
            inp_loc_emb_dol  = st.text_input("Local Embarque US$", value="000000000000000")
            inp_loc_emb_rea  = st.text_input("Local Embarque R$",  value="000000000000000")

        with c3:
            st.markdown("**🏦 Pagamento / Siscomex**")
            inp_agencia = st.text_input("Agência", value=cab_sgw.get('agencia','3715') or '3715')
            inp_banco   = st.text_input("Banco",   value="341")
            st.markdown("---")
            st.markdown("**🔖 Conhecimento de Carga**")
            inp_idt_conhec = st.text_input("IDT Conhecimento", value=cab_sgw.get('idtConhecimento','CE123456') or 'CE123456')
            inp_idt_master = st.text_input("IDT Master",       value=cab_sgw.get('idtMaster','CE123456')       or 'CE123456')
            st.markdown("---")
            st.markdown("**💰 Receita 7811**")
            inp_valor_7811 = st.text_input("Valor Receita 7811", value="000000000000000")

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
                        data=xml_bytes, file_name=file_name, mime="text/xml"
                    )
                    st.success("✅ XML gerado com sucesso!")

                    with st.expander("👁️ Preview XML (primeiros 3000 caracteres)"):
                        st.code(xml_bytes.decode('utf-8', errors='ignore')[:3000], language='xml')

                except Exception as e:
                    st.error(f"Erro na geração do XML: {e}")
                    st.code(traceback.format_exc())
        else:
            st.warning("Realize o upload e a vinculação antes de gerar o XML.")


# ==============================================================================
# APLICAÇÃO PRINCIPAL
# ==============================================================================
def main():
    load_css()

    st.markdown("""
    <div class="hero">
        <img src="https://raw.githubusercontent.com/DaniloNs-creator/final/7ea6ab2a610ef8f0c11be3c34f046e7ff2cdfc6a/haefele_logo.png"
             class="hero-logo" alt="Häfele Logo">
        <h1 class="hero-title">Sistema de Processamento Unificado 2026</h1>
        <p class="hero-sub">Processamento de TXT · CT-e · DUIMP — Análise e geração de XML fiscal</p>
        <div class="hero-chips">
            <span class="chip">📄 TXT</span>
            <span class="chip">🚚 CT-e</span>
            <span class="chip">📊 DUIMP</span>
            <span class="chip">🔵 Sigraweb</span>
            <span class="chip">🟠 Extrato DUIMP</span>
            <span class="chip">⚙️ XML 8686</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📄  Processador TXT",
        "🚚  Processador CT-e",
        "📊  Sistema Integrado DUIMP"
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


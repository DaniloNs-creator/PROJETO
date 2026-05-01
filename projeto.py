import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO, BytesIO
import re
import os
import tempfile
from collections import defaultdict

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Analisador SPED – EFD Contribuições & ICMS/IPI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CST TABLES
# ──────────────────────────────────────────────
CST_PIS_COFINS = {
    "01": ("Operação Tributável – BC Valor Operação", True),
    "02": ("Operação Tributável – BC Valor Operação – Alíquota Diferenciada", True),
    "03": ("Operação Tributável – BC Qtd Vendida × Alíquota por Unidade", True),
    "04": ("Operação Tributável Monofásica – Revenda", False),
    "05": ("Operação Tributável Substituição Tributária", False),
    "06": ("Operação Tributável – Alíquota Zero", False),
    "07": ("Operação Isenta da Contribuição", False),
    "08": ("Operação Sem Incidência da Contribuição", False),
    "09": ("Operação com Suspensão da Contribuição", False),
    "49": ("Outras Operações de Saída", False),
    "50": ("Op. com Direito a Crédito – Vinculada Exclus. Receita Tributada no Mercado Interno", True),
    "51": ("Op. com Direito a Crédito – Vinculada Exclus. Receita Não Tributada no Mercado Interno", True),
    "52": ("Op. com Direito a Crédito – Vinculada Exclus. Receita de Exportação", True),
    "53": ("Op. com Direito a Crédito – Vinculada a Receitas Tributadas e Não Tributadas no Mercado Interno", True),
    "54": ("Op. com Direito a Crédito – Vinculada a Receitas Tributadas no Mercado Interno e de Exportação", True),
    "55": ("Op. com Direito a Crédito – Vinculada a Receitas Não Tributadas no Mercado Interno e de Exportação", True),
    "56": ("Op. com Direito a Crédito – Vinculada a Receitas Tributadas e Não Tributadas no Mercado Interno e de Exportação", True),
    "60": ("Crédito Presumido – Op. Aquisição Vinculada Exclus. Receita Tributada no Mercado Interno", True),
    "61": ("Crédito Presumido – Op. Aquisição Vinculada Exclus. Receita Não Tributada no Mercado Interno", True),
    "62": ("Crédito Presumido – Op. Aquisição Vinculada Exclus. Receita de Exportação", True),
    "63": ("Crédito Presumido – Op. Aquisição Vinculada a Receitas Tributadas e Não Tributadas no Mercado Interno", True),
    "64": ("Crédito Presumido – Op. Aquisição Vinculada a Receitas Tributadas no Mercado Interno e de Exportação", True),
    "65": ("Crédito Presumido – Op. Aquisição Vinculada a Receitas Não Tributadas no Mercado Interno e de Exportação", True),
    "66": ("Crédito Presumido – Op. Aquisição Vinculada a Receitas Tributadas e Não Tributadas no Mercado Interno e de Exportação", True),
    "67": ("Crédito Presumido – Outras Operações", True),
    "70": ("Operação de Aquisição Sem Direito a Crédito", False),
    "71": ("Operação de Aquisição com Isenção", False),
    "72": ("Operação de Aquisição com Suspensão", False),
    "73": ("Operação de Aquisição a Alíquota Zero", False),
    "74": ("Operação de Aquisição Sem Incidência da Contribuição", False),
    "75": ("Operação de Aquisição por Substituição Tributária", False),
    "98": ("Outras Operações de Entrada", False),
    "99": ("Outras Operações", False),
}

CST_ICMS = {
    "00": ("Tributada Integralmente", True),
    "10": ("Tributada e com Cobrança de ICMS por ST", True),
    "20": ("Com Redução de BC", True),
    "30": ("Isenta ou Não Tributada e com Cobrança de ICMS por ST", False),
    "40": ("Isenta", False),
    "41": ("Não Tributada", False),
    "50": ("Com Suspensão", False),
    "51": ("Com Diferimento", True),
    "60": ("ICMS Cobrado Anteriormente por ST", False),
    "70": ("Com Redução de BC e Cobrança de ICMS por ST", True),
    "90": ("Outras", False),
}

CST_IPI = {
    # Entradas
    "00": ("Entrada com Recuperação de Crédito", True),
    "01": ("Entrada Tributada com Alíquota Zero", False),
    "02": ("Entrada Isenta", False),
    "03": ("Entrada Não Tributada", False),
    "04": ("Entrada Imune", False),
    "05": ("Entrada com Suspensão", False),
    "49": ("Outras Entradas", False),
    # Saídas
    "50": ("Saída Tributada", True),
    "51": ("Saída Tributável com Alíquota Zero", False),
    "52": ("Saída Isenta", False),
    "53": ("Saída Não Tributada", False),
    "54": ("Saída Imune", False),
    "55": ("Saída com Suspensão", False),
    "99": ("Outras Saídas", False),
}

# ──────────────────────────────────────────────
# PARSER ROBUSTO (sem depender de sped lib para leitura)
# ──────────────────────────────────────────────

def parse_sped_file(content: str):
    """Parse SPED file content into a dict of {registro: [list of dicts]}."""
    registros = defaultdict(list)
    linhas_raw = {}  # reg_key -> list of raw lines
    errors = []

    lines = content.splitlines()
    total = len(lines)

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        # Remove leading/trailing pipes if present
        if line.startswith("|") and line.endswith("|"):
            parts = line[1:-1].split("|")
        elif "|" in line:
            parts = line.split("|")
            if parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]
        else:
            continue

        if not parts:
            continue

        reg = parts[0].strip().upper()
        if not re.match(r'^[0-9A-Z]{4,5}$', reg):
            continue

        registros[reg].append(parts)
        if reg not in linhas_raw:
            linhas_raw[reg] = []
        linhas_raw[reg].append(i + 1)

    return registros, linhas_raw, errors


def detect_tipo(registros):
    """Detect if file is EFD Contribuições (PIS/COFINS) or ICMS/IPI."""
    # EFD Contribuições has blocks C, D, F, I, M, P, 1, A
    # EFD ICMS/IPI has blocks B, C, D, E, G, H, K
    contrib_blocos = {"M100", "M200", "M300", "M400", "P100", "F100", "F200"}
    icms_blocos = {"E100", "E110", "E500", "G100", "H010", "K100"}

    contrib_score = sum(1 for r in contrib_blocos if r in registros)
    icms_score = sum(1 for r in icms_blocos if r in registros)

    if contrib_score > icms_score:
        return "EFD Contribuições (PIS/COFINS)"
    elif icms_score > contrib_score:
        return "EFD ICMS/IPI"
    else:
        return "Indeterminado"


# ──────────────────────────────────────────────
# FIELD MAPS for key registers
# ──────────────────────────────────────────────

# EFD CONTRIBUIÇÕES field maps
CAMPOS_CONTRIB = {
    "0000": ["REG","COD_VER","TIPO_ESCRIT","IND_SIT_ESP","NUM_REC_ANTERIOR","DT_INI","DT_FIN","NOME","CNPJ","UF","COD_MUN","SUFRAMA","IND_NAT_PJ","IND_ATIV"],
    "C100": ["REG","IND_OPER","IND_EMIT","COD_PART","COD_MOD","COD_SIT","SER","NUM_DOC","CHAVE_NFE","DT_DOC","DT_EXE_FEC","VL_DOC","IND_PGTO","VL_DESC","VL_ABAT_NT","VL_MERC","IND_FRT","VL_FRT","VL_SEG","VL_OUT_DA","VL_BC_ICMS","VL_ICMS","VL_BC_ICMS_ST","VL_ICMS_ST","VL_IPI","VL_PIS","VL_COFINS","VL_PIS_ST","VL_COFINS_ST"],
    "C170": ["REG","NUM_ITEM","COD_ITEM","DESCR_COMPL","QTD","UNID","VL_ITEM","VL_DESC","IND_MOV","CST_ICMS","CFOP","COD_NAT","VL_BC_ICMS","ALIQ_ICMS","VL_ICMS","VL_BC_ICMS_ST","ALIQ_ST","VL_ICMS_ST","IND_APUR","CST_IPI","COD_ENQ","VL_BC_IPI","ALIQ_IPI","VL_IPI","CST_PIS","VL_BC_PIS","ALIQ_PIS","QUANT_BC_PIS","ALIQ_PIS_QUANT","VL_PIS","CST_COFINS","VL_BC_COFINS","ALIQ_COFINS","QUANT_BC_COFINS","ALIQ_COFINS_QUANT","VL_COFINS","COD_CTA"],
    "C175": ["REG","CFOP","VL_OPR","VL_DESC_GLB","VL_BC_ICMS","VL_ICMS","VL_BC_ICMS_ST","VL_ICMS_ST","CST_PIS","VL_BC_PIS","ALIQ_PIS","QUANT_BC_PIS","ALIQ_PIS_QUANT","VL_PIS","CST_COFINS","VL_BC_COFINS","ALIQ_COFINS","QUANT_BC_COFINS","ALIQ_COFINS_QUANT","VL_COFINS","COD_CTA"],
    "C180": ["REG","COD_CRED","IND_ORIG_CRED","CFOP","QUANT_BC_PIS","ALIQ_PIS_QUANT","VL_BC_PIS","ALIQ_PIS","VL_PIS","QUANT_BC_COFINS","ALIQ_COFINS_QUANT","VL_BC_COFINS","ALIQ_COFINS","VL_COFINS","COD_CTA"],
    "C190": ["REG","CST_ICMS","CFOP","ALIQ_ICMS","VL_OPR","VL_BC_ICMS","VL_ICMS","VL_BC_ICMS_ST","VL_ICMS_ST","VL_RED_BC","VL_IPI","COD_OBS"],
    "D100": ["REG","IND_OPER","IND_EMIT","COD_PART","COD_MOD","COD_SIT","SER","SUB","NUM_DOC","CHV_CTE","DT_DOC","DT_A_P","TP_CT_e","CHVE_CTE","VL_DOC","VL_DESC","IND_FRT","VL_SERV","VL_BC_ICMS","VL_ICMS","VL_NT","VL_PIS","VL_COFINS","CST_PIS","VL_BC_PIS","ALIQ_PIS","VL_PIS_EF","CST_COFINS","VL_BC_COFINS","ALIQ_COFINS","VL_COFINS_EF"],
    "F100": ["REG","IND_OPER","COD_PART","COD_ITEM","DT_OPER","VL_OPER","CST_PIS","VL_BC_PIS","ALIQ_PIS","VL_PIS","CST_COFINS","VL_BC_COFINS","ALIQ_COFINS","VL_COFINS","NAT_BC_CRED","IND_ORIG_CRED","COD_CTA","COD_CCUS"],
    "M100": ["REG","COD_CRED","IND_CRED_ORI","VL_BC_PIS","ALIQ_PIS","QUANT_BC_PIS","VL_CRED","VL_AJUS_ACRES","VL_AJUS_REDUC","VL_CRED_DIF","VL_CRED_DISP","IND_DESC_CRED","VL_CRED_DESC","SLD_CRED"],
    "M200": ["REG","VL_TOT_CONT_NC_PER","VL_TOT_CRED_DESC","VL_TOT_CONT_NC_DEV","VL_RET_NC","VL_OUT_DED_NC","VL_CONT_NC_REC","VL_TOT_CONT_CUM_PER","VL_RET_CUM","VL_OUT_DED_CUM","VL_CONT_CUM_REC","VL_TOT_CONT_REC"],
    "M500": ["REG","COD_CRED","IND_CRED_ORI","VL_BC_COFINS","ALIQ_COFINS","QUANT_BC_COFINS","VL_CRED","VL_AJUS_ACRES","VL_AJUS_REDUC","VL_CRED_DIF","VL_CRED_DISP","IND_DESC_CRED","VL_CRED_DESC","SLD_CRED"],
    "M600": ["REG","VL_TOT_CONT_NC_PER","VL_TOT_CRED_DESC","VL_TOT_CONT_NC_DEV","VL_RET_NC","VL_OUT_DED_NC","VL_CONT_NC_REC","VL_TOT_CONT_CUM_PER","VL_RET_CUM","VL_OUT_DED_CUM","VL_CONT_CUM_REC","VL_TOT_CONT_REC"],
}

# EFD ICMS/IPI field maps
CAMPOS_ICMS = {
    "0000": ["REG","COD_VER","TIPO_ESCRIT","IND_SIT_ESP","NUM_REC_ANTERIOR","DT_INI","DT_FIN","NOME","CNPJ","CPF","UF","IE","COD_MUN","IM","SUFRAMA","IND_PERFIL","IND_ATIV"],
    "C100": ["REG","IND_OPER","IND_EMIT","COD_PART","COD_MOD","COD_SIT","SER","NUM_DOC","CHV_NFE","DT_DOC","DT_E_S","VL_DOC","IND_PGTO","VL_DESC","VL_ABAT_NT","VL_MERC","IND_FRT","VL_FRT","VL_SEG","VL_OUT_DA","VL_BC_ICMS","VL_ICMS","VL_BC_ICMS_ST","VL_ICMS_ST","VL_IPI","VL_PIS","VL_COFINS","VL_PIS_ST","VL_COFINS_ST"],
    "C170": ["REG","NUM_ITEM","COD_ITEM","DESCR_COMPL","QTD","UNID","VL_ITEM","VL_DESC","IND_MOV","CST_ICMS","CFOP","COD_NAT","VL_BC_ICMS","ALIQ_ICMS","VL_ICMS","VL_BC_ICMS_ST","ALIQ_ST","VL_ICMS_ST","IND_APUR","CST_IPI","COD_ENQ","VL_BC_IPI","ALIQ_IPI","VL_IPI","CST_PIS","VL_BC_PIS","ALIQ_PIS","QUANT_BC_PIS","ALIQ_PIS_QUANT","VL_PIS","CST_COFINS","VL_BC_COFINS","ALIQ_COFINS","QUANT_BC_COFINS","ALIQ_COFINS_QUANT","VL_COFINS","COD_CTA"],
    "C190": ["REG","CST_ICMS","CFOP","ALIQ_ICMS","VL_OPR","VL_BC_ICMS","VL_ICMS","VL_BC_ICMS_ST","VL_ICMS_ST","VL_RED_BC","VL_IPI","COD_OBS"],
    "E100": ["REG","DT_INI","DT_FIN"],
    "E110": ["REG","VL_TOT_DEBITOS","VL_AJ_DEBITOS","VL_TOT_AJ_DEBITOS","VL_ESTORNOS_CRED","VL_TOT_CREDITOS","VL_AJ_CREDITOS","VL_TOT_AJ_CREDITOS","VL_ESTORNOS_DEB","VL_SLD_CREDOR_ANT","VL_SLD_APURADO","VL_TOT_DED","VL_ICMS_RECOLHER","VL_SLD_CREDOR_TRANSPORTAR","DEB_ESP"],
    "E500": ["REG","IND_APUR"],
    "E510": ["REG","CFOP","CST_IPI","ALIQ_IPI","VL_OPR","VL_BC_IPI","VL_IPI"],
    "E520": ["REG","VL_SD_ANT_IPI","VL_DEB_IPI","VL_CRED_IPI","VL_OD_IPI","VL_OC_IPI","VL_SC_IPI","VL_SD_IPI"],
    "H010": ["REG","DT_INV","VL_INV"],
    "H020": ["REG","CST_ICMS","BC_ICMS","VL_ICMS"],
    "K100": ["REG","DT_INI","DT_FIN"],
    "K200": ["REG","DT_EST","COD_ITEM","QTD","IND_EST","COD_PART"],
}

# ──────────────────────────────────────────────
# VALIDATION ENGINE
# ──────────────────────────────────────────────

def to_float(val):
    try:
        return float(str(val).replace(",", ".").strip())
    except:
        return None


def validate_cst_pis_cofins(row: dict, reg_name: str):
    """Validate PIS/COFINS CST rules."""
    issues = []
    for tributo in ["PIS", "COFINS"]:
        cst_field = f"CST_{tributo}"
        bc_field = f"VL_BC_{tributo}"
        aliq_field = f"ALIQ_{tributo}"
        vl_field = f"VL_{tributo}"
        quant_bc = f"QUANT_BC_{tributo}"
        aliq_quant = f"ALIQ_{tributo}_QUANT"

        cst = str(row.get(cst_field, "")).strip().zfill(2)
        if not cst or cst == "00":
            continue

        cst_info = CST_PIS_COFINS.get(cst)
        if not cst_info:
            issues.append({
                "registro": reg_name,
                "campo": cst_field,
                "cst": cst,
                "tipo": "CST Inválido",
                "detalhe": f"CST {cst} não encontrado na tabela oficial",
                "gravidade": "ERRO"
            })
            continue

        descricao, requer_tributo = cst_info

        if requer_tributo:
            # CST that requires BC, ALIQ, VL
            bc = to_float(row.get(bc_field, ""))
            aliq = to_float(row.get(aliq_field, ""))
            vl = to_float(row.get(vl_field, ""))

            # For CST 03: quantity-based
            if cst == "03":
                quant = to_float(row.get(quant_bc, ""))
                aliq_q = to_float(row.get(aliq_quant, ""))
                if not quant or quant == 0:
                    issues.append({"registro": reg_name, "campo": quant_bc, "cst": cst, "tipo": "BC Quantidade Ausente", "detalhe": f"CST {cst} ({descricao}) requer {quant_bc} preenchido", "gravidade": "ERRO"})
                if not aliq_q or aliq_q == 0:
                    issues.append({"registro": reg_name, "campo": aliq_quant, "cst": cst, "tipo": "Alíquota Quantidade Ausente", "detalhe": f"CST {cst} requer {aliq_quant} preenchido", "gravidade": "ERRO"})
                if vl is None or vl == 0:
                    issues.append({"registro": reg_name, "campo": vl_field, "cst": cst, "tipo": "Valor Ausente", "detalhe": f"CST {cst} requer {vl_field} preenchido", "gravidade": "ERRO"})
            else:
                if bc is None or bc == 0:
                    issues.append({"registro": reg_name, "campo": bc_field, "cst": cst, "tipo": "Base de Cálculo Ausente", "detalhe": f"CST {cst} ({descricao}) requer {bc_field} preenchido", "gravidade": "ERRO"})
                if aliq is None or aliq == 0:
                    issues.append({"registro": reg_name, "campo": aliq_field, "cst": cst, "tipo": "Alíquota Ausente", "detalhe": f"CST {cst} requer {aliq_field} preenchido", "gravidade": "ERRO"})
                if vl is None or vl == 0:
                    issues.append({"registro": reg_name, "campo": vl_field, "cst": cst, "tipo": "Valor Ausente", "detalhe": f"CST {cst} requer {vl_field} preenchido", "gravidade": "ERRO"})

                # Cross-check: BC * ALIQ% ~ VL (tolerance 0.10)
                if bc and aliq and vl:
                    calc = round(bc * aliq / 100, 2)
                    if abs(calc - vl) > 0.10:
                        issues.append({"registro": reg_name, "campo": vl_field, "cst": cst, "tipo": "Divergência de Cálculo", "detalhe": f"{tributo}: BC({bc}) × Alíq({aliq}%) = {calc} ≠ {vl} (dif={abs(calc-vl):.2f})", "gravidade": "ALERTA"})
        else:
            # CST without tax – BC, ALIQ and VL should be zero/empty
            bc = to_float(row.get(bc_field, ""))
            vl = to_float(row.get(vl_field, ""))
            if bc and bc != 0:
                issues.append({"registro": reg_name, "campo": bc_field, "cst": cst, "tipo": "Campo Indevido", "detalhe": f"CST {cst} ({descricao}) não gera débito/crédito, mas {bc_field}={bc}", "gravidade": "ALERTA"})

    return issues


def validate_cst_icms(row: dict, reg_name: str):
    """Validate ICMS CST rules."""
    issues = []
    cst = str(row.get("CST_ICMS", "")).strip().zfill(2)
    if not cst or cst == "00" and "VL_ICMS" not in row:
        return issues

    cst_info = CST_ICMS.get(cst)
    if cst and cst != "" and not cst_info:
        issues.append({"registro": reg_name, "campo": "CST_ICMS", "cst": cst, "tipo": "CST Inválido", "detalhe": f"CST ICMS {cst} não reconhecido", "gravidade": "ERRO"})
        return issues

    if cst_info:
        descricao, requer_tributo = cst_info
        if requer_tributo:
            bc = to_float(row.get("VL_BC_ICMS", ""))
            aliq = to_float(row.get("ALIQ_ICMS", ""))
            vl = to_float(row.get("VL_ICMS", ""))

            if not bc:
                issues.append({"registro": reg_name, "campo": "VL_BC_ICMS", "cst": cst, "tipo": "BC ICMS Ausente", "detalhe": f"CST {cst} ({descricao}) requer VL_BC_ICMS", "gravidade": "ERRO"})
            if not aliq:
                issues.append({"registro": reg_name, "campo": "ALIQ_ICMS", "cst": cst, "tipo": "Alíquota ICMS Ausente", "detalhe": f"CST {cst} requer ALIQ_ICMS", "gravidade": "ERRO"})
            if bc and aliq and vl and vl > 0:
                calc = round(bc * aliq / 100, 2)
                if abs(calc - vl) > 0.10:
                    issues.append({"registro": reg_name, "campo": "VL_ICMS", "cst": cst, "tipo": "Divergência Cálculo ICMS", "detalhe": f"BC({bc}) × Alíq({aliq}%) = {calc} ≠ {vl}", "gravidade": "ALERTA"})
    return issues


def validate_cst_ipi(row: dict, reg_name: str):
    """Validate IPI CST rules."""
    issues = []
    cst = str(row.get("CST_IPI", "")).strip().zfill(2)
    if not cst:
        return issues

    cst_info = CST_IPI.get(cst)
    if not cst_info:
        if cst not in ("", "00"):
            issues.append({"registro": reg_name, "campo": "CST_IPI", "cst": cst, "tipo": "CST IPI Inválido", "detalhe": f"CST IPI {cst} não reconhecido", "gravidade": "ERRO"})
        return issues

    descricao, requer_tributo = cst_info
    if requer_tributo:
        bc = to_float(row.get("VL_BC_IPI", ""))
        aliq = to_float(row.get("ALIQ_IPI", ""))
        vl = to_float(row.get("VL_IPI", ""))
        if not bc:
            issues.append({"registro": reg_name, "campo": "VL_BC_IPI", "cst": cst, "tipo": "BC IPI Ausente", "detalhe": f"CST IPI {cst} ({descricao}) requer VL_BC_IPI", "gravidade": "ERRO"})
        if not aliq:
            issues.append({"registro": reg_name, "campo": "ALIQ_IPI", "cst": cst, "tipo": "Alíquota IPI Ausente", "detalhe": f"CST IPI {cst} requer ALIQ_IPI", "gravidade": "ERRO"})
        if bc and aliq and vl and vl > 0:
            calc = round(bc * aliq / 100, 2)
            if abs(calc - vl) > 0.10:
                issues.append({"registro": reg_name, "campo": "VL_IPI", "cst": cst, "tipo": "Divergência Cálculo IPI", "detalhe": f"BC({bc}) × Alíq({aliq}%) = {calc} ≠ {vl}", "gravidade": "ALERTA"})
    return issues


def full_validation(registros: dict, campos_map: dict):
    """Run full validation across all registers."""
    all_issues = []
    regs_to_validate = ["C170", "C175", "D100", "F100", "C190", "E510"]

    for reg_name in regs_to_validate:
        if reg_name not in registros:
            continue
        campos = campos_map.get(reg_name, [])
        for i, row_parts in enumerate(registros[reg_name]):
            row = {}
            for j, campo in enumerate(campos):
                row[campo] = row_parts[j] if j < len(row_parts) else ""

            row["_linha"] = i + 1

            issues_pis = validate_cst_pis_cofins(row, f"{reg_name} (linha {i+1})")
            issues_icms = validate_cst_icms(row, f"{reg_name} (linha {i+1})")
            issues_ipi = validate_cst_ipi(row, f"{reg_name} (linha {i+1})")

            all_issues.extend(issues_pis)
            all_issues.extend(issues_icms)
            all_issues.extend(issues_ipi)

    return all_issues


# ──────────────────────────────────────────────
# DATAFRAME BUILDER
# ──────────────────────────────────────────────

def build_df(registros: dict, reg_name: str, campos_map: dict):
    if reg_name not in registros:
        return pd.DataFrame()
    campos = campos_map.get(reg_name, [])
    rows = []
    for parts in registros[reg_name]:
        row = {}
        for j, campo in enumerate(campos):
            row[campo] = parts[j] if j < len(parts) else ""
        rows.append(row)
    return pd.DataFrame(rows)


def to_excel_bytes(dfs: dict):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in dfs.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet[:31], index=False)
    return buf.getvalue()


def rebuild_sped_line(parts):
    return "|" + "|".join(parts) + "|"


# ──────────────────────────────────────────────
# SIDEBAR & STATE
# ──────────────────────────────────────────────

def init_state():
    if "registros" not in st.session_state:
        st.session_state.registros = {}
    if "linhas_raw" not in st.session_state:
        st.session_state.linhas_raw = {}
    if "tipo" not in st.session_state:
        st.session_state.tipo = ""
    if "campos_map" not in st.session_state:
        st.session_state.campos_map = {}
    if "issues" not in st.session_state:
        st.session_state.issues = []
    if "content_lines" not in st.session_state:
        st.session_state.content_lines = []
    if "edited_registros" not in st.session_state:
        st.session_state.edited_registros = {}

init_state()

# ──────────────────────────────────────────────
# STYLES
# ──────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1a1f2e; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.metric-card {
    background: linear-gradient(135deg, #1e3a5f 0%, #0f2847 100%);
    border-radius: 12px;
    padding: 16px;
    border-left: 4px solid #3b82f6;
    margin-bottom: 8px;
}
.erro-card { border-left-color: #ef4444; background: linear-gradient(135deg,#3b1f1f,#1f0f0f); }
.alerta-card { border-left-color: #f59e0b; background: linear-gradient(135deg,#3b2f1f,#1f1a0f); }
.ok-card { border-left-color: #10b981; background: linear-gradient(135deg,#1f3b2f,#0f1f1a); }
.badge-erro { background:#ef4444; color:#fff; border-radius:8px; padding:2px 8px; font-size:12px; font-weight:bold; }
.badge-alerta { background:#f59e0b; color:#000; border-radius:8px; padding:2px 8px; font-size:12px; font-weight:bold; }
.section-header { font-size:1.3rem; font-weight:700; color:#3b82f6; border-bottom:2px solid #3b82f6; padding-bottom:6px; margin-bottom:16px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────

with st.sidebar:
    st.image("https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/importacao-e-exportacao/logistica/svgs/brasao_republica_federal_do_brasil.svg/@@images/image.svg", width=60)
    st.title("📊 SPED Analyzer")
    st.caption("EFD Contribuições | ICMS/IPI")
    st.divider()

    uploaded = st.file_uploader(
        "📂 Importar Arquivo TXT (SPED)",
        type=["txt"],
        help="Arraste o arquivo .txt gerado pelo sistema contábil"
    )

    if uploaded:
        with st.spinner("Lendo arquivo..."):
            content = uploaded.read().decode("latin-1", errors="replace")
            lines = content.splitlines()
            registros, linhas_raw, errs = parse_sped_file(content)
            tipo = detect_tipo(registros)
            campos_map = CAMPOS_CONTRIB if "PIS/COFINS" in tipo else CAMPOS_ICMS
            issues = full_validation(registros, campos_map)

            st.session_state.registros = registros
            st.session_state.linhas_raw = linhas_raw
            st.session_state.tipo = tipo
            st.session_state.campos_map = campos_map
            st.session_state.issues = issues
            st.session_state.content_lines = lines
            st.session_state.edited_registros = {k: [list(r) for r in v] for k, v in registros.items()}

        st.success(f"✅ Arquivo carregado!")
        st.info(f"**Tipo:** {tipo}")

    st.divider()
    nav = st.radio(
        "Navegação",
        ["🏠 Dashboard", "🔍 Analisar Blocos", "⚠️ Validações", "✏️ Editor de Registros", "📤 Exportar"],
        label_visibility="collapsed"
    )

# ──────────────────────────────────────────────
# MAIN CONTENT
# ──────────────────────────────────────────────

if not st.session_state.registros:
    st.markdown("""
    <div style='text-align:center; padding: 80px 20px;'>
        <h1 style='color:#3b82f6;'>📊 SPED Analyzer Pro</h1>
        <p style='font-size:1.2rem; color:#94a3b8;'>Análise e Validação de EFD Contribuições e ICMS/IPI</p>
        <br>
        <div style='background:#1e3a5f; border-radius:16px; padding:32px; max-width:600px; margin:auto; border:1px solid #3b82f6;'>
            <h3 style='color:#60a5fa;'>Como usar:</h3>
            <p style='color:#cbd5e1; text-align:left;'>
            1️⃣ Importe seu arquivo .txt SPED na barra lateral<br><br>
            2️⃣ O sistema detecta automaticamente o tipo (EFD Contribuições ou ICMS/IPI)<br><br>
            3️⃣ Explore os blocos, valide os CSTs e corrija inconsistências<br><br>
            4️⃣ Exporte o arquivo corrigido no padrão PVA Validador
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

registros = st.session_state.registros
campos_map = st.session_state.campos_map
issues = st.session_state.issues
tipo = st.session_state.tipo

# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

if "Dashboard" in nav:
    st.markdown(f"<div class='section-header'>🏠 Dashboard — {tipo}</div>", unsafe_allow_html=True)

    # Header info
    if "0000" in registros and registros["0000"]:
        r0 = registros["0000"][0]
        campos_0 = campos_map.get("0000", [])
        info = {c: r0[i] if i < len(r0) else "" for i, c in enumerate(campos_0)}
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏢 Empresa", info.get("NOME", "—")[:25])
        col2.metric("📋 CNPJ", info.get("CNPJ", "—"))
        col3.metric("📅 Período", f"{info.get('DT_INI','?')} ~ {info.get('DT_FIN','?')}")
        col4.metric("🗺️ UF", info.get("UF", "—"))

    st.divider()

    # KPIs
    erros = [i for i in issues if i["gravidade"] == "ERRO"]
    alertas = [i for i in issues if i["gravidade"] == "ALERTA"]
    total_regs = sum(len(v) for v in registros.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total de Registros", f"{total_regs:,}")
    c2.metric("🗂️ Tipos de Registro", len(registros))
    c3.metric("🔴 Erros", len(erros), delta=None)
    c4.metric("🟡 Alertas", len(alertas), delta=None)

    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📊 Registros por Bloco")
        bloco_counts = defaultdict(int)
        for reg, rows in registros.items():
            bloco = reg[0]
            bloco_counts[bloco] += len(rows)
        df_blocos = pd.DataFrame(list(bloco_counts.items()), columns=["Bloco", "Qtd"]).sort_values("Bloco")
        fig = px.bar(df_blocos, x="Bloco", y="Qtd", color="Qtd",
                     color_continuous_scale="Blues", title="Quantidade de Linhas por Bloco")
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("⚠️ Problemas por Tipo")
        if issues:
            tipo_counts = defaultdict(int)
            for issue in issues:
                tipo_counts[issue["tipo"]] += 1
            df_tipos = pd.DataFrame(list(tipo_counts.items()), columns=["Tipo", "Qtd"]).sort_values("Qtd", ascending=False)
            fig2 = px.bar(df_tipos, x="Qtd", y="Tipo", orientation="h",
                          color="Qtd", color_continuous_scale="Reds", title="Problemas por Categoria")
            fig2.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.success("✅ Nenhum problema encontrado!")

    # Top registros
    st.subheader("📋 Top 15 Registros por Volume")
    reg_counts = {k: len(v) for k, v in registros.items()}
    top = sorted(reg_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    df_top = pd.DataFrame(top, columns=["Registro", "Qtd"])
    df_top["Bloco"] = df_top["Registro"].str[0]
    fig3 = px.treemap(df_top, path=["Bloco", "Registro"], values="Qtd",
                      color="Qtd", color_continuous_scale="Blues")
    fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)


# ──────────────────────────────────────────────
# ANALISAR BLOCOS
# ──────────────────────────────────────────────

elif "Analisar" in nav:
    st.markdown("<div class='section-header'>🔍 Análise de Blocos e Registros</div>", unsafe_allow_html=True)

    available_regs = sorted(registros.keys())
    blocos = sorted(set(r[0] for r in available_regs))

    col1, col2 = st.columns([1, 3])
    with col1:
        bloco_sel = st.selectbox("Bloco", blocos)
    with col2:
        regs_bloco = [r for r in available_regs if r.startswith(bloco_sel)]
        reg_sel = st.selectbox("Registro", regs_bloco)

    if reg_sel:
        df = build_df(registros, reg_sel, campos_map)
        n = len(df)
        st.caption(f"**{n}** ocorrências do registro **{reg_sel}**")

        # Highlight issues for this register
        reg_issues = [i for i in issues if reg_sel in i["registro"]]

        if reg_issues:
            with st.expander(f"⚠️ {len(reg_issues)} problema(s) neste registro", expanded=False):
                df_issues = pd.DataFrame(reg_issues)
                st.dataframe(df_issues, use_container_width=True, hide_index=True)

        # Show dataframe with numeric conversion
        for col in df.columns:
            if col.startswith("VL_") or col.startswith("ALIQ_") or col.startswith("QUANT_"):
                df[col] = pd.to_numeric(df[col].str.replace(",", "."), errors="ignore")

        st.dataframe(df, use_container_width=True, height=400, hide_index=True)

        # Totalizador para campos numéricos
        num_cols = [c for c in df.columns if df[c].dtype in ["float64", "int64"]]
        if num_cols:
            st.subheader("∑ Totalizadores")
            totais = {c: df[c].sum() for c in num_cols if df[c].sum() != 0}
            if totais:
                cols = st.columns(min(len(totais), 4))
                for idx, (campo, val) in enumerate(totais.items()):
                    cols[idx % 4].metric(campo, f"R$ {val:,.2f}" if "VL_" in campo else f"{val:,.4f}")

        # Charts for CST distribution
        for cst_col in ["CST_PIS", "CST_COFINS", "CST_ICMS", "CST_IPI"]:
            if cst_col in df.columns:
                st.subheader(f"📊 Distribuição {cst_col}")
                cst_dist = df[cst_col].value_counts().reset_index()
                cst_dist.columns = [cst_col, "Qtd"]
                fig = px.pie(cst_dist, names=cst_col, values="Qtd", hole=0.4)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)


# ──────────────────────────────────────────────
# VALIDAÇÕES
# ──────────────────────────────────────────────

elif "Validações" in nav:
    st.markdown("<div class='section-header'>⚠️ Validações e Inconsistências</div>", unsafe_allow_html=True)

    if not issues:
        st.markdown("<div class='metric-card ok-card'><h3>✅ Sem Problemas Encontrados</h3><p>Todos os registros analisados estão em conformidade com as regras do PVA.</p></div>", unsafe_allow_html=True)
    else:
        erros = [i for i in issues if i["gravidade"] == "ERRO"]
        alertas = [i for i in issues if i["gravidade"] == "ALERTA"]

        c1, c2 = st.columns(2)
        c1.metric("🔴 Erros Críticos", len(erros))
        c2.metric("🟡 Alertas", len(alertas))

        tab1, tab2, tab3 = st.tabs(["🔴 Todos os Erros", "🟡 Alertas", "📊 Análise por CST"])

        with tab1:
            if erros:
                df_erros = pd.DataFrame(erros)
                # Filtros
                regs_unicas = sorted(df_erros["registro"].str.extract(r'(C\d+|D\d+|F\d+|E\d+|M\d+)')[0].dropna().unique().tolist())
                filtro = st.multiselect("Filtrar por Registro", options=sorted(df_erros["tipo"].unique()), default=[])
                if filtro:
                    df_erros = df_erros[df_erros["tipo"].isin(filtro)]
                st.dataframe(
                    df_erros[["registro", "campo", "cst", "tipo", "detalhe"]],
                    use_container_width=True, height=500, hide_index=True,
                    column_config={
                        "gravidade": st.column_config.TextColumn("Gravidade"),
                        "detalhe": st.column_config.TextColumn("Detalhe", width="large"),
                    }
                )
            else:
                st.success("Sem erros críticos!")

        with tab2:
            if alertas:
                df_alertas = pd.DataFrame(alertas)
                st.dataframe(df_alertas[["registro", "campo", "cst", "tipo", "detalhe"]], use_container_width=True, height=400, hide_index=True)
            else:
                st.success("Sem alertas!")

        with tab3:
            st.subheader("Erros por CST")
            df_all = pd.DataFrame(issues)
            if not df_all.empty:
                cst_erros = df_all.groupby(["cst", "gravidade"]).size().reset_index(name="Qtd")
                fig = px.bar(cst_erros, x="cst", y="Qtd", color="gravidade",
                             color_discrete_map={"ERRO": "#ef4444", "ALERTA": "#f59e0b"},
                             title="Problemas por CST")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

        # Tabela de referência CST
        with st.expander("📚 Tabela de Referência CST PIS/COFINS"):
            df_cst = pd.DataFrame(
                [(cst, desc, "✅ Sim" if req else "❌ Não") for cst, (desc, req) in CST_PIS_COFINS.items()],
                columns=["CST", "Descrição", "Requer BC/Alíq/Vl"]
            )
            st.dataframe(df_cst, use_container_width=True, hide_index=True)

        with st.expander("📚 Tabela de Referência CST ICMS"):
            df_cst_icms = pd.DataFrame(
                [(cst, desc, "✅ Sim" if req else "❌ Não") for cst, (desc, req) in CST_ICMS.items()],
                columns=["CST", "Descrição", "Requer BC/Alíq/Vl"]
            )
            st.dataframe(df_cst_icms, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────
# EDITOR
# ──────────────────────────────────────────────

elif "Editor" in nav:
    st.markdown("<div class='section-header'>✏️ Editor de Registros</div>", unsafe_allow_html=True)
    st.warning("⚠️ Alterações aqui modificam os dados em memória. Use 'Exportar' para salvar o arquivo corrigido.")

    available_regs = sorted(st.session_state.edited_registros.keys())
    reg_ed = st.selectbox("Selecione o Registro para Editar", available_regs)

    if reg_ed:
        campos = campos_map.get(reg_ed, [])
        rows = st.session_state.edited_registros[reg_ed]

        if not rows:
            st.info("Registro sem ocorrências.")
        else:
            # Build dataframe for editing
            df_ed = pd.DataFrame(rows, columns=campos if campos else [f"Campo_{i}" for i in range(len(rows[0]))])

            st.info(f"Editando **{len(df_ed)}** linhas do registro **{reg_ed}**. Modifique as células abaixo e clique em 'Salvar Alterações'.")

            edited_df = st.data_editor(
                df_ed,
                use_container_width=True,
                num_rows="dynamic",
                height=450,
                key=f"editor_{reg_ed}"
            )

            col_save, col_reset = st.columns([1, 4])
            with col_save:
                if st.button("💾 Salvar Alterações", type="primary"):
                    st.session_state.edited_registros[reg_ed] = edited_df.values.tolist()
                    # Re-run validation
                    st.session_state.issues = full_validation(st.session_state.edited_registros, campos_map)
                    st.success(f"✅ {reg_ed} atualizado! Validação reexecutada.")
                    st.rerun()
            with col_reset:
                if st.button("🔄 Restaurar Original"):
                    st.session_state.edited_registros[reg_ed] = [list(r) for r in registros[reg_ed]]
                    st.success("Restaurado para o original.")
                    st.rerun()

    # Quick fix: auto-zero non-taxable fields
    st.divider()
    st.subheader("🔧 Correções Automáticas")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Zerar BC/Alíq/Vl em CSTs não tributados**")
        st.caption("Remove valores indevidos em CSTs isentos/não tributados/suspensos")
        if st.button("🤖 Aplicar Correção Automática"):
            count = 0
            for reg_name in ["C170", "C175", "D100", "F100"]:
                if reg_name not in st.session_state.edited_registros:
                    continue
                campos_r = campos_map.get(reg_name, [])
                for row_parts in st.session_state.edited_registros[reg_name]:
                    row = {c: row_parts[i] if i < len(row_parts) else "" for i, c in enumerate(campos_r)}
                    for tributo in ["PIS", "COFINS"]:
                        cst = str(row.get(f"CST_{tributo}", "")).zfill(2)
                        cst_info = CST_PIS_COFINS.get(cst)
                        if cst_info and not cst_info[1]:
                            for field in [f"VL_BC_{tributo}", f"ALIQ_{tributo}", f"VL_{tributo}"]:
                                if field in campos_r:
                                    idx = campos_r.index(field)
                                    if idx < len(row_parts) and row_parts[idx] not in ("", "0", "0,00"):
                                        row_parts[idx] = "0,00"
                                        count += 1
            st.session_state.issues = full_validation(st.session_state.edited_registros, campos_map)
            st.success(f"✅ {count} campo(s) zerado(s). Validação reexecutada.")
            st.rerun()


# ──────────────────────────────────────────────
# EXPORTAR
# ──────────────────────────────────────────────

elif "Exportar" in nav:
    st.markdown("<div class='section-header'>📤 Exportar Arquivo</div>", unsafe_allow_html=True)

    tab_txt, tab_excel, tab_relatorio = st.tabs(["📄 Arquivo TXT (PVA)", "📊 Excel", "📋 Relatório de Validação"])

    with tab_txt:
        st.info("O arquivo será gerado no formato padrão SPED (.txt com pipes) compatível com o PVA Validador.")

        edited = st.session_state.edited_registros
        erros_restantes = [i for i in st.session_state.issues if i["gravidade"] == "ERRO"]

        if erros_restantes:
            st.warning(f"⚠️ Ainda existem **{len(erros_restantes)} erros** no arquivo. O PVA pode rejeitar. Deseja exportar mesmo assim?")
            force = st.checkbox("Exportar mesmo com erros")
        else:
            force = True
            st.success("✅ Sem erros! Arquivo pronto para exportação.")

        if force:
            # Rebuild file from edited_registros maintaining original order
            original_lines = st.session_state.content_lines
            # Build a lookup: for each line, find the register and update
            new_lines = []
            reg_counters = defaultdict(int)

            for line in original_lines:
                line_stripped = line.strip()
                if not line_stripped:
                    new_lines.append(line)
                    continue

                if line_stripped.startswith("|") and line_stripped.endswith("|"):
                    parts = line_stripped[1:-1].split("|")
                elif "|" in line_stripped:
                    parts = line_stripped.split("|")
                    if parts and parts[0] == "":
                        parts = parts[1:]
                    if parts and parts[-1] == "":
                        parts = parts[:-1]
                else:
                    new_lines.append(line)
                    continue

                if not parts:
                    new_lines.append(line)
                    continue

                reg = parts[0].strip().upper()
                idx = reg_counters[reg]

                if reg in edited and idx < len(edited[reg]):
                    new_parts = edited[reg][idx]
                    new_lines.append(rebuild_sped_line([str(p) for p in new_parts]))
                    reg_counters[reg] += 1
                else:
                    new_lines.append(line_stripped)
                    reg_counters[reg] += 1

            output = "\n".join(new_lines)
            st.download_button(
                label="⬇️ Baixar Arquivo TXT Corrigido",
                data=output.encode("latin-1", errors="replace"),
                file_name="EFD_corrigido.txt",
                mime="text/plain",
                type="primary"
            )
            st.caption(f"📏 {len(new_lines):,} linhas | {len(output.encode('latin-1', errors='replace')):,} bytes")

    with tab_excel:
        st.info("Exporta os principais registros em abas separadas de uma planilha Excel.")
        regs_excel = st.multiselect(
            "Selecione os registros para exportar",
            options=sorted(registros.keys()),
            default=[r for r in ["0000", "C100", "C170", "C190", "D100", "F100", "M200", "M600", "E110"] if r in registros]
        )
        if st.button("📊 Gerar Excel", type="primary"):
            dfs = {}
            for reg in regs_excel:
                df = build_df(registros, reg, campos_map)
                if not df.empty:
                    dfs[reg] = df
            if dfs:
                excel_bytes = to_excel_bytes(dfs)
                st.download_button(
                    "⬇️ Baixar Excel",
                    data=excel_bytes,
                    file_name="EFD_analise.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    with tab_relatorio:
        st.info("Exporta o relatório completo de validação em Excel.")
        if st.session_state.issues:
            df_rel = pd.DataFrame(st.session_state.issues)
            buf = BytesIO()
            df_rel.to_excel(buf, index=False)
            st.download_button(
                "⬇️ Baixar Relatório de Validação",
                data=buf.getvalue(),
                file_name="relatorio_validacao_SPED.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.dataframe(df_rel, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Sem problemas para reportar.")

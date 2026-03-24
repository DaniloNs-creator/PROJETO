import streamlit as st
import requests
import json
from datetime import datetime

# ==========================================
# Configurações da Página
# ==========================================
st.set_page_config(page_title="Laggo WMS Integration", layout="wide", page_icon="📦")
st.title("📦 Integração Laggo WMS - Painel de Controle")
[span_8](start_span)[span_9](start_span)[span_10](start_span)st.markdown("Painel profissional para integração com as APIs do Infor ION[span_8](end_span)[span_9](end_span)[span_10](end_span).")

# ==========================================
# Barra Lateral: Configurações e Autenticação
# ==========================================
st.sidebar.header("⚙️ Configurações ION API")
[span_11](start_span)[span_12](start_span)[span_13](start_span)st.sidebar.markdown("Insira os dados do seu arquivo `.ionapi`[span_11](end_span)[span_12](end_span)[span_13](end_span).")

# [span_14](start_span)[span_15](start_span)[span_16](start_span)Campos de configuração[span_14](end_span)[span_15](end_span)[span_16](end_span)
tenant_id = st.sidebar.text_input("Tenant ID (ti)", value="A62KR42EX6BAV5NU_TST")
client_id = st.sidebar.text_input("Client ID (ci)")
client_secret = st.sidebar.text_input("Client Secret (cs)", type="password")
username = st.sidebar.text_input("Username / SAAK (saak)")
password = st.sidebar.text_input("Password / SASK (sask)", type="password")
base_url = st.sidebar.text_input("Base URL ION API", value="https://mingle-ionapi.inforcloudsuite.com")
sso_url = st.sidebar.text_input("SSO Token URL", value="https://mingle-sso.inforcloudsuite.com:443")

def get_auth_token():
    [span_17](start_span)[span_18](start_span)[span_19](start_span)"""Gera o token OAuth 2.0 com base nas credenciais informadas[span_17](end_span)[span_18](end_span)[span_19](end_span)."""
    token_url = f"{sso_url}/{tenant_id}/as/token.oauth2"
    payload = {
        "grant_type": "password",
        "username": username,
        "password": password
    }
    # [span_20](start_span)[span_21](start_span)[span_22](start_span)A autenticação exige envio como Basic Auth[span_20](end_span)[span_21](end_span)[span_22](end_span)
    auth = (client_id, client_secret)
    
    try:
        response = requests.post(token_url, data=payload, auth=auth)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        st.sidebar.error(f"Erro de autenticação: {e}")
        return None

if st.sidebar.button("Gerar Token"):
    if client_id and client_secret and username and password:
        with st.spinner("Autenticando..."):
            token = get_auth_token()
            if token:
                st.session_state['access_token'] = token
                [span_23](start_span)[span_24](start_span)[span_25](start_span)st.sidebar.success("Token gerado com sucesso! (Válido por 2 horas)[span_23](end_span)[span_24](end_span)[span_25](end_span)")
    else:
        st.sidebar.warning("Preencha todas as credenciais.")

# Verifica se está autenticado
is_authenticated = 'access_token' in st.session_state

# ==========================================
# Navegação Principal (Abas)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 Consulta de Estoque", "🧾 Atualização de Faturamento", "📥 Cadastro ASN Filial"])

headers = {}
if is_authenticated:
    headers["Authorization"] = f"Bearer {st.session_state['access_token']}"

# --- ABA 1: Consulta Posição de Estoque ---
with tab1:
    st.header("Consulta de Posição de Estoque")
    [span_26](start_span)st.markdown("Pesquise o estoque informando parâmetros ou deixe em branco para pesquisa total[span_26](end_span).")
    
    col1, col2 = st.columns(2)
    with col1:
        proprietario = st.text_input("Proprietário", value="POLITEC")
        filial = st.text_input("Filial", value="wmwhse1")
        nota = st.text_input("Nota (Opcional)")
    with col2:
        sku = st.text_input("SKU (Opcional)")
        chave = st.text_input("Chave (Opcional)")
        lote = st.text_input("Lote (Opcional)")
        
    if st.button("Consultar Estoque"):
        if not is_authenticated:
            st.error("Gere o token de autenticação primeiro.")
        else:
            [span_27](start_span)url = f"{base_url}/{tenant_id}/APIFLOWS/consultaestoque/estoque" #[span_27](end_span)
            payload = {
                "proprietario": proprietario,
                "filial": filial
            }
            if nota: payload["nota"] = nota
            if sku: payload["sku"] = sku
            if chave: payload["chave"] = chave
            if lote: payload["lote"] = lote
                
            with st.spinner("Consultando..."):
                resp = requests.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    st.success("Consulta realizada com sucesso!")
                    [span_28](start_span)st.json(resp.json()) #[span_28](end_span)
                else:
                    st.error(f"Erro {resp.status_code}: {resp.text}")

# --- ABA 2: Atualização de Faturamento ---
with tab2:
    st.header("Atualização Dados de Faturamento")
    [span_29](start_span)st.markdown("Envio através de API Rest multipartMessage[span_29](end_span).")
    
    col1, col2 = st.columns(2)
    with col1:
        fat_proprietario = st.text_input("Proprietário (Faturamento)", value="POLITEC")
        fat_filial = st.text_input("Filial (Faturamento)", value="wmwhse1")
        fat_ordem = st.text_input("Ordem Externa", value="Ordem12345")
    with col2:
        fat_nota = st.text_input("Nota Fiscal", value="2345")
        fat_chave = st.text_input("Chave NF")
        fat_valor = st.number_input("Valor Total", value=0.0, format="%.2f")
        
    if st.button("Atualizar Faturamento"):
        if not is_authenticated:
            st.error("Gere o token de autenticação primeiro.")
        else:
            [span_30](start_span)url = f"{base_url}/{tenant_id}/IONSERVICES/api/ion/messaging/service/v3/multipartMessage" #[span_30](end_span)
            
            # [span_31](start_span)Message Payload[span_31](end_span)
            message_payload = {
                "AtualizacaoFaturamento": [{
                    "proprietario": fat_proprietario,
                    "ordem_externa": fat_ordem,
                    "chave_nf": fat_chave,
                    "nota_fiscal": fat_nota,
                    "valor_total": fat_valor,
                    "filial": fat_filial
                }]
            }
            
            # [span_32](start_span)Parameter Request[span_32](end_span)
            parameter_request = {
                "documentName": "AtualizacaoFaturamento",
                "documentId": fat_ordem,
                "accountingEntity": fat_proprietario,
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default"
            }
            
            files = {
                [span_33](start_span)'MessagePayload': ('MessagePayload', json.dumps(message_payload), 'application/octet-stream'), #[span_33](end_span)
                [span_34](start_span)'ParameterRequest': ('ParameterRequest.json', json.dumps(parameter_request), 'application/json') #[span_34](end_span)
            }
            
            with st.spinner("Enviando dados..."):
                resp = requests.post(url, headers=headers, files=files)
                if resp.status_code in [200, 202]:
                    [span_35](start_span)st.success("Processado com sucesso[span_35](end_span)!")
                    st.json(resp.json() if resp.text else {"status": "OK", "code": resp.status_code})
                else:
                    st.error(f"Erro {resp.status_code}: {resp.text}")

# --- ABA 3: Cadastro de ASN Filial ---
with tab3:
    st.header("Cadastrar ASN de Recebimento")
    [span_36](start_span)[span_37](start_span)st.markdown("Cria um aviso de recebimento (ASN) no WMS[span_36](end_span)[span_37](end_span).")
    
    asn_prop = st.text_input("Proprietário (ASN)", value="LAGG001")
    [span_38](start_span)asn_ext = st.text_input("Recebimento Externo (Chave única)[span_38](end_span)", value="CHAVENOTA123")
    asn_filial = st.text_input("Filial WMS", value="wmwhse1")
    
    st.subheader("Detalhes do Item")
    asn_sku = st.text_input("SKU")
    [span_39](start_span)asn_qtd = st.number_input("Quantidade Prevista[span_39](end_span)", value=100.0)
    asn_val = st.number_input("Valor Unitário", value=10.0)
    
    if st.button("Cadastrar ASN"):
        if not is_authenticated:
            st.error("Gere o token de autenticação primeiro.")
        else:
            [span_40](start_span)url = f"{base_url}/{tenant_id}/IONSERVICES/api/ion/messaging/service/v3/multipartMessage" #[span_40](end_span)
            
            # [span_41](start_span)Message Payload (Simplificado para o exemplo)[span_41](end_span)
            message_payload = {
                "proprietario": asn_prop,
                "recebimento_externo": asn_ext,
                "filial": asn_filial,
                "recebimentodetalhes": [{
                    "sku": asn_sku,
                    "recdet_linha": "00001",
                    "recdet_lin_ext": "00001",
                    "qtde": asn_qtd,
                    "valor_unitario": asn_val
                }]
            }
            
            # [span_42](start_span)Parameter Request[span_42](end_span)
            parameter_request = {
                "documentName": "AsnFilial",
                "documentId": asn_ext,
                "accountingEntity": asn_prop,
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default",
                "source": username
            }
            
            files = {
                [span_43](start_span)'MessagePayload': ('MessagePayload', json.dumps(message_payload), 'application/octet-stream'), #[span_43](end_span)
                [span_44](start_span)'ParameterRequest': ('ParameterRequest.json', json.dumps(parameter_request), 'application/json') #[span_44](end_span)
            }
            
            with st.spinner("Enviando ASN..."):
                resp = requests.post(url, headers=headers, files=files)
                [span_45](start_span)if resp.status_code in [200, 202]: #[span_45](end_span)
                    st.success("ASN cadastrada com sucesso!")
                    st.json(resp.json() if resp.text else {"status": "OK", "code": resp.status_code})
                else:
                    st.error(f"Erro {resp.status_code}: {resp.text}")

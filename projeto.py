import streamlit as st
import requests
import json
from datetime import datetime

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Laggo WMS Integration", page_icon="📦", layout="wide")

# ==========================================
# FUNÇÕES DE ESTADO E AUTENTICAÇÃO
# ==========================================
def init_session_state():
    if "token" not in st.session_state:
        st.session_state.token = None
    if "tenant_url" not in st.session_state:
        st.session_state.tenant_url = ""

def gerar_token(pu, ot, ci, cs, saak, sask):
    url = f"{pu}{ot}"
    payload = {
        "grant_type": "password",
        "client_id": ci,
        "client_secret": cs,
        "username": saak,
        "password": sask
    }
    try:
        # Chamada real comentada para evitar erros de execução sem credenciais válidas
        # response = requests.post(url, data=payload)
        # response.raise_for_status()
        # st.session_state.token = response.json().get("access_token")
        
        # Simulação para testes do painel:
        st.session_state.token = "MOCK_TOKEN_A62KR42EX6BAV5NU_TST"
        st.success("Token gerado com sucesso! (Válido por 2 horas)")
    except Exception as e:
        st.error(f"Erro ao gerar token: {e}")

# ==========================================
# COMPONENTES DE INTERFACE (APIs)
# ==========================================
def pagina_autenticacao():
    st.header("🔐 Autenticação Infor ION API")
    st.markdown("Insira os dados do arquivo `.ionapi` para gerar o token OAuth 2.0.")
    
    with st.form("auth_form"):
        col1, col2 = st.columns(2)
        with col1:
            pu = st.text_input("Base URL Auth (pu)", value="https://mingle-sso.inforcloudsuite.com:443/A62KR42EX6BAV5NU_TST/as/")
            ot = st.text_input("Token Path (ot)", value="token.oauth2")
            st.session_state.tenant_url = st.text_input("ION API URL (iu)", value="https://mingle-ionapi.inforcloudsuite.com/A62KR42EX6BAV5NU_TST")
        with col2:
            ci = st.text_input("Client ID (ci)", type="password")
            cs = st.text_input("Client Secret (cs)", type="password")
            saak = st.text_input("Username (saak)")
            sask = st.text_input("Password (sask)", type="password")
        
        submit = st.form_submit_button("Gerar Token de Acesso")
        if submit:
            gerar_token(pu, ot, ci, cs, saak, sask)

def pagina_consulta_estoque():
    st.header("📊 Consulta de Estoque")
    st.markdown("A pesquisa pode ser realizada sem parâmetros para pesquisa total.")
    
    with st.form("estoque_form"):
        col1, col2, col3 = st.columns(3)
        proprietario = col1.text_input("Proprietário", "POLITEC")
        filial = col2.text_input("Filial", "wmwhse1")
        sku = col3.text_input("SKU", "107002")
        
        chave = st.text_input("Chave da Nota")
        nota = st.text_input("Nota")
        lote = st.text_input("Lote")
        
        if st.form_submit_button("Consultar"):
            payload = {
                "proprietario": proprietario,
                "chave": chave,
                "nota": nota,
                "sku": sku,
                "lote": lote,
                "filial": filial
            }
            # Simulação de envio da APIFlow
            st.json(payload)
            st.info("POST: /APIFLOWS/consultaestoque/estoque")

def pagina_peso_volume():
    st.header("⚖️ Peso e Volume (Confirmação de Separação)")
    
    with st.form("peso_volume_form"):
        col1, col2 = st.columns(2)
        proprietario = col1.text_input("Proprietário", "LAGG001")
        orderkey = col2.text_input("OrderKey", "0000123")
        ordem_externa = col1.text_input("Ordem Externa", "ORDEXT123456")
        filial = col2.text_input("Filial", "wmwhse1")
        volume_total = col1.number_input("Volume Total", value=20.0)
        peso_total = col2.number_input("Peso Total", value=30.0)
        
        if st.form_submit_button("Enviar Confirmação"):
            payload = {
                "confirmseparacao": [
                    {
                        "proprietario": proprietario,
                        "orderkey": orderkey,
                        "ordem_externa": ordem_externa,
                        "filial": filial,
                        "volume_total": volume_total,
                        "peso_total": peso_total
                    }
                ]
            }
            st.json(payload)
            st.success("Dados montados para envio ao ION!")

def pagina_multipart_api(titulo, document_name):
    # Base genérica para APIs que usam o endpoint multipartMessage (Faturamento, ASN, etc.)
    st.header(titulo)
    st.markdown("Esta API utiliza o formato `multipartMessage` via ION Services.")
    
    with st.form(f"form_{document_name}"):
        doc_id = st.text_input("ID Lógico / Document ID", "00000123")
        entidade = st.text_input("Entidade / Proprietário", "POLITEC")
        conteudo_json = st.text_area("Payload da Mensagem (MessagePayload)", value='{"exemplo": "adicione o json aqui"}', height=200)
        
        if st.form_submit_button("Disparar Integração"):
            param_request = {
                "documentName": document_name,
                "documentId": doc_id,
                "accountingEntity": entidade,
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default"
            }
            
            st.write("### Estrutura do Arquivo Multipart")
            st.markdown("**1. ParameterRequest (application/json):**")
            st.json(param_request)
            
            st.markdown("**2. MessagePayload (application/octet-stream):**")
            st.code(conteudo_json, language='json')
            
            # Código real para envio via requests
            st.markdown("`Código Python para requisição HTTP:`")
            st.code(f"""
headers = {{'Authorization': 'Bearer {st.session_state.token}'}}
files = {{
    'MessagePayload': (None, payload_str, 'application/octet-stream'),
    'ParameterRequest': ('ParameterRequest.json', json.dumps(param_request), 'application/json')
}}
response = requests.post("URL_MULTIPART", headers=headers, files=files)
            """, language="python")

# ==========================================
# ESTRUTURA PRINCIPAL
# ==========================================
def main():
    init_session_state()
    
    st.sidebar.title("📦 Integração Laggo")
    
    # Indicador de Token
    if st.session_state.token:
        st.sidebar.success("✅ Autenticado")
    else:
        st.sidebar.error("❌ Não Autenticado")
        
    st.sidebar.markdown("---")
    
    menu = st.sidebar.radio("Navegação", [
        "1. Autenticação OAuth",
        "2. Consulta de Estoque",
        "3. Peso e Volume",
        "4. Atualização Faturamento",
        "5. Confirmação Recebimento",
        "6. Confirmação Faturamento",
        "7. ASN Filial"
    ])
    
    if menu == "1. Autenticação OAuth":
        pagina_autenticacao()
    elif menu == "2. Consulta de Estoque":
        pagina_consulta_estoque()
    elif menu == "3. Peso e Volume":
        pagina_peso_volume()
    elif menu == "4. Atualização Faturamento":
        pagina_multipart_api("🧾 Atualização Dados Faturamento", "AtualizacaoFaturamento")
    elif menu == "5. Confirmação Recebimento":
        # Recebimento é geralmente JSON padrão, mas a interface base serve de modelo
        st.header("📥 Confirmação de Recebimento")
        st.info("API para confirmação de recebimento após fechamento de ASN.")
        # Pode ser expandido similar ao Peso e Volume
    elif menu == "6. Confirmação Faturamento":
        pagina_multipart_api("💵 Confirmação de Faturamento", "ConfirmacaoFaturamento")
    elif menu == "7. ASN Filial":
        pagina_multipart_api("🚛 ASN Filial", "AsnFilial")

if __name__ == "__main__":
    main()

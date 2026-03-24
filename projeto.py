import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

# Default values (for demonstration - should be replaced with actual .ionapi file content)
DEFAULT_IONAPI = {
    "ti": "A62KR42EX6BAV5NU_TST",
    "cn": "IONWorkFlow-A62KR42EX6BAV5NU_TST",
    "dt": "12",
    "ci": "A62KR42EX6BAV5NU_TST~VnRDLp8A_JdiXT9oQkngLHFHaOtIv0OPPLjMYYJKJV8",
    "cs": "WXTAauXdKPSldiJV5olE0jvkVw5COQTahxeV3Mh7jd8JoS_y_EQhH68mIr0XVs6yr7ApFmIR0apD3go He_XqwQ",
    "iu": "https://mingle-ionapi.inforcloudsuite.com",
    "pu": "https://mingle-sso.inforcloudsuite.com:443/A62KR42EX6BAV5NU_TST/as/",
    "oa": "authorization.oauth2",
    "ot": "token.oauth2",
    "or": "revoke_token.oauth2",
    "ev": "U1478358101",
    "v": "1.0",
    "saak": "A62KR42EX6BAV5NU_TST#hEPrlXR9hygcFLnTtSV2ZB5FRtj2GZseUukx6doG7C30CEkDm- _dUbW7HmJhio-TaHliVrr7AMLuEHYDJp5E_w",
    "sask": "drON0gs8xCo33mVfa0Afpw2YRrGptfqfsAMZCX_CXD8Cd437FeJ2Hn0tCu2EBMCYQcnx0A Mtcfm TV9zTCFLDTA"
}

# Base URLs and endpoints
# For Stock Query (Infor API FLOW) - uses tenant from IONAPI
STOCK_QUERY_ENDPOINT = "https://mingle-ionapi.inforcloudsuite.com/{tenant}/APIFLOWS/consultaestoque/estoque"

# For other services (ION SERVICES) - using default tenant placeholder
ION_SERVICES_BASE = "https://mingle-ionapi.inforcloudsuite.com"
ASN_ENDPOINT = ION_SERVICES_BASE + "/multipartMessage"  # Placeholder - actual endpoint may differ
BILLING_CONFIRM_ENDPOINT = ION_SERVICES_BASE + "/multipartMessage"
WEIGHT_VOLUME_ENDPOINT = ION_SERVICES_BASE + "/multipartMessage"
RECEIPT_CONFIRM_ENDPOINT = ION_SERVICES_BASE + "/multipartMessage"
BILLING_UPDATE_ENDPOINT = ION_SERVICES_BASE + "/multipartMessage"

# -----------------------------------------------------------------------------
# AUTHENTICATION MODULE
# -----------------------------------------------------------------------------
class InforAuthenticator:
    """Handles OAuth 2.0 token generation for Infor CloudSuite"""
    
    def __init__(self, ionapi_config):
        self.config = ionapi_config
        self.token = None
        self.token_expiry = None
    
    def get_token(self):
        """Get a valid token, refreshing if expired"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
        
        # Generate new token
        access_token_url = self.config["pu"] + self.config["ot"]
        
        # Prepare payload for Password Credentials Grant
        payload = {
            "grant_type": "password",
            "username": self.config["saak"],
            "password": self.config["sask"],
            "client_id": self.config["ci"],
            "client_secret": self.config["cs"]
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            response = requests.post(access_token_url, data=payload, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            self.token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 7200)  # Default 2 hours
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)  # Buffer 1 minute
            return self.token
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return None
    
    def get_auth_header(self):
        """Return the Authorization header for Bearer token"""
        token = self.get_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

# -----------------------------------------------------------------------------
# API SERVICES MODULE
# -----------------------------------------------------------------------------
class InforAPIServices:
    """Wrapper for all Infor WMS API integrations"""
    
    def __init__(self, auth):
        self.auth = auth
    
    # 1. Stock Query API (Infor API FLOW)
    def query_stock(self, owner=None, key=None, nota=None, sku=None, lote=None, filial=None):
        """
        Query stock levels based on parameters.
        If no parameters, returns total stock.
        """
        endpoint = STOCK_QUERY_ENDPOINT.format(tenant=self.auth.config.get("ti", ""))
        
        payload = {}
        if owner:
            payload["proprietario"] = owner
        if key:
            payload["chave"] = key
        if nota:
            payload["nota"] = nota
        if sku:
            payload["sku"] = sku
        if lote:
            payload["lote"] = lote
        if filial:
            payload["filial"] = filial
        
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e), "response": response.text if 'response' in locals() else None}
    
    # 2. ASN Filial API (Create ASN)
    def create_asn(self, asn_data):
        """Create an ASN (Advanced Shipping Notice)"""
        # Prepare parameter request wrapper
        wrapper = {
            "parameterrequest": {
                "documentName": "AsnFilial",
                "documentId": asn_data["recebimento"]["recebimento_externo"],
                "accountingEntity": asn_data["recebimento"]["proprietario"],
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default",
                "source": self.auth.config.get("saak", "")
            },
            "messagepayload": asn_data
        }
        
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(ASN_ENDPOINT, json=wrapper, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e), "response": response.text if 'response' in locals() else None}
    
    # 3. Billing Confirmation API
    def confirm_billing(self, billing_data):
        """Confirm billing with order details"""
        wrapper = {
            "parameterrequest": {
                "documentName": "OrdemExpedAPI",
                "documentId": billing_data["confirmacaoFaturamento"]["ordem_externa"],
                "accountingEntity": billing_data["confirmacaoFaturamento"]["proprietario"],
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default",
                "source": self.auth.config.get("saak", "")
            },
            "messagepayload": billing_data
        }
        
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(BILLING_CONFIRM_ENDPOINT, json=wrapper, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e), "response": response.text if 'response' in locals() else None}
    
    # 4. Weight and Volume API (after packing)
    def send_weight_volume(self, weight_volume_data):
        """Send weight and volume information after packing"""
        # Prepare wrapper similar to other services
        wrapper = {
            "parameterrequest": {
                "documentName": "confirmseparacao",
                "documentId": weight_volume_data.get("orderkey", ""),
                "accountingEntity": weight_volume_data.get("proprietario", ""),
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default",
                "source": self.auth.config.get("saak", "")
            },
            "messagepayload": weight_volume_data
        }
        
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(WEIGHT_VOLUME_ENDPOINT, json=wrapper, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e), "response": response.text if 'response' in locals() else None}
    
    # 5. Receipt Confirmation API
    def confirm_receipt(self, receipt_data):
        """Confirm receipt of goods"""
        wrapper = {
            "parameterrequest": {
                "documentName": "ConfirmaRecebimento",
                "documentId": receipt_data.get("recebimento", {}).get("recebimento_externo", ""),
                "accountingEntity": receipt_data.get("recebimento", {}).get("proprietario", ""),
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default",
                "source": self.auth.config.get("saak", "")
            },
            "messagepayload": receipt_data
        }
        
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(RECEIPT_CONFIRM_ENDPOINT, json=wrapper, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e), "response": response.text if 'response' in locals() else None}
    
    # 6. Billing Data Update API (shipper/carrier)
    def update_billing_data(self, update_data):
        """Update billing data with shipper and carrier information"""
        wrapper = {
            "parameterrequest": {
                "documentName": "AtualizacaoFaturamento",
                "documentId": update_data.get("documentId", ""),
                "accountingEntity": update_data.get("accountingEntity", ""),
                "fromLogicalId": "lid://infor.ims.ionims",
                "encoding": "NONE",
                "characterSet": "UTF-8",
                "toLogicalId": "lid://default",
                "source": self.auth.config.get("saak", "")
            },
            "messagepayload": update_data
        }
        
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.post(BILLING_UPDATE_ENDPOINT, json=wrapper, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e), "response": response.text if 'response' in locals() else None}

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def load_ionapi_from_file(uploaded_file):
    """Parse uploaded .ionapi file content into dictionary"""
    try:
        content = uploaded_file.read().decode('utf-8')
        # Clean the content - remove any extra whitespace, newlines
        content = content.strip()
        # Try to parse as JSON
        config = json.loads(content)
        return config
    except json.JSONDecodeError:
        # If not valid JSON, try to evaluate as Python dict literal
        try:
            # Replace any problematic line breaks
            content = content.replace('\n', '').replace('\r', '')
            config = eval(content)
            return config
        except:
            st.error("Failed to parse IONAPI file. Please ensure it's a valid JSON or dictionary format.")
            return None

def display_api_response(response):
    """Helper to display API response in a formatted way"""
    if response.get("success"):
        st.success("✅ Request successful!")
        st.json(response.get("data", {}))
    else:
        st.error(f"❌ Request failed: {response.get('error', 'Unknown error')}")
        if response.get("response"):
            st.text(f"Response: {response.get('response')}")

# -----------------------------------------------------------------------------
# STREAMLIT UI
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Infor WMS Integration Suite", page_icon="📦", layout="wide")
    
    st.title("📦 Infor WMS Integration Suite")
    st.markdown("Connect to Infor CloudSuite WMS and manage stock, ASN, billing, and shipping data.")
    
    # Sidebar - Authentication Configuration
    with st.sidebar:
        st.header("🔐 Authentication")
        st.markdown("Upload your `.ionapi` file or use default configuration for testing.")
        
        use_default = st.checkbox("Use default IONAPI configuration (testing)", value=False)
        
        if not use_default:
            uploaded_file = st.file_uploader("Upload .ionapi file", type=["ionapi", "json", "txt"])
            if uploaded_file:
                ionapi_config = load_ionapi_from_file(uploaded_file)
                if ionapi_config:
                    st.success("Configuration loaded!")
            else:
                st.info("Please upload your .ionapi file.")
                ionapi_config = None
        else:
            ionapi_config = DEFAULT_IONAPI
            st.info("Using default configuration.")
        
        if ionapi_config:
            st.subheader("Current Configuration")
            st.json({
                "tenant": ionapi_config.get("ti"),
                "app": ionapi_config.get("cn"),
                "auth_url": ionapi_config.get("pu")
            })
            
            # Initialize authenticator and services
            auth = InforAuthenticator(ionapi_config)
            services = InforAPIServices(auth)
            
            # Test authentication button
            if st.button("Test Authentication"):
                with st.spinner("Testing authentication..."):
                    token = auth.get_token()
                    if token:
                        st.success("✅ Authentication successful!")
                        st.info(f"Token expires at: {auth.token_expiry.strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        st.error("Authentication failed. Check your configuration.")
        else:
            st.warning("No valid IONAPI configuration. Please upload a file or use default.")
            services = None
    
    # Main content - tabs for each API
    if services:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Stock Query", 
            "📄 ASN Filial", 
            "📑 Billing Confirmation",
            "⚖️ Weight & Volume",
            "✅ Receipt Confirmation",
            "✏️ Billing Data Update"
        ])
        
        # Tab 1: Stock Query
        with tab1:
            st.header("Stock Query (Infor API FLOW)")
            st.markdown("Query stock levels by various parameters. Leave all fields empty to fetch total stock.")
            
            col1, col2 = st.columns(2)
            with col1:
                owner = st.text_input("Owner (proprietario)", placeholder="e.g., POLITEC")
                sku = st.text_input("SKU", placeholder="e.g., 107002")
                nota = st.text_input("Nota", placeholder="e.g., 59875")
            with col2:
                filial = st.text_input("Branch (filial)", placeholder="e.g., wmwhse1")
                lote = st.text_input("Lot (lote)", placeholder="Optional")
                chave = st.text_input("Chave", placeholder="Optional (NF key)")
            
            if st.button("🔍 Query Stock", type="primary"):
                with st.spinner("Querying stock..."):
                    result = services.query_stock(
                        owner=owner if owner else None,
                        key=chave if chave else None,
                        nota=nota if nota else None,
                        sku=sku if sku else None,
                        lote=lote if lote else None,
                        filial=filial if filial else None
                    )
                    if result.get("success"):
                        data = result.get("data", [])
                        if isinstance(data, list):
                            st.success(f"Found {len(data)} stock records.")
                            df = pd.DataFrame(data)
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.json(data)
                    else:
                        st.error(f"Query failed: {result.get('error')}")
        
        # Tab 2: ASN Filial
        with tab2:
            st.header("Create ASN Filial")
            st.markdown("Register an Advanced Shipping Notice with shipper and carrier details.")
            
            with st.form("asn_form"):
                st.subheader("Receiving Information")
                col1, col2 = st.columns(2)
                with col1:
                    proprietario = st.text_input("Owner (proprietario)", value="POLITEC")
                    recebimento_externo = st.text_input("External Receipt Number", value="CHAVENOTA123456789")
                    recebimento_externo2 = st.text_input("External Receipt Number 2", placeholder="Optional")
                    tipo = st.selectbox("Receipt Type", ["1 - Normal", "2 - Return", "8 - Production Order"])
                    data_emissao = st.date_input("Issue Date", datetime.now())
                with col2:
                    filial = st.text_input("Branch (filial)", value="wmwhse1")
                    valor_bruto = st.number_input("Gross Value", value=0.0, step=100.0)
                    valor_liquido = st.number_input("Net Value", value=0.0, step=100.0)
                    texto_livre5 = st.text_input("Free Text 5")
                    texto_livre6 = st.text_input("Free Text 6")
                    texto_livre7 = st.text_input("Free Text 7")
                
                st.subheader("Shipper Details")
                col1, col2 = st.columns(2)
                with col1:
                    exp_cnpj = st.text_input("Shipper CNPJ")
                    exp_nome = st.text_input("Shipper Name")
                    exp_logradouro = st.text_input("Address")
                    exp_numero = st.text_input("Number")
                with col2:
                    exp_complemento = st.text_input("Complement")
                    exp_bairro = st.text_input("Neighborhood")
                    exp_cidade = st.text_input("City")
                    exp_uf = st.text_input("State")
                    exp_cep = st.text_input("CEP")
                
                st.subheader("Carrier Details")
                col1, col2 = st.columns(2)
                with col1:
                    transp_cnpj = st.text_input("Carrier CNPJ")
                    transp_nome = st.text_input("Carrier Name")
                    transp_logradouro = st.text_input("Carrier Address")
                    transp_numero = st.text_input("Carrier Number")
                with col2:
                    transp_bairro = st.text_input("Carrier Neighborhood")
                    transp_cidade = st.text_input("Carrier City")
                    transp_uf = st.text_input("Carrier State")
                    transp_zip = st.text_input("Carrier ZIP")
                
                st.subheader("Items")
                items = []
                num_items = st.number_input("Number of items", min_value=1, max_value=10, value=1, step=1)
                for i in range(int(num_items)):
                    st.markdown(f"**Item {i+1}**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        sku = st.text_input(f"SKU {i+1}", key=f"sku_{i}")
                        qtd = st.number_input(f"Quantity {i+1}", value=1.0, step=0.5, format="%.2f", key=f"qtd_{i}")
                        valor_unitario = st.number_input(f"Unit Price {i+1}", value=0.0, step=1.0, key=f"val_{i}")
                    with col2:
                        sku_desc = st.text_input(f"SKU Description {i+1}", key=f"desc_{i}")
                        lote_fab = st.text_input(f"Manufacturing Lot {i+1}", key=f"lot_{i}")
                        classe_prod = st.text_input(f"Product Class {i+1}", key=f"class_{i}")
                    with col3:
                        recdet_linha = st.text_input(f"Line Number {i+1}", value=f"{i+1:05d}", key=f"line_{i}")
                        data_fab = st.date_input(f"Manufacturing Date {i+1}", key=f"fab_{i}")
                        data_val = st.date_input(f"Expiration Date {i+1}", key=f"val_{i}")
                        ean = st.text_input(f"EAN {i+1}", key=f"ean_{i}")
                    
                    items.append({
                        "sku": sku,
                        "sku_descricao": sku_desc,
                        "recdet_linha": recdet_linha,
                        "qtde": qtd,
                        "lote_fabricacao": lote_fab,
                        "data_fabricacao": str(data_fab),
                        "data_validade": str(data_val),
                        "valor_unitario": valor_unitario,
                        "classe_produto": classe_prod,
                        "ean": ean
                    })
                
                submit = st.form_submit_button("Create ASN", type="primary")
                
                if submit:
                    tipo_value = tipo.split(" - ")[0]
                    asn_payload = {
                        "recebimento": {
                            "proprietario": proprietario,
                            "recebimento_externo": recebimento_externo,
                            "recebimento_externo2": recebimento_externo2,
                            "tipo": tipo_value,
                            "data_emissao": data_emissao.strftime("%Y-%m-%dT%H:%M:%S"),
                            "valor_bruto": valor_bruto,
                            "valor_liquido": valor_liquido,
                            "texto_livre5": texto_livre5,
                            "texto_livre6": texto_livre6,
                            "texto_livre7": texto_livre7,
                            "filial": filial
                        },
                        "expedidor": {
                            "exp_cnpj": exp_cnpj,
                            "exp_nome": exp_nome,
                            "exp_logradouro": exp_logradouro,
                            "exp_numero": exp_numero,
                            "exp_complemento": exp_complemento,
                            "exp_bairro": exp_bairro,
                            "exp_cidade": exp_cidade,
                            "exp_uf": exp_uf,
                            "exp_cep": exp_cep
                        },
                        "transportadora": {
                            "transp_cnpj": transp_cnpj,
                            "transp_nome": transp_nome,
                            "transp_logradouro": transp_logradouro,
                            "transp_numero": transp_numero,
                            "transp_bairro": transp_bairro,
                            "transp_cidade": transp_cidade,
                            "transp_uf": transp_uf,
                            "transp_zip": transp_zip
                        },
                        "recebimentodetalhes": items
                    }
                    
                    with st.spinner("Creating ASN..."):
                        result = services.create_asn(asn_payload)
                        display_api_response(result)
        
        # Tab 3: Billing Confirmation
        with tab3:
            st.header("Billing Confirmation")
            st.markdown("Confirm billing with order details.")
            
            with st.form("billing_form"):
                col1, col2 = st.columns(2)
                with col1:
                    proprietario = st.text_input("Owner", value="LAGGO01")
                    orderkey = st.text_input("Order Key (Infor)", value="0000231")
                    ordem_externa = st.text_input("External Order", value="ORDEXT123456")
                with col2:
                    ordem_externa2 = st.text_input("External Order 2", value="ORDEXT123456")
                    filial = st.text_input("Branch", value="wmwhse1")
                
                st.subheader("Order Items")
                items = []
                num_items = st.number_input("Number of items", min_value=1, value=1, step=1, key="bill_items")
                for i in range(int(num_items)):
                    st.markdown(f"**Item {i+1}**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        sku = st.text_input(f"SKU {i+1}", key=f"bill_sku_{i}")
                    with col2:
                        linha = st.text_input(f"Line {i+1}", value=f"{i+1:04d}", key=f"bill_linha_{i}")
                    with col3:
                        qtd = st.number_input(f"Quantity Shipped {i+1}", value=1.0, step=0.5, format="%.2f", key=f"bill_qtd_{i}")
                    items.append({"sku": sku, "linha": linha, "qtd_expedido": qtd})
                
                submit = st.form_submit_button("Confirm Billing", type="primary")
                
                if submit:
                    billing_payload = {
                        "confirmacaoFaturamento": {
                            "proprietario": proprietario,
                            "orderkey": orderkey,
                            "ordem_externa": ordem_externa,
                            "ordem_externa2": ordem_externa2,
                            "filial": filial,
                            "detalheconfirmacao": items[0] if len(items) == 1 else items
                        }
                    }
                    if len(items) > 1:
                        billing_payload["confirmacaoFaturamento"]["detalheconfirmacao"] = items
                    
                    with st.spinner("Sending billing confirmation..."):
                        result = services.confirm_billing(billing_payload)
                        display_api_response(result)
        
        # Tab 4: Weight & Volume
        with tab4:
            st.header("Weight & Volume Confirmation")
            st.markdown("Send packing information after order packing.")
            
            with st.form("weight_volume_form"):
                col1, col2 = st.columns(2)
                with col1:
                    proprietario = st.text_input("Owner", value="POLITEC")
                    orderkey = st.text_input("Order Key", value="0000231")
                with col2:
                    ordem_externa = st.text_input("External Order", value="ORDEXT123456")
                    filial = st.text_input("Branch", value="wmwhse1")
                
                col1, col2 = st.columns(2)
                with col1:
                    volume_total = st.number_input("Total Volume (m³)", value=0.0, step=0.1)
                with col2:
                    peso_total = st.number_input("Total Weight (kg)", value=0.0, step=0.1)
                
                ordem_externa2 = st.text_input("External Order 2 (Optional)", placeholder="Document reference like NFE")
                
                submit = st.form_submit_button("Send Weight & Volume", type="primary")
                
                if submit:
                    payload = {
                        "proprietario": proprietario,
                        "orderkey": orderkey,
                        "ordem_externa": ordem_externa,
                        "ordem_externa2": ordem_externa2,
                        "filial": filial,
                        "Volume_total": volume_total,
                        "Peso_total": peso_total
                    }
                    with st.spinner("Sending weight/volume data..."):
                        result = services.send_weight_volume(payload)
                        display_api_response(result)
        
        # Tab 5: Receipt Confirmation
        with tab5:
            st.header("Receipt Confirmation")
            st.markdown("Confirm receipt of goods after ASN closure.")
            
            with st.form("receipt_form"):
                st.subheader("Receiving Header")
                col1, col2 = st.columns(2)
                with col1:
                    proprietario = st.text_input("Owner", value="LAGGO01")
                    recebimento_externo = st.text_input("External Receipt Number", value="CHAVENOTA323456789")
                with col2:
                    filial = st.text_input("Branch", value="wmhsel")
                
                st.subheader("Received Items")
                items = []
                num_items = st.number_input("Number of items", min_value=1, value=1, step=1, key="rec_items")
                for i in range(int(num_items)):
                    st.markdown(f"**Item {i+1}**")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        sku = st.text_input(f"SKU {i+1}", key=f"rec_sku_{i}")
                        recdet_lin_ext = st.text_input(f"External Line {i+1}", value=f"{i+1:05d}", key=f"rec_line_{i}")
                    with col2:
                        qtde = st.number_input(f"Expected Qty {i+1}", value=0.0, step=0.5, format="%.5f", key=f"rec_qtde_{i}")
                        qtde_recebida = st.number_input(f"Received Qty {i+1}", value=0.0, step=0.5, format="%.5f", key=f"rec_rec_{i}")
                    with col3:
                        lote_fab = st.text_input(f"Lot {i+1}", key=f"rec_lot_{i}")
                        data_fab = st.date_input(f"Manufacturing Date {i+1}", key=f"rec_fab_{i}")
                    with col4:
                        data_val = st.date_input(f"Expiration Date {i+1}", key=f"rec_val_{i}")
                        numero_serie = st.text_input(f"Serial Number {i+1}", key=f"rec_serie_{i}")
                    
                    items.append({
                        "sku": sku,
                        "recdet_lin_ext": recdet_lin_ext,
                        "qtde": qtde,
                        "qtde_recebida": qtde_recebida,
                        "lote_fabricacao": lote_fab,
                        "data_fabricacao": str(data_fab),
                        "data_validade": str(data_val),
                        "numero_serie": numero_serie
                    })
                
                submit = st.form_submit_button("Confirm Receipt", type="primary")
                
                if submit:
                    receipt_payload = {
                        "recebimento": {
                            "proprietario": proprietario,
                            "recebimento_externo": recebimento_externo,
                            "filial": filial
                        },
                        "recebimentodetalhes": items
                    }
                    with st.spinner("Confirming receipt..."):
                        result = services.confirm_receipt(receipt_payload)
                        display_api_response(result)
        
        # Tab 6: Billing Data Update
        with tab6:
            st.header("Billing Data Update")
            st.markdown("Update billing data with shipper and carrier information.")
            
            with st.form("update_form"):
                col1, col2 = st.columns(2)
                with col1:
                    documentId = st.text_input("Document ID (External Order Number)")
                    accountingEntity = st.text_input("Owner (Accounting Entity)")
                with col2:
                    # Additional fields as per documentation
                    shipper_cnpj = st.text_input("Shipper CNPJ")
                    carrier_cnpj = st.text_input("Carrier CNPJ")
                
                st.markdown("Additional update data can be added in JSON format:")
                additional_data = st.text_area("Additional JSON Data", "{}")
                
                submit = st.form_submit_button("Update Billing Data", type="primary")
                
                if submit:
                    try:
                        extra = json.loads(additional_data) if additional_data else {}
                        payload = {
                            "documentId": documentId,
                            "accountingEntity": accountingEntity,
                            "expedidor": {"exp_cnpj": shipper_cnpj} if shipper_cnpj else {},
                            "transportadora": {"transp_cnpj": carrier_cnpj} if carrier_cnpj else {},
                            **extra
                        }
                        with st.spinner("Updating billing data..."):
                            result = services.update_billing_data(payload)
                            display_api_response(result)
                    except json.JSONDecodeError:
                        st.error("Invalid JSON in additional data.")
    else:
        st.info("👈 Please configure authentication in the sidebar to start using the API integrations.")

if __name__ == "__main__":
    main()
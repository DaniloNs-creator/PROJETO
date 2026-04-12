import streamlit as st
import pandas as pd
import io
import copy

# Configuração da página
st.set_page_config(page_title="Editor Profissional de EFD", layout="wide")

# --- 1. DEFINIÇÕES E LAYOUTS DOS REGISTROS ---
# Para um app profissional, essa parte seria muito mais extensa,
# cobrindo todos os registros definidos nos Guias Práticos.
# Aqui focamos nos principais para demonstrar a lógica completa.

# Layout EFD ICMS/IPI (Exemplo parcial para Bloco C)
EFD_ICMS_LAYOUT = {
    '0000': ['REG', 'COD_VER', 'COD_FIN', 'DT_INI', 'DT_FIN', 'NOME', 'CNPJ', 'CPF', 'UF', 'IE', 'COD_MUN', 'IM', 'SUFRAMA', 'IND_PERFIL', 'IND_ATIV'],
    'C100': ['REG', 'IND_OPER', 'IND_EMIT', 'COD_PART', 'COD_MOD', 'COD_SIT', 'SER', 'NUM_DOC', 'CHV_NFE', 'DT_DOC', 'DT_E_S', 'VL_DOC', 'IND_PGTO', 'VL_DESC', 'VL_ABAT_NT', 'VL_MERC', 'IND_FRT', 'VL_FRT', 'VL_SEG', 'VL_OUT_DA', 'VL_BC_ICMS', 'VL_ICMS', 'VL_BC_ICMS_ST', 'VL_ICMS_ST', 'VL_IPI', 'VL_PIS', 'VL_COFINS', 'VL_PIS_ST', 'VL_COFINS_ST'],
    'C170': ['REG', 'NUM_ITEM', 'COD_ITEM', 'DESCR_COMPL', 'QTD', 'UNID', 'VL_ITEM', 'VL_DESC', 'IND_MOV', 'CST_ICMS', 'CFOP', 'COD_NAT', 'VL_BC_ICMS', 'ALIQ_ICMS', 'VL_ICMS', 'VL_BC_ICMS_ST', 'ALIQ_ST', 'VL_ICMS_ST', 'IND_APUR', 'CST_IPI', 'COD_ENQ', 'VL_BC_IPI', 'ALIQ_IPI', 'VL_IPI', 'CST_PIS', 'VL_BC_PIS', 'ALIQ_PIS', 'QUANT_BC_PIS', 'ALIQ_PIS_REAIS', 'VL_PIS', 'CST_COFINS', 'VL_BC_COFINS', 'ALIQ_COFINS', 'QUANT_BC_COFINS', 'ALIQ_COFINS_REAIS', 'VL_COFINS', 'COD_CTA'],
    'C190': ['REG', 'CST_ICMS', 'CFOP', 'ALIQ_ICMS', 'VL_OPR', 'VL_BC_ICMS', 'VL_ICMS', 'VL_BC_ICMS_ST', 'VL_ICMS_ST', 'VL_RED_BC', 'COD_OBS'],
    'C001': ['REG', 'IND_MOV'],
    'C990': ['REG', 'QTD_LIN_C'],
    '0990': ['REG', 'QTD_LIN_0'],
    '9001': ['REG', 'IND_MOV'],
    '9900': ['REG', 'REG_BLC', 'QTD_REG_BLC'],
    '9999': ['REG', 'QTD_LIN']
}

# Layout EFD Contribuições (Exemplo parcial para Bloco M e P)
EFD_CONTRIB_LAYOUT = {
    '0000': ['REG', 'COD_VER', 'TIPO_ESCRIT', 'IND_SIT_ESP', 'NUM_REC_ANTERIOR', 'DT_INI', 'DT_FIN', 'NOME', 'CNPJ', 'UF', 'COD_MUN', 'SUFRAMA', 'IND_NAT_PJ', 'IND_ATIV'],
    'M100': ['REG', 'COD_CRED', 'IND_CRED_ORI', 'VL_BC_PIS', 'ALIQ_PIS', 'QUANT_BC_PIS', 'ALIQ_PIS_QUANT', 'VL_CRED', 'VL_AJUS_ACRES', 'VL_AJUS_REDUC', 'VL_CRED_DIF', 'VL_CRED_DISP', 'IND_DESC_CRED', 'VL_CRED_DESC', 'SLD_CRED'],
    'M200': ['REG', 'VL_TOT_CRED', 'VL_TOT_CRED_DESC', 'VL_TOT_CRED_DISP', 'VL_TOT_CRED_EXT', 'VL_TOT_CRED_EXT_DESC', 'VL_TOT_CRED_EXT_DISP'],
    'M500': ['REG', 'COD_CRED', 'IND_CRED_ORI', 'VL_BC_PIS', 'ALIQ_PIS', 'QUANT_BC_PIS', 'ALIQ_PIS_QUANT', 'VL_CRED', 'VL_AJUS_ACRES', 'VL_AJUS_REDUC', 'VL_CRED_DIF', 'VL_CRED_DISP', 'IND_DESC_CRED', 'VL_CRED_DESC', 'SLD_CRED'],
    'M600': ['REG', 'VL_TOT_CRED', 'VL_TOT_CRED_DESC', 'VL_TOT_CRED_DISP', 'VL_TOT_CRED_EXT', 'VL_TOT_CRED_EXT_DESC', 'VL_TOT_CRED_EXT_DISP'],
    'P100': ['REG', 'DT_INI', 'DT_FIN', 'VL_REC_TOT_EST', 'COD_CTA', 'VL_REC_ATIV', 'VL_REC_DEMAIS', 'INFO_COMPL'],
    'P200': ['REG', 'VL_REC_TOT_EST', 'VL_REC_ATIV', 'VL_REC_DEMAIS', 'VL_REC_TOT_EST_ANT', 'VL_REC_ATIV_ANT', 'VL_REC_DEMAIS_ANT'],
    '0001': ['REG', 'IND_MOV'],
    'M001': ['REG', 'IND_MOV'],
    'M990': ['REG', 'QTD_LIN_M'],
    'P001': ['REG', 'IND_MOV'],
    'P990': ['REG', 'QTD_LIN_P'],
    '0990': ['REG', 'QTD_LIN_0'],
    '9001': ['REG', 'IND_MOV'],
    '9900': ['REG', 'REG_BLC', 'QTD_REG_BLC'],
    '9999': ['REG', 'QTD_LIN']
}

# --- 2. FUNÇÃO DE PARSING (ENTRADA) ---
def parse_efd(file_content):
    """Lê um arquivo EFD e organiza os registros em um dicionário de DataFrames."""
    data = {}
    lines = file_content.decode('utf-8').strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line == '':
            continue
        
        parts = line.split('|')
        # Remove strings vazias no início e no fim devido ao delimitador '|'
        parts = [p for p in parts if p != '']
        if not parts:
            continue
            
        reg_type = parts[0]
        
        # Inicializa o DataFrame se não existir
        if reg_type not in data:
            data[reg_type] = []
        
        data[reg_type].append(parts)
    
    # Converte listas para DataFrames e aplica o layout
    for reg, rows in data.items():
        if reg in EFD_ICMS_LAYOUT:
            columns = EFD_ICMS_LAYOUT[reg]
        elif reg in EFD_CONTRIB_LAYOUT:
            columns = EFD_CONTRIB_LAYOUT[reg]
        else:
            # Registro desconhecido, tenta inferir a estrutura
            max_len = max(len(row) for row in rows)
            columns = ['REG'] + [f'CAMPO_{i}' for i in range(1, max_len)]
            st.warning(f"Registro '{reg}' não mapeado. Usando layout inferido.")
            
        # Ajusta linhas para o número correto de colunas
        adjusted_rows = []
        for row in rows:
            if len(row) < len(columns):
                row.extend([''] * (len(columns) - len(row)))
            elif len(row) > len(columns):
                row = row[:len(columns)]
            adjusted_rows.append(row)
            
        data[reg] = pd.DataFrame(adjusted_rows, columns=columns)
    
    return data

# --- 3. FUNÇÕES DE RECÁLCULO ---

def recalcular_icms(efd_data):
    """Recalcula totais do C100 e gera novos C190 com base nos C170."""
    if 'C100' not in efd_data or 'C170' not in efd_data:
        return efd_data

    df_c100 = efd_data['C100'].copy()
    df_c170 = efd_data['C170'].copy()
    novos_c190 = []

    # Agrupa C170 por chave do C100 (índice + outros campos únicos)
    for idx, c100_row in df_c100.iterrows():
        # Simples: usamos o índice como ID
        itens = df_c170[df_c170.index == idx] # Na prática, precisa de lógica de relacionamento real
        
        # Recalcula totais no C100
        df_c100.at[idx, 'VL_BC_ICMS'] = itens['VL_BC_ICMS'].astype(float).sum()
        df_c100.at[idx, 'VL_ICMS'] = itens['VL_ICMS'].astype(float).sum()
        df_c100.at[idx, 'VL_IPI'] = itens['VL_IPI'].astype(float).sum()
        df_c100.at[idx, 'VL_PIS'] = itens['VL_PIS'].astype(float).sum()
        df_c100.at[idx, 'VL_COFINS'] = itens['VL_COFINS'].astype(float).sum()

        # Recalcula C190 (agrupado por CST_ICMS, CFOP, ALIQ_ICMS)
        if not itens.empty:
            agrupado = itens.groupby(['CST_ICMS', 'CFOP', 'ALIQ_ICMS']).agg({
                'VL_ITEM': 'sum', # VL_OPR
                'VL_BC_ICMS': 'sum',
                'VL_ICMS': 'sum',
                'VL_BC_ICMS_ST': 'sum',
                'VL_ICMS_ST': 'sum'
            }).reset_index()
            
            for _, grupo in agrupado.iterrows():
                novo_c190 = {
                    'REG': 'C190',
                    'CST_ICMS': grupo['CST_ICMS'],
                    'CFOP': grupo['CFOP'],
                    'ALIQ_ICMS': grupo['ALIQ_ICMS'],
                    'VL_OPR': grupo['VL_ITEM'],
                    'VL_BC_ICMS': grupo['VL_BC_ICMS'],
                    'VL_ICMS': grupo['VL_ICMS'],
                    'VL_BC_ICMS_ST': grupo['VL_BC_ICMS_ST'],
                    'VL_ICMS_ST': grupo['VL_ICMS_ST'],
                    'VL_RED_BC': '0.00', # Ajustar conforme regra
                    'COD_OBS': ''
                }
                novos_c190.append(novo_c190)

    efd_data['C100'] = df_c100
    if novos_c190:
        efd_data['C190'] = pd.DataFrame(novos_c190)
    else:
        efd_data.pop('C190', None)
        
    return efd_data

def recalcular_contrib(efd_data):
    """Recalcula M200 com base nos M100 e M600 com base nos M500."""
    # M200 a partir de M100
    if 'M100' in efd_data:
        df_m100 = efd_data['M100']
        vl_tot_cred = df_m100['VL_CRED'].astype(float).sum()
        vl_tot_cred_desc = df_m100['VL_CRED_DESC'].astype(float).sum()
        vl_tot_cred_disp = df_m100['VL_CRED_DISP'].astype(float).sum()
        
        novo_m200 = {
            'REG': 'M200',
            'VL_TOT_CRED': f"{vl_tot_cred:.2f}",
            'VL_TOT_CRED_DESC': f"{vl_tot_cred_desc:.2f}",
            'VL_TOT_CRED_DISP': f"{vl_tot_cred_disp:.2f}",
            'VL_TOT_CRED_EXT': '0.00',
            'VL_TOT_CRED_EXT_DESC': '0.00',
            'VL_TOT_CRED_EXT_DISP': '0.00'
        }
        efd_data['M200'] = pd.DataFrame([novo_m200])

    # M600 a partir de M500
    if 'M500' in efd_data:
        df_m500 = efd_data['M500']
        vl_tot_cred = df_m500['VL_CRED'].astype(float).sum()
        vl_tot_cred_desc = df_m500['VL_CRED_DESC'].astype(float).sum()
        vl_tot_cred_disp = df_m500['VL_CRED_DISP'].astype(float).sum()
        
        novo_m600 = {
            'REG': 'M600',
            'VL_TOT_CRED': f"{vl_tot_cred:.2f}",
            'VL_TOT_CRED_DESC': f"{vl_tot_cred_desc:.2f}",
            'VL_TOT_CRED_DISP': f"{vl_tot_cred_disp:.2f}",
            'VL_TOT_CRED_EXT': '0.00',
            'VL_TOT_CRED_EXT_DESC': '0.00',
            'VL_TOT_CRED_EXT_DISP': '0.00'
        }
        efd_data['M600'] = pd.DataFrame([novo_m600])
        
    return efd_data

# --- 4. FUNÇÃO DE ESCRITA (SAÍDA) ---
def write_efd(efd_data):
    """Gera um novo arquivo EFD .txt a partir dos DataFrames, respeitando a hierarquia."""
    output_lines = []
    
    # Ordem básica dos blocos
    block_order = ['0000', '0001', '0990', # Bloco 0
                   'C001', 'C100', 'C170', 'C190', 'C990', # Bloco C (ICMS/IPI)
                   'M001', 'M100', 'M200', 'M500', 'M600', 'M990', # Bloco M (Contrib)
                   'P001', 'P100', 'P200', 'P990', # Bloco P (Contrib)
                   '9001', '9900', '9999'] # Bloco 9
    
    # Adiciona registros na ordem definida
    for reg in block_order:
        if reg in efd_data:
            df = efd_data[reg]
            for _, row in df.iterrows():
                line = '|' + '|'.join(str(v) for v in row.values) + '|\n'
                output_lines.append(line)
    
    # Adiciona quaisquer registros não mapeados na ordem
    for reg, df in efd_data.items():
        if reg not in block_order:
            for _, row in df.iterrows():
                line = '|' + '|'.join(str(v) for v in row.values) + '|\n'
                output_lines.append(line)
                
    return ''.join(output_lines)

# --- 5. INTERFACE DO USUÁRIO COM STREAMLIT ---

def main():
    st.title("📊 Editor Profissional de EFD (ICMS/IPI e Contribuições)")
    st.markdown("""
    **Instruções:**
    1.  Faça o upload de um arquivo EFD (`.txt`).
    2.  Selecione o tipo de EFD (ICMS/IPI ou Contribuições).
    3.  Escolha o registro que deseja visualizar e editar.
    4.  Edite os valores diretamente na tabela.
    5.  Clique em "Reprocessar Cálculos" para atualizar registros pais.
    6.  Baixe o novo arquivo EFD corrigido.
    """)

    uploaded_file = st.file_uploader("Carregue seu arquivo EFD (.txt)", type=['txt'])

    if uploaded_file is not None:
        # Armazena o arquivo no estado da sessão
        if 'efd_data' not in st.session_state or st.button("Recarregar Arquivo Original"):
            with st.spinner("Analisando arquivo EFD..."):
                st.session_state.efd_data = parse_efd(uploaded_file.getvalue())
                st.session_state.efd_type = st.radio("Tipo de EFD:", ('ICMS/IPI', 'Contribuições'), index=0)
            st.success("Arquivo carregado e analisado com sucesso!")

        efd_data = st.session_state.efd_data
        efd_type = st.session_state.efd_type

        # Seleção do Registro
        registros_disponiveis = list(efd_data.keys())
        registro_selecionado = st.selectbox("Selecione o Registro para Editar:", registros_disponiveis)

        if registro_selecionado:
            st.subheader(f"Editando Registro: {registro_selecionado}")
            df_original = efd_data[registro_selecionado].copy()

            # Editor de dados
            df_editado = st.data_editor(
                df_original,
                num_rows="dynamic",
                use_container_width=True,
                key=f"editor_{registro_selecionado}"
            )

            # Botões de Ação
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Salvar Edições do Registro", type="primary"):
                    st.session_state.efd_data[registro_selecionado] = df_editado
                    st.success(f"Registro {registro_selecionado} atualizado na memória.")
            
            with col2:
                if st.button("🔄 Reprocessar Cálculos"):
                    with st.spinner("Recalculando registros dependentes..."):
                        if efd_type == 'ICMS/IPI':
                            st.session_state.efd_data = recalcular_icms(st.session_state.efd_data)
                        else:
                            st.session_state.efd_data = recalcular_contrib(st.session_state.efd_data)
                    st.success("Recálculo concluído! Registros pai (C100, M200, M600) atualizados.")
                    st.rerun()
            
            with col3:
                if st.button("📥 Gerar e Baixar Novo Arquivo EFD"):
                    novo_conteudo = write_efd(st.session_state.efd_data)
                    st.download_button(
                        label="Clique para baixar o arquivo",
                        data=novo_conteudo,
                        file_name=f"efd_atualizado_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                    st.info("Arquivo gerado com sucesso!")

if __name__ == "__main__":
    main()

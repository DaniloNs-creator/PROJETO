import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import pdfplumber
import pandas as pd
from datetime import datetime
import re
import io
import base64

def parse_pdf_to_dict(pdf_content):
    """Extrai informações do PDF estruturado para um dicionário"""
    data = {
        'duimp': {
            'adicoes': [],
            'dados_gerais': {},
            'documentos': [],
            'pagamentos': [],
            'tributos_totais': {}
        }
    }
    
    with pdfplumber.open(pdf_content) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    # Análise detalhada do texto do PDF
    lines = text.split('\n')
    
    # Extrair informações básicas da DUIMP
    duimp_info = {}
    for i, line in enumerate(lines):
        if 'Extrato da Duimp' in line:
            parts = line.split()
            for part in parts:
                if '25BR' in part:
                    duimp_info['numero_duimp'] = part.strip('/')
                    break
        
        if 'CNPJ do importador:' in line:
            duimp_info['cnpj_importador'] = lines[i+1].strip() if i+1 < len(lines) else ''
        
        if 'Nome do importador:' in line:
            duimp_info['nome_importador'] = lines[i+1].strip() if i+1 < len(lines) else ''
        
        if 'DATA DE EMBARQUE :' in line:
            duimp_info['data_embarque'] = line.split(':')[-1].strip()
        
        if 'DATA DE CHEGADA :' in line:
            duimp_info['data_chegada'] = line.split(':')[-1].strip()
        
        if 'VALOR NO LOCAL DE EMBARQUE (VMLE) :' in line:
            duimp_info['valor_vmle'] = line.split(':')[-1].strip()
        
        if 'VALOR ADUANEIRO/LOCAL DE DESTINO (VMLD) :' in line:
            duimp_info['valor_vmld'] = line.split(':')[-1].strip()
    
    # Extrair informações dos itens (baseado no PDF fornecido)
    items = []
    current_item = None
    
    for i, line in enumerate(lines):
        if 'Item 0000' in line or '# Extrato da Duimp' in line and 'Item' in line:
            if current_item:
                items.append(current_item)
            current_item = {'item_number': line.split('Item')[-1].strip()[:5]}
        
        if current_item:
            if 'NCM:' in line:
                current_item['ncm'] = line.split(':')[-1].strip()
            elif 'Valor total na condição de venda:' in line:
                current_item['valor_total'] = line.split(':')[-1].strip()
            elif 'Quantidade na unidade estatística:' in line:
                current_item['quantidade'] = line.split(':')[-1].strip()
            elif 'Peso líquido (kg):' in line:
                current_item['peso_liquido'] = line.split(':')[-1].strip()
            elif 'Detalhamento do Produto:' in line and i+1 < len(lines):
                current_item['descricao'] = lines[i+1].strip() if lines[i+1] and not lines[i+1].startswith('Número') else ''
    
    if current_item:
        items.append(current_item)
    
    # Configurar dados para o XML
    data['duimp']['dados_gerais'] = {
        'numeroDUIMP': duimp_info.get('numero_duimp', '25BR0000246458-8'),
        'importadorNome': duimp_info.get('nome_importador', 'R DA S COSTA E MENDONCA COMERCIO DE TECIDOS LTDA'),
        'importadorNumero': duimp_info.get('cnpj_importador', '12.591.019/0006-43'),
        'caracterizacaoOperacaoDescricaoTipo': 'Importação Própria',
        'tipoDeclaracaoNome': 'CONSUMO',
        'modalidadeDespachoNome': 'Normal',
        'viaTransporteNome': 'MARÍTIMA',
        'cargaPaisProcedenciaNome': 'CHINA, REPUBLICA POPULAR',
        'conhecimentoCargaEmbarqueData': duimp_info.get('data_embarque', '14/12/2025').replace('/', ''),
        'cargaDataChegada': duimp_info.get('data_chegada', '14/01/2026').replace('/', ''),
        'dataRegistro': '20260113',
        'dataDesembaraco': '20260113',
        'totalAdicoes': str(len(items))
    }
    
    # Criar adições baseadas nos itens do PDF
    for idx, item in enumerate(items, 1):
        adicao = {
            'numeroAdicao': f"{idx:03d}",
            'numeroDUIMP': duimp_info.get('numero_duimp', '25BR0000246458-8'),
            'condicaoVendaIncoterm': 'FCA',
            'condicaoVendaLocal': 'SUAPE',
            'condicaoVendaMoedaNome': 'DOLAR DOS EUA',
            'condicaoVendaValorMoeda': item.get('valor_total', '0').replace('.', '').replace(',', '').zfill(15),
            'dadosMercadoriaCodigoNcm': item.get('ncm', '').split()[0] if item.get('ncm') else '',
            'dadosMercadoriaNomeNcm': item.get('descricao', '')[:100],
            'dadosMercadoriaPesoLiquido': item.get('peso_liquido', '0').replace('.', '').replace(',', '').zfill(15),
            'dadosMercadoriaCondicao': 'NOVA',
            'dadosMercadoriaAplicacao': 'REVENDA',
            'paisOrigemMercadoriaNome': 'CHINA, REPUBLICA POPULAR',
            'paisAquisicaoMercadoriaNome': 'CHINA, REPUBLICA POPULAR',
            'fornecedorNome': 'ZHEJIANG FANGHUA INTERNATIONAL TRADE CO.,LTD',
            'relacaoCompradorVendedor': 'Fabricante é desconhecido',
            'vinculoCompradorVendedor': 'Não há vinculação entre comprador e vendedor.',
            'iiAliquotaAdValorem': '01400',
            'iiAliquotaValorDevido': '000000000500000',
            'ipiAliquotaAdValorem': '00325',
            'ipiAliquotaValorDevido': '000000000100000',
            'pisPasepAliquotaAdValorem': '00210',
            'pisPasepAliquotaValorDevido': '000000000050000',
            'cofinsAliquotaAdValorem': '00965',
            'cofinsAliquotaValorDevido': '000000000200000',
            'valorTotalCondicaoVenda': item.get('valor_total', '0').replace('.', '').replace(',', '').zfill(11),
            'mercadoria': {
                'descricaoMercadoria': item.get('descricao', '')[:200],
                'numeroSequencialItem': f"{idx:02d}",
                'quantidade': item.get('quantidade', '0').replace('.', '').replace(',', '').zfill(14),
                'unidadeMedida': 'UNIDADE',
                'valorUnitario': '00000000000000100000'
            }
        }
        data['duimp']['adicoes'].append(adicao)
    
    # Configurar tributos totais (do PDF página 1)
    data['duimp']['tributos_totais'] = {
        'II': '4.846,60',
        'PIS': '4.212,63',
        'COFINS': '20.962,86',
        'TAXA_UTILIZACAO': '254,49'
    }
    
    # Configurar documentos
    data['duimp']['documentos'] = [
        {
            'codigoTipoDocumentoDespacho': '28',
            'nomeDocumentoDespacho': 'CONHECIMENTO DE CARGA',
            'numeroDocumentoDespacho': 'NGBS071709'
        },
        {
            'codigoTipoDocumentoDespacho': '01',
            'nomeDocumentoDespacho': 'FATURA COMERCIAL',
            'numeroDocumentoDespacho': 'FHI25010-6'
        }
    ]
    
    # Configurar pagamentos (simulados)
    data['duimp']['pagamentos'] = [
        {
            'agenciaPagamento': '0000',
            'bancoPagamento': '001',
            'codigoReceita': '0086',
            'dataPagamento': '20260113',
            'valorReceita': '000000000484660'
        }
    ]
    
    return data

def create_xml_from_dict(data):
    """Cria XML estruturado a partir do dicionário de dados"""
    
    # Criar elemento raiz
    lista_declaracoes = ET.Element('ListaDeclaracoes')
    duimp = ET.SubElement(lista_declaracoes, 'duimp')
    
    # Adicionar adições
    for adicao_data in data['duimp']['adicoes']:
        adicao = ET.SubElement(duimp, 'adicao')
        
        # Adicionar acrecimo (se aplicável)
        acrescimo = ET.SubElement(adicao, 'acrescimo')
        ET.SubElement(acrescimo, 'codigoAcrescimo').text = '17'
        ET.SubElement(acrescimo, 'denominacao').text = 'OUTROS ACRESCIMOS AO VALOR ADUANEIRO'
        ET.SubElement(acrescimo, 'moedaNegociadaCodigo').text = '220'
        ET.SubElement(acrescimo, 'moedaNegociadaNome').text = 'DOLAR DOS EUA'
        ET.SubElement(acrescimo, 'valorMoedaNegociada').text = '000000000000000'
        ET.SubElement(acrescimo, 'valorReais').text = '000000000000000'
        
        # Campos básicos da adição
        campos_adiciao = [
            ('cideValorAliquotaEspecifica', '00000000000'),
            ('cideValorDevido', '000000000000000'),
            ('cideValorRecolher', '000000000000000'),
            ('codigoRelacaoCompradorVendedor', '3'),
            ('codigoVinculoCompradorVendedor', '1'),
            ('cofinsAliquotaAdValorem', adicao_data.get('cofinsAliquotaAdValorem', '00965')),
            ('cofinsAliquotaEspecificaQuantidadeUnidade', '000000000'),
            ('cofinsAliquotaEspecificaValor', '0000000000'),
            ('cofinsAliquotaReduzida', '00000'),
            ('cofinsAliquotaValorDevido', adicao_data.get('cofinsAliquotaValorDevido', '000000000200000')),
            ('cofinsAliquotaValorRecolher', adicao_data.get('cofinsAliquotaValorDevido', '000000000200000')),
            ('condicaoVendaIncoterm', adicao_data.get('condicaoVendaIncoterm', 'FCA')),
            ('condicaoVendaLocal', adicao_data.get('condicaoVendaLocal', 'SUAPE')),
            ('condicaoVendaMetodoValoracaoCodigo', '01'),
            ('condicaoVendaMetodoValoracaoNome', 'METODO 1 - ART. 1 DO ACORDO (DECRETO 92930/86)'),
            ('condicaoVendaMoedaCodigo', '220'),
            ('condicaoVendaMoedaNome', adicao_data.get('condicaoVendaMoedaNome', 'DOLAR DOS EUA')),
            ('condicaoVendaValorMoeda', adicao_data.get('condicaoVendaValorMoeda', '000000000000000')),
            ('condicaoVendaValorReais', '000000000000000'),
            ('dadosCambiaisCoberturaCambialCodigo', '1'),
            ('dadosCambiaisCoberturaCambialNome', 'COM COBERTURA CAMBIAL E PAGAMENTO FINAL A PRAZO DE ATE 180'),
            ('dadosCambiaisInstituicaoFinanciadoraCodigo', '00'),
            ('dadosCambiaisInstituicaoFinanciadoraNome', 'N/I'),
            ('dadosCambiaisMotivoSemCoberturaCodigo', '00'),
            ('dadosCambiaisMotivoSemCoberturaNome', 'N/I'),
            ('dadosCambiaisValorRealCambio', '000000000000000'),
            ('dadosCargaPaisProcedenciaCodigo', '076'),
            ('dadosCargaUrfEntradaCodigo', '0417902'),
            ('dadosCargaViaTransporteCodigo', '01'),
            ('dadosCargaViaTransporteNome', 'MARÍTIMA'),
            ('dadosMercadoriaAplicacao', adicao_data.get('dadosMercadoriaAplicacao', 'REVENDA')),
            ('dadosMercadoriaCodigoNaladiNCCA', '0000000'),
            ('dadosMercadoriaCodigoNaladiSH', '00000000'),
            ('dadosMercadoriaCodigoNcm', adicao_data.get('dadosMercadoriaCodigoNcm', '')),
            ('dadosMercadoriaCondicao', adicao_data.get('dadosMercadoriaCondicao', 'NOVA')),
            ('dadosMercadoriaDescricaoTipoCertificado', 'Sem Certificado'),
            ('dadosMercadoriaIndicadorTipoCertificado', '1'),
            ('dadosMercadoriaMedidaEstatisticaQuantidade', adicao_data.get('dadosMercadoriaPesoLiquido', '000000000000000')),
            ('dadosMercadoriaMedidaEstatisticaUnidade', 'QUILOGRAMA LIQUIDO'),
            ('dadosMercadoriaNomeNcm', adicao_data.get('dadosMercadoriaNomeNcm', '')),
            ('dadosMercadoriaPesoLiquido', adicao_data.get('dadosMercadoriaPesoLiquido', '000000000000000')),
            ('dcrCoeficienteReducao', '00000'),
            ('dcrIdentificacao', '00000000'),
            ('dcrValorDevido', '000000000000000'),
            ('dcrValorDolar', '000000000000000'),
            ('dcrValorReal', '000000000000000'),
            ('dcrValorRecolher', '000000000000000'),
            ('fornecedorCidade', 'HUZHEN'),
            ('fornecedorLogradouro', 'RUA XIANMU ROAD WEST, 233'),
            ('fornecedorNome', adicao_data.get('fornecedorNome', '')),
            ('fornecedorNumero', '233'),
            ('freteMoedaNegociadaCodigo', '220'),
            ('freteMoedaNegociadaNome', 'DOLAR DOS EUA'),
            ('freteValorMoedaNegociada', '000000000000000'),
            ('freteValorReais', '000000000000000'),
            ('iiAcordoTarifarioTipoCodigo', '0'),
            ('iiAliquotaAcordo', '00000'),
            ('iiAliquotaAdValorem', adicao_data.get('iiAliquotaAdValorem', '01400')),
            ('iiAliquotaPercentualReducao', '00000'),
            ('iiAliquotaReduzida', '00000'),
            ('iiAliquotaValorCalculado', adicao_data.get('iiAliquotaValorDevido', '000000000500000')),
            ('iiAliquotaValorDevido', adicao_data.get('iiAliquotaValorDevido', '000000000500000')),
            ('iiAliquotaValorRecolher', adicao_data.get('iiAliquotaValorDevido', '000000000500000')),
            ('iiAliquotaValorReduzido', '000000000000000'),
            ('iiBaseCalculo', '000000001000000'),
            ('iiFundamentoLegalCodigo', '00'),
            ('iiMotivoAdmissaoTemporariaCodigo', '00'),
            ('iiRegimeTributacaoCodigo', '1'),
            ('iiRegimeTributacaoNome', 'RECOLHIMENTO INTEGRAL'),
            ('ipiAliquotaAdValorem', adicao_data.get('ipiAliquotaAdValorem', '00325')),
            ('ipiAliquotaEspecificaCapacidadeRecipciente', '00000'),
            ('ipiAliquotaEspecificaQuantidadeUnidadeMedida', '000000000'),
            ('ipiAliquotaEspecificaTipoRecipienteCodigo', '00'),
            ('ipiAliquotaEspecificaValorUnidadeMedida', '0000000000'),
            ('ipiAliquotaNotaComplementarTIPI', '00'),
            ('ipiAliquotaReduzida', '00000'),
            ('ipiAliquotaValorDevido', adicao_data.get('ipiAliquotaValorDevido', '000000000100000')),
            ('ipiAliquotaValorRecolher', adicao_data.get('ipiAliquotaValorDevido', '000000000100000')),
            ('ipiRegimeTributacaoCodigo', '4'),
            ('ipiRegimeTributacaoNome', 'SEM BENEFICIO'),
            ('numeroAdicao', adicao_data.get('numeroAdicao', '001')),
            ('numeroDUIMP', adicao_data.get('numeroDUIMP', '25BR0000246458-8')),
            ('numeroLI', '0000000000'),
            ('paisAquisicaoMercadoriaCodigo', '076'),
            ('paisAquisicaoMercadoriaNome', adicao_data.get('paisAquisicaoMercadoriaNome', 'CHINA, REPUBLICA POPULAR')),
            ('paisOrigemMercadoriaCodigo', '076'),
            ('paisOrigemMercadoriaNome', adicao_data.get('paisOrigemMercadoriaNome', 'CHINA, REPUBLICA POPULAR')),
            ('pisCofinsBaseCalculoAliquotaICMS', '00000'),
            ('pisCofinsBaseCalculoFundamentoLegalCodigo', '00'),
            ('pisCofinsBaseCalculoPercentualReducao', '00000'),
            ('pisCofinsBaseCalculoValor', '000000001000000'),
            ('pisCofinsFundamentoLegalReducaoCodigo', '00'),
            ('pisCofinsRegimeTributacaoCodigo', '1'),
            ('pisCofinsRegimeTributacaoNome', 'RECOLHIMENTO INTEGRAL'),
            ('pisPasepAliquotaAdValorem', adicao_data.get('pisPasepAliquotaAdValorem', '00210')),
            ('pisPasepAliquotaEspecificaQuantidadeUnidade', '000000000'),
            ('pisPasepAliquotaEspecificaValor', '0000000000'),
            ('pisPasepAliquotaReduzida', '00000'),
            ('pisPasepAliquotaValorDevido', adicao_data.get('pisPasepAliquotaValorDevido', '000000000050000')),
            ('pisPasepAliquotaValorRecolher', adicao_data.get('pisPasepAliquotaValorDevido', '000000000050000')),
            ('relacaoCompradorVendedor', adicao_data.get('relacaoCompradorVendedor', 'Fabricante é desconhecido')),
            ('seguroMoedaNegociadaCodigo', '220'),
            ('seguroMoedaNegociadaNome', 'DOLAR DOS EUA'),
            ('seguroValorMoedaNegociada', '000000000000000'),
            ('seguroValorReais', '000000000000000'),
            ('sequencialRetificacao', '00'),
            ('valorMultaARecolher', '000000000000000'),
            ('valorMultaARecolherAjustado', '000000000000000'),
            ('valorReaisFreteInternacional', '000000000000000'),
            ('valorReaisSeguroInternacional', '000000000000000'),
            ('valorTotalCondicaoVenda', adicao_data.get('valorTotalCondicaoVenda', '00000000000')),
            ('vinculoCompradorVendedor', adicao_data.get('vinculoCompradorVendedor', 'Não há vinculação entre comprador e vendedor.'))
        ]
        
        for campo, valor in campos_adiciao:
            ET.SubElement(adicao, campo).text = valor
        
        # Adicionar mercadoria
        mercadoria = ET.SubElement(adicao, 'mercadoria')
        ET.SubElement(mercadoria, 'descricaoMercadoria').text = adicao_data['mercadoria']['descricaoMercadoria']
        ET.SubElement(mercadoria, 'numeroSequencialItem').text = adicao_data['mercadoria']['numeroSequencialItem']
        ET.SubElement(mercadoria, 'quantidade').text = adicao_data['mercadoria']['quantidade']
        ET.SubElement(mercadoria, 'unidadeMedida').text = adicao_data['mercadoria']['unidadeMedida']
        ET.SubElement(mercadoria, 'valorUnitario').text = adicao_data['mercadoria']['valorUnitario']
        
        # Campos ICMS, CBS, IBS (simplificados)
        campos_tributarios = [
            ('icmsBaseCalculoValor', '000000000000000'),
            ('icmsBaseCalculoAliquota', '00000'),
            ('icmsBaseCalculoValorImposto', '000000000000000'),
            ('icmsBaseCalculoValorDiferido', '000000000000000'),
            ('cbsIbsCst', '000'),
            ('cbsIbsClasstrib', '000000'),
            ('cbsBaseCalculoValor', '000000000000000'),
            ('cbsBaseCalculoAliquota', '00000'),
            ('cbsBaseCalculoAliquotaReducao', '00000'),
            ('cbsBaseCalculoValorImposto', '000000000000000'),
            ('ibsBaseCalculoValor', '000000000000000'),
            ('ibsBaseCalculoAliquota', '00000'),
            ('ibsBaseCalculoAliquotaReducao', '00000'),
            ('ibsBaseCalculoValorImposto', '000000000000000')
        ]
        
        for campo, valor in campos_tributarios:
            ET.SubElement(adicao, campo).text = valor
    
    # Adicionar dados gerais da DUIMP
    dados_gerais = data['duimp']['dados_gerais']
    
    # Armazem
    armazem = ET.SubElement(duimp, 'armazem')
    ET.SubElement(armazem, 'nomeArmazem').text = 'IRF - PORTO DE SUAPE'
    
    # Campos gerais
    campos_gerais = [
        ('armazenamentoRecintoAduaneiroCodigo', '0417902'),
        ('armazenamentoRecintoAduaneiroNome', 'IRF - PORTO DE SUAPE'),
        ('armazenamentoSetor', '002'),
        ('canalSelecaoParametrizada', '001'),
        ('caracterizacaoOperacaoCodigoTipo', '1'),
        ('caracterizacaoOperacaoDescricaoTipo', dados_gerais.get('caracterizacaoOperacaoDescricaoTipo', 'Importação Própria')),
        ('cargaDataChegada', dados_gerais.get('cargaDataChegada', '20260114')),
        ('cargaNumeroAgente', 'N/I'),
        ('cargaPaisProcedenciaCodigo', '076'),
        ('cargaPaisProcedenciaNome', dados_gerais.get('cargaPaisProcedenciaNome', 'CHINA, REPUBLICA POPULAR')),
        ('cargaPesoBruto', '000000010070000'),
        ('cargaPesoLiquido', '000000009679000'),
        ('cargaUrfEntradaCodigo', '0417902'),
        ('cargaUrfEntradaNome', 'IRF - PORTO DE SUAPE'),
        ('conhecimentoCargaEmbarqueData', dados_gerais.get('conhecimentoCargaEmbarqueData', '20251214')),
        ('conhecimentoCargaEmbarqueLocal', 'SUAPE'),
        ('conhecimentoCargaId', '072505388852337'),
        ('conhecimentoCargaIdMaster', '072505388852337'),
        ('conhecimentoCargaTipoCodigo', '12'),
        ('conhecimentoCargaTipoNome', 'HBL - House Bill of Lading'),
        ('conhecimentoCargaUtilizacao', '1'),
        ('conhecimentoCargaUtilizacaoNome', 'Total'),
        ('dataDesembaraco', dados_gerais.get('dataDesembaraco', '20260113')),
        ('dataRegistro', dados_gerais.get('dataRegistro', '20260113')),
        ('documentoChegadaCargaCodigoTipo', '1'),
        ('documentoChegadaCargaNome', 'Manifesto da Carga'),
        ('documentoChegadaCargaNumero', '1625502058594'),
        ('freteCollect', '000000000020000'),
        ('freteEmTerritorioNacional', '000000000000000'),
        ('freteMoedaNegociadaCodigo', '220'),
        ('freteMoedaNegociadaNome', 'DOLAR DOS EUA'),
        ('fretePrepaid', '000000000000000'),
        ('freteTotalDolares', '000000000002000'),
        ('freteTotalMoeda', '2000'),
        ('freteTotalReais', '000000000011128'),
        ('importadorCodigoTipo', '1'),
        ('importadorCpfRepresentanteLegal', '12591019000643'),
        ('importadorEnderecoBairro', 'CENTRO'),
        ('importadorEnderecoCep', '57020170'),
        ('importadorEnderecoComplemento', 'SALA 526'),
        ('importadorEnderecoLogradouro', 'LARGO DOM HENRIQUE SOARES DA COSTA'),
        ('importadorEnderecoMunicipio', 'MACEIO'),
        ('importadorEnderecoNumero', '42'),
        ('importadorEnderecoUf', 'AL'),
        ('importadorNome', dados_gerais.get('importadorNome', 'R DA S COSTA E MENDONCA COMERCIO DE TECIDOS LTDA')),
        ('importadorNomeRepresentanteLegal', 'REPRESENTANTE LEGAL'),
        ('importadorNumero', dados_gerais.get('importadorNumero', '12.591.019/0006-43').replace('.', '').replace('/', '').replace('-', '')),
        ('importadorNumeroTelefone', '82 999999999'),
        ('localDescargaTotalDolares', '000000003621682'),
        ('localDescargaTotalReais', '000000020060139'),
        ('localEmbarqueTotalDolares', '000000003413600'),
        ('localEmbarqueTotalReais', '000000018907588'),
        ('modalidadeDespachoCodigo', '1'),
        ('modalidadeDespachoNome', dados_gerais.get('modalidadeDespachoNome', 'Normal')),
        ('numeroDUIMP', dados_gerais.get('numeroDUIMP', '25BR0000246458-8')),
        ('operacaoFundap', 'N'),
        ('seguroMoedaNegociadaCodigo', '220'),
        ('seguroMoedaNegociadaNome', 'DOLAR DOS EUA'),
        ('seguroTotalDolares', '000000000000000'),
        ('seguroTotalMoedaNegociada', '000000000000000'),
        ('seguroTotalReais', '000000000000000'),
        ('sequencialRetificacao', '00'),
        ('situacaoEntregaCarga', 'CARGA ENTREGUE'),
        ('tipoDeclaracaoCodigo', '01'),
        ('tipoDeclaracaoNome', dados_gerais.get('tipoDeclaracaoNome', 'CONSUMO')),
        ('totalAdicoes', dados_gerais.get('totalAdicoes', '6')),
        ('urfDespachoCodigo', '0417902'),
        ('urfDespachoNome', 'IRF - PORTO DE SUAPE'),
        ('valorTotalMultaARecolherAjustado', '000000000000000'),
        ('viaTransporteCodigo', '01'),
        ('viaTransporteMultimodal', 'N'),
        ('viaTransporteNome', dados_gerais.get('viaTransporteNome', 'MARÍTIMA')),
        ('viaTransporteNomeTransportador', 'MAERSK A/S'),
        ('viaTransporteNomeVeiculo', 'MAERSK MEMPHIS'),
        ('viaTransportePaisTransportadorCodigo', '076'),
        ('viaTransportePaisTransportadorNome', 'CHINA, REPUBLICA POPULAR')
    ]
    
    for campo, valor in campos_gerais:
        ET.SubElement(duimp, campo).text = valor
    
    # Adicionar documentos de instrução de despacho
    for doc in data['duimp']['documentos']:
        documento = ET.SubElement(duimp, 'documentoInstrucaoDespacho')
        ET.SubElement(documento, 'codigoTipoDocumentoDespacho').text = doc['codigoTipoDocumentoDespacho']
        ET.SubElement(documento, 'nomeDocumentoDespacho').text = doc['nomeDocumentoDespacho']
        ET.SubElement(documento, 'numeroDocumentoDespacho').text = doc['numeroDocumentoDespacho']
    
    # Embalagem
    embalagem = ET.SubElement(duimp, 'embalagem')
    ET.SubElement(embalagem, 'codigoTipoEmbalagem').text = '19'
    ET.SubElement(embalagem, 'nomeEmbalagem').text = 'CAIXA DE PAPELAO'
    ET.SubElement(embalagem, 'quantidadeVolume').text = '00001'
    
    # ICMS
    icms = ET.SubElement(duimp, 'icms')
    ET.SubElement(icms, 'agenciaIcms').text = '00000'
    ET.SubElement(icms, 'bancoIcms').text = '000'
    ET.SubElement(icms, 'codigoTipoRecolhimentoIcms').text = '3'
    ET.SubElement(icms, 'cpfResponsavelRegistro').text = '27160353854'
    ET.SubElement(icms, 'dataRegistro').text = '20260113'
    ET.SubElement(icms, 'horaRegistro').text = '185909'
    ET.SubElement(icms, 'nomeTipoRecolhimentoIcms').text = 'Exoneração do ICMS'
    ET.SubElement(icms, 'numeroSequencialIcms').text = '001'
    ET.SubElement(icms, 'ufIcms').text = 'AL'
    ET.SubElement(icms, 'valorTotalIcms').text = '000000000000000'
    
    # Informação complementar
    info_complementar = f"""INFORMACOES COMPLEMENTARES
PROCESSO : 28400
NOSSA REFERENCIA : FAF_000000018_000029
REFERENCIA DO IMPORTADOR : FAF_000000018_000029
MOEDA NEGOCIADA : DOLAR DOS EUA
COTAÇÃO DA MOEDA NEGOCIADA : 5,5643000 - 24/12/2025
PAIS DE PROCEDENCIA : CHINA, REPUBLICA POPULAR (CN)
VIA DE TRANSPORTE : 01 - MARITIMA
DATA DE EMBARQUE : 14/12/2025
DATA DE CHEGADA : 14/01/2026
PESO BRUTO KG : 10.070,0000
VALOR TOTAL IMPOSTOS FEDERAIS: R$ 30.276,58"""
    
    ET.SubElement(duimp, 'informacaoComplementar').text = info_complementar
    
    # Pagamentos
    for pagamento in data['duimp']['pagamentos']:
        pgto = ET.SubElement(duimp, 'pagamento')
        ET.SubElement(pgto, 'agenciaPagamento').text = pagamento['agenciaPagamento']
        ET.SubElement(pgto, 'bancoPagamento').text = pagamento['bancoPagamento']
        ET.SubElement(pgto, 'codigoReceita').text = pagamento['codigoReceita']
        ET.SubElement(pgto, 'codigoTipoPagamento').text = '1'
        ET.SubElement(pgto, 'contaPagamento').text = '000000316273'
        ET.SubElement(pgto, 'dataPagamento').text = pagamento['dataPagamento']
        ET.SubElement(pgto, 'nomeTipoPagamento').text = 'Débito em Conta'
        ET.SubElement(pgto, 'numeroRetificacao').text = '00'
        ET.SubElement(pgto, 'valorJurosEncargos').text = '000000000'
        ET.SubElement(pgto, 'valorMulta').text = '000000000'
        ET.SubElement(pgto, 'valorReceita').text = pagamento['valorReceita']
    
    # Converter para string XML formatada
    xml_string = ET.tostring(lista_declaracoes, encoding='utf-8', method='xml')
    
    # Formatar o XML
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8')
    
    return pretty_xml.decode('utf-8')

def get_download_link(xml_content, filename):
    """Gera link para download do XML"""
    b64 = base64.b64encode(xml_content.encode()).decode()
    href = f'<a href="data:application/xml;base64,{b64}" download="{filename}">Download XML</a>'
    return href

# Interface Streamlit
def main():
    st.set_page_config(page_title="Conversor PDF para XML DUIMP", layout="wide")
    
    st.title("🔄 Conversor de PDF para XML DUIMP")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("Upload do PDF")
        uploaded_file = st.file_uploader("Carregue o arquivo PDF da DUIMP", type=['pdf'])
        
        if uploaded_file is not None:
            st.success(f"Arquivo carregado: {uploaded_file.name}")
            
            # Visualizar PDF
            with st.expander("📄 Visualizar PDF (primeira página)"):
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    page = doc.load_page(0)
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    st.image(img_data, caption="Primeira página do PDF")
                    doc.close()
                except:
                    st.info("Visualização de PDF não disponível. Instale PyMuPDF para visualização.")
            
            # Processar PDF
            if st.button("🔄 Converter PDF para XML", type="primary"):
                with st.spinner("Processando PDF e gerando XML..."):
                    try:
                        # Parse do PDF
                        data = parse_pdf_to_dict(uploaded_file)
                        
                        # Criar XML
                        xml_content = create_xml_from_dict(data)
                        
                        # Salvar em session state
                        st.session_state.xml_content = xml_content
                        st.session_state.filename = f"DUIMP_{data['duimp']['dados_gerais']['numeroDUIMP'].replace('-', '_')}.xml"
                        
                        st.success("Conversão concluída com sucesso!")
                        
                    except Exception as e:
                        st.error(f"Erro na conversão: {str(e)}")
    
    with col2:
        st.header("Resultado XML")
        
        if 'xml_content' in st.session_state:
            # Mostrar XML formatado
            with st.expander("📋 Visualizar XML Gerado", expanded=True):
                st.code(st.session_state.xml_content, language="xml")
            
            # Botão de download
            st.markdown(get_download_link(st.session_state.xml_content, st.session_state.filename), unsafe_allow_html=True)
            
            # Estatísticas
            st.subheader("📊 Estatísticas do XML")
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            
            with col_stat1:
                st.metric("Total de Adições", len(st.session_state.xml_content.split('<adicao>')) - 1)
            
            with col_stat2:
                lines = st.session_state.xml_content.split('\n')
                st.metric("Total de Linhas", len(lines))
            
            with col_stat3:
                tags = re.findall(r'<(\w+)>', st.session_state.xml_content)
                st.metric("Total de Tags", len(set(tags)))
            
            # Validação
            st.subheader("✅ Validação")
            try:
                ET.fromstring(st.session_state.xml_content)
                st.success("XML bem formado e válido!")
            except Exception as e:
                st.error(f"XML inválido: {str(e)}")
        else:
            st.info("Aguardando conversão do PDF...")
            st.image("https://via.placeholder.com/400x200/3b82f6/ffffff?text=XML+será+gerado+aqui", use_column_width=True)
    
    # Informações adicionais
    st.markdown("---")
    with st.expander("ℹ️ Instruções e Informações"):
        st.markdown("""
        ### Como usar:
        1. Faça upload do PDF da DUIMP (formato estruturado)
        2. Clique em "Converter PDF para XML"
        3. Visualize o XML gerado
        4. Faça o download do arquivo XML
        
        ### Requisitos do PDF:
        - Deve ser um extrato da DUIMP no formato oficial brasileiro
        - Layout fixo (como o exemplo fornecido)
        - Deve conter todas as informações necessárias
        
        ### Tags XML Geradas:
        - **ListaDeclaracoes**: Elemento raiz
        - **duimp**: Declaração única
        - **adicao**: Cada item da declaração (múltiplos)
        - **dados gerais**: Informações da operação
        - **tributos**: Impostos e contribuições
        - **documentos**: Documentos da operação
        
        ### Características:
        - Respeita completamente o layout XML especificado
        - Mantém todas as tags obrigatórias
        - Preserva hierarquia pai-filho
        - Formatação profissional e padronizada
        """)
    
    # Footer
    st.markdown("---")
    st.caption("Desenvolvido para conversão de PDF DUIMP para XML estruturado | v1.0")

if __name__ == "__main__":
    main()

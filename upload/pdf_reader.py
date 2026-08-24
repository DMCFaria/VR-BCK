import io
import re
from pypdf import PdfReader, PdfWriter


def extrair_cnpj_boleto(texto):
    """Extrai CNPJ do boleto, priorizando o CO-ESTIPULANTE para evitar o CNPJ do Emissor."""
    match_co = re.search(r'CO-ESTIPULANTE:.*?CNPJ:\s*([\d\.\-/]+)', texto, re.IGNORECASE)
    if match_co:
        return match_co.group(1)
    match = re.search(r'CNPJ:\s*([\d\.\-/]+)', texto)
    return match.group(1) if match else None


def extrair_fatura_boleto(texto):
    """Extrai número da fatura/Nosso Número do boleto."""
    padroes = [
        r'\d{2}/\d{2}/\d{4}\s+(\d+)\s+\d{2}/\d{2}/\d{4}',
        r'(?:Fatura|FATURA)\s*(?:N[º°ºsS]*\s*)?[:\-]?\s*(\d+)',
        r'(?:Fatura|FATURA)[ \t]*[:\-]?[ \t]*(\S+)',
        r'(?:Nosso[ ]?N[úu]mero|NOSSO[ ]?NUMERO)[ \t]*[:\-]?[ \t]*(\S+)',
        r'N[º°]\s*do\s*Documento[ \t]*[:\-]?[ \t]*(\S+)',
        r'(?:N[úu]mero|NUMERO)[ \t]+do[ \t]+Documento[ \t]*[:\-]?[ \t]*(\S+)',
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            fatura = match.group(1).strip().rstrip('.')
            if fatura.upper() not in ['EMISSOR', 'EMISSOR:', 'CNPJ', 'PRODUTO', 'VENCIMENTO', 'Nº']:
                return fatura
    return None


def extrair_cnpj_nota_debito(texto):
    """Extrai CNPJ da nota de débito (formato: XX.XXX.XXX/0001-XX ou 14 dígitos puros)."""
    match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto)
    if match:
        return match.group(1)
    match_labeled = re.search(r'CNPJ:\s*(\d{14})', texto, re.IGNORECASE)
    if match_labeled:
        return match_labeled.group(1)
    match_digits = re.search(r'(\d{14})', texto)
    return match_digits.group(1) if match_digits else None


def extrair_cnpj_nota_fiscal(texto):
    """Extrai CNPJ da nota fiscal (formato: XX.XXX.XXX/0001-XX ou 14 dígitos puros)."""
    match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto)
    if match:
        return match.group(1)
    match_labeled = re.search(r'CNPJ:\s*(\d{14})', texto, re.IGNORECASE)
    if match_labeled:
        return match_labeled.group(1)
    match_digits = re.search(r'(\d{14})', texto)
    return match_digits.group(1) if match_digits else None


def classificar_pdf_por_conteudo(pdf_file, max_paginas=2):
    """
    Classifica um PDF como 'boleto', 'nota_debito' ou 'nota_fiscal' pelo TEXTO
    das primeiras páginas — fallback para quando o nome do arquivo não segue o
    padrão. Retorna None quando não reconhece (ou o PDF é ilegível).

    A comparação é feita sobre o texto COMPACTADO (sem acentos, espaços ou
    pontuação): o extract_text do pypdf frequentemente devolve títulos com o
    espaçamento quebrado ('N O T A DE DÉBITO', 'NOTADEDEBITO'), e a comparação
    com espaços literais deixava de reconhecer documentos legítimos.
    """
    import logging
    import re
    import unicodedata

    logger = logging.getLogger(__name__)
    nome_arquivo = getattr(pdf_file, 'name', '?')

    try:
        pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        texto = ''
        for page in reader.pages[:max_paginas]:
            texto += (page.extract_text() or '') + '\n'
    except Exception as e:
        logger.warning(f"[CLASSIFICAR_PDF] Falha ao ler '{nome_arquivo}': {e}")
        return None
    finally:
        try:
            pdf_file.seek(0)
        except Exception:
            pass

    sem_acentos = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').upper()
    compacto = re.sub(r'[^A-Z0-9]', '', sem_acentos)

    if not compacto:
        # PDF sem camada de texto (escaneado como imagem) — nada a comparar.
        logger.warning(f"[CLASSIFICAR_PDF] '{nome_arquivo}' não tem texto extraível (PDF de imagem?).")
        return None

    # Ordem importa: títulos são mais específicos que marcadores genéricos
    # (um boleto pode citar "nota fiscal" nas instruções de pagamento).
    if 'NOTADEDEBITO' in compacto or 'NOTADEBITO' in compacto:
        return 'nota_debito'

    marcadores_boleto = (
        'FICHADECOMPENSACAO',
        'LINHADIGITAVEL',
        'LOCALDEPAGAMENTO',
        'NOSSONUMERO',
        'PAGAVELEMQUALQUERBANCO',
    )
    if any(m in compacto for m in marcadores_boleto):
        return 'boleto'

    marcadores_nf = (
        'NFSE',
        'NOTAFISCALDESERVICO',
        'NOTAFISCALELETRONICA',
        'DANFE',
        'NOTAFISCAL',
    )
    if any(m in compacto for m in marcadores_nf):
        return 'nota_fiscal'

    logger.warning(
        f"[CLASSIFICAR_PDF] '{nome_arquivo}' tem texto ({len(compacto)} caracteres) "
        f"mas nenhum marcador conhecido. Início do texto: {sem_acentos[:200]!r}"
    )
    return None


def ler_boleto(pdf_file):
    """
    Lê o conteúdo do PDF de Boleto e exibe no terminal.
    Args:
        pdf_file: Arquivo PDF em memória (InMemoryUploadedFile ou Similar)
    Returns:
        dict com informações extraídas por página
    """
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    
    print(f"Total de páginas: {len(reader.pages)}")
    
    paginas = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        cnpj = extrair_cnpj_boleto(text)
        fatura = extrair_fatura_boleto(text)
        
        print(f"Pag {i + 1}: CNPJ={cnpj}, Fatura={fatura}")
        
        paginas.append({
            "numero_pagina": i + 1,
            "texto": text,
            "cnpj": cnpj,
            "fatura": fatura,
        })
    
    return {
        "tipo": "BOLETO",
        "total_paginas": len(reader.pages),
        "paginas": paginas
    }


def ler_nota_debito(pdf_file):
    """
    Lê o conteúdo do PDF de Nota de Débito e exibe no terminal.
    Args:
        pdf_file: Arquivo PDF em memória
    Returns:
        dict com informações extraídas por página
    """
    
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    
    print(f"Total de páginas: {len(reader.pages)}")
    
    paginas = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        cnpj = extrair_cnpj_nota_debito(text)
         
        paginas.append({
            "numero_pagina": i + 1,
            "texto": text,
            "cnpj": cnpj
        })
    
    return {
        "tipo": "NOTA_DEBITO",
        "total_paginas": len(reader.pages),
        "paginas": paginas
    }


def ler_nota_fiscal(pdf_file):
    """
    Lê o conteúdo do PDF de Nota Fiscal e exibe no terminal.
    Args:
        pdf_file: Arquivo PDF em memória
    Returns:
        dict com informações extraídas por página
    """
    
    
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    
    print(f"Total de páginas: {len(reader.pages)}")
    
    paginas = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        cnpj = extrair_cnpj_nota_fiscal(text)
        
        print(f"Pag {i + 1}: CNPJ={cnpj}")
        
        paginas.append({
            "numero_pagina": i + 1,
            "texto": text,
            "cnpj": cnpj
        })
    
    return {
        "tipo": "NOTA_FISCAL",
        "total_paginas": len(reader.pages),
        "paginas": paginas
    }


def separar_pdf_em_paginas(pdf_file, tipo, pasta_temp):
    """
    Separa o PDF em páginas individuais e salva em uma pasta temporária.
    Args:
        pdf_file: Arquivo PDF em memória
        tipo: Tipo do documento (boleto, nota_debito, nota_fiscal)
        pasta_temp: Caminho da pasta temporária para salvar os arquivos
    Returns:
        dict com informações das páginas separadas
    """
    import os
    from pypdf import PdfReader, PdfWriter
    
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    
    arquivos_separados = []
    pasta_tipo = os.path.join(pasta_temp, tipo)
    os.makedirs(pasta_tipo, exist_ok=True)
    
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        
        nome_arquivo = f"pagina_{i + 1:03d}.pdf"
        caminho_arquivo = os.path.join(pasta_tipo, nome_arquivo)
        
        with open(caminho_arquivo, 'wb') as f:
            writer.write(f)
        
        arquivos_separados.append({
            "numero_pagina": i + 1,
            "nome_arquivo": nome_arquivo,
            "caminho": caminho_arquivo,
            "tipo": tipo
        })
        
        print(f"Criada página {i + 1}: {caminho_arquivo}")
    
    return arquivos_separados
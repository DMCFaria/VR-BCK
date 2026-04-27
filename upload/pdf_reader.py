import io
import re
from pypdf import PdfReader, PdfWriter


def extrair_cnpj_boleto(texto):
    """Extrai CNPJ do boleto (formato: CNPJ: XX.XXX.XXX-XXXX-XX)"""
    match = re.search(r'CNPJ:\s*([\d\.\-/]+)', texto)
    return match.group(1) if match else None


def extrair_cnpj_nota_debito(texto):
    """Extrai CNPJ da nota de débito (formato: XX.XXX.XXX/0001-XX)"""
    match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto)
    return match.group(1) if match else None


def extrair_cnpj_nota_fiscal(texto):
    """Extrai CNPJ da nota fiscal (formato: XX.XXX.XXX/0001-XX)"""
    match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto)
    return match.group(1) if match else None


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
        
        print(f"Pag {i + 1}: CNPJ={cnpj}")
        
        paginas.append({
            "numero_pagina": i + 1,
            "texto": text,
            "cnpj": cnpj
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
import decimal
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from collections import defaultdict

# Importa o Parser
from .RB.parsers import parse_rb_layout
from .serializers import ProcessamentoFinalSerializer, FileUploadSerializer
from .models import FileUpload


# --- FUNÇÕES AUXILIARES ---

def _convert_decimals_to_json_safe(data):
    """
    Recursivamente converte objetos Decimal para strings para serialização JSON.
    Funciona para dicionários, listas e valores isolados.
    """
    if isinstance(data, dict):
        return {key: _convert_decimals_to_json_safe(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_convert_decimals_to_json_safe(element) for element in data]
    elif isinstance(data, decimal.Decimal):
        return str(data) 
    return data

def _get_beneficiary_summary(parsed_data):
    """
    Calcula o total de benefícios por funcionário a partir da lista detalhada (planilha).
    """
    movimentacoes_detalhada = parsed_data.get('movimentacoes_detalhada', [])
    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}
    departamentos_por_cpf = {}

    for row in movimentacoes_detalhada:
        cpf = row.get('cpf_func')
        nome = row.get('nome_func')
        valor = row.get('valor_recarga_bene')
        condominio = row.get('departamento')

        if cpf and valor is not None:
            if not isinstance(valor, decimal.Decimal):
                try: 
                    valor = decimal.Decimal(str(valor))
                except: 
                    valor = decimal.Decimal('0.00')
            total_por_cpf[cpf] += valor
            nomes_por_cpf[cpf] = nome
            departamentos_por_cpf[cpf] = condominio

    summary_list = []
    for cpf, total in total_por_cpf.items():
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total), # Já converte para string aqui por segurança
            "condominio": departamentos_por_cpf.get(cpf)
        })
    return summary_list



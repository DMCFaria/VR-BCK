import decimal
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from collections import defaultdict

from .RB.parsers import parse_rb_layout
from .serializers import ProcessamentoFinalSerializer, FileUploadSerializer
from .models import FileUpload


def _convert_decimals_to_json_safe(data):
    if isinstance(data, dict):
        return {key: _convert_decimals_to_json_safe(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_convert_decimals_to_json_safe(element) for element in data]
    elif isinstance(data, decimal.Decimal):
        return str(data) 
    return data

def _get_beneficiary_summary(parsed_data):
    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}
    condominios_por_cpf = {}

    condominios = parsed_data.get('condominios', [])
    for condo in condominios:
        for func in condo.get('funcionarios', []):
            cpf = func.get('cpf')
            nome = func.get('nome')
            valor_bene = func.get('valor_bene', 0)

            if cpf:
                if not isinstance(valor_bene, decimal.Decimal):
                    try:
                        valor_bene = decimal.Decimal(str(valor_bene))
                    except:
                        valor_bene = decimal.Decimal('0.00')
                total_por_cpf[cpf] += valor_bene
                nomes_por_cpf[cpf] = nome
                condominios_por_cpf[cpf] = condo.get('nome', '')

    summary_list = []
    for cpf, total in total_por_cpf.items():
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total),
            "condominio": condominios_por_cpf.get(cpf)
        })
    return summary_list



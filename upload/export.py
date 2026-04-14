import io
import re
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from django.db.models import Sum
from django.utils import timezone
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from entidades.models import Condominio, Funcionario, Administradora, VinculoCondominio
from beneficios.models import MovimentacaoBeneficio, Produto


def gerar_txt_compra(administradora_cnpj, data_competencia=None):
    """
    Gera o arquivo txt_compra para envio à VR Benefícios.
    Formato posicional baseado no layout VR.
    """
    linhas = []
    seq = 1
    
    admin = Administradora.objects.filter(cnpj=administradora_cnpj).first()
    if not admin:
        return None, "Administradora não encontrada"
    
    query = VinculoCondominio.objects.filter(administradora=admin)
    if data_competencia:
        query = query.filter(
            condominio__movimentacaobeneficio__data_competencia=data_competencia
        ).distinct()
    
    vinculos = query.select_related('condominio').prefetch_related('gerentes')
    
    linhas.append(f"0001{administradora_cnpj.zfill(16)}{admin.nome[:56]:<56}{' ' * (62 - len(admin.nome))}000000001")
    seq += 1
    
    for vinculo in vinculos:
        condominio = vinculo.condominio
        
        linha1 = (f"103{administradora_cnpj.zfill(16)}"
                 f"{condominio.cnpj.zfill(16)}"
                 f"{condominio.nome[:40]:<40}"
                 f"{'AVENIDA':<10}"
                 f"{(condominio.endereco or 'PRESIDENTE ANTONIO CARLOS')[:35]:<35}"
                 f"{(condominio.numero or '0006')[:15]:<15}"
                 f"{(condominio.bairro or 'CENTRO')[:30]:<30}"
                 f"{(condominio.cidade or 'RIO DE JANEIRO')[:30]:<30}"
                 f"{(condominio.estado or 'RJ')[:2]:<2}"
                 f"{(condominio.cep or '20020010')[:10]:<10}"
                 f"{'JULIANA BRAGA':<20}"
                 f"{str(seq).zfill(9)}")
        linhas.append(linha1)
        seq += 1
        
        linha2 = (f"113{administradora_cnpj.zfill(16)}"
                 f"{condominio.cnpj.zfill(16)}"
                 f"{admin.cnpj[:14]:<14}"
                 f"{condominio.nome[:30]:<30}"
                 f"suportebeneficios@grupofedcorp.com.br{'':<55}"
                 f"{str(seq).zfill(9)}")
        linhas.append(linha2)
        seq += 1
        
        gerentes = vinculo.gerentes.all()
        emails = [g.email for g in gerentes if g.email] if gerentes else ['suportevr@grupofedcorp.com.br']
        
        for email in emails:
            linha3 = (f"123{administradora_cnpj.zfill(16)}"
                     f"{condominio.cnpj.zfill(16)}"
                     f"{'suportevr@grupofedcorp.com.br':<50}"
                     f"{email:<50}"
                     f"{'suportevr@grupofedcorp.com.br':<50}"
                     f"{' ' * 35}"
                     f"{str(seq).zfill(9)}")
            linhas.append(linha3)
            seq += 1
    
    return '\n'.join(linhas), None


def gerar_faturamento(data_inicio=None, data_fim=None, administradora_cnpj=None, condominio_cnpj=None):
    """
    Gera dados para planilha de faturamento.
    """
    query = MovimentacaoBeneficio.objects.select_related(
        'empresa_cnpj', 'funcionario_cpf', 'produto_codigo'
    )
    
    if data_inicio:
        query = query.filter(data_competencia__gte=data_inicio)
    if data_fim:
        query = query.filter(data_competencia__lte=data_fim)
    if administradora_cnpj:
        query = query.filter(
            empresa_cnpj__vinculocondominio__administradora__cnpj=administradora_cnpj
        )
    if condominio_cnpj:
        query = query.filter(empresa_cnpj__cnpj=condominio_cnpj)
    
    movimentacoes = query.order_by('empresa_cnpj', 'funcionario_cpf', 'data_competencia')
    
    dados = []
    for mov in movimentacoes:
        func = mov.funcionario_cpf
        cond = mov.empresa_cnpj
        prod = mov.produto_codigo
        
        valor_unitario = mov.valor_beneficio / mov.quantidade_dias if mov.quantidade_dias > 0 else mov.valor_beneficio
        
        datos_periodo = mov.data_competencia.strftime('%d/%m/%Y')
        data_ini = mov.data_competencia.replace(day=1)
        data_fim = data_ini + timedelta(days=30)
        periodos = f"{data_ini.strftime('%d/%m/%Y')} - {data_fim.strftime('%d/%m/%Y')}"
        
        dados.append({
            'CPF': func.cpf,
            'NOME_FUNC': func.nome,
            'PRODUTO': prod.codigo_produto,
            'BENEFICIO': prod.nome,
            'VALOR_UNITARIO': valor_unitario,
            'QUANTIDADE': mov.quantidade_dias,
            'VALOR_RECARGA_BENE': mov.valor_beneficio,
            'REPASSE_VT': None,
            'DEPARTAMENTO': cond.nome,
            'CNPJ': cond.cnpj,
            'ENDERECO': cond.endereco or '',
            'BAIRRO': cond.bairro or '',
            'CIDADE': cond.cidade or '',
            'UF': cond.estado or '',
            'CEP': cond.cep or '',
            'TAXA': None,
            'vencimento': datos_periodo,
            'periodos': periodos,
            'periodo2': ''
        })
    
    return dados


class ExportTxtCompraView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, *args, **kwargs):
        administradora_cnpj = request.query_params.get('administradora_cnpj')
        data_competencia = request.query_params.get('data_competencia')
        
        if not administradora_cnpj:
            return Response(
                {'detail': 'Parâmetro administradora_cnpj é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if data_competencia:
            try:
                data_competencia = datetime.strptime(data_competencia, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'detail': 'Data inválida. Use formato YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        conteudo, erro = gerar_txt_compra(administradora_cnpj, data_competencia)
        
        if erro:
            return Response({'detail': erro}, status=status.HTTP_404_NOT_FOUND)
        
        response = Response(
            {'filename': f'txt_compra_{administradora_cnpj}.txt', 'conteudo': conteudo},
            status=status.HTTP_200_OK
        )
        response['Content-Disposition'] = f'attachment; filename="txt_compra_{administradora_cnpj}.txt"'
        return response


class ExportFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, *args, **kwargs):
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        administradora_cnpj = request.query_params.get('administradora_cnpj')
        condominio_cnpj = request.query_params.get('condominio_cnpj')
        formato = request.query_params.get('formato', 'json')
        
        if data_inicio:
            try:
                data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'detail': 'Data início inválida. Use formato YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if data_fim:
            try:
                data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'detail': 'Data fim inválida. Use formato YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        dados = gerar_faturamento(
            data_inicio=data_inicio,
            data_fim=data_fim,
            administradora_cnpj=administradora_cnpj,
            condominio_cnpj=condominio_cnpj
        )
        
        if formato == 'xlsx':
            df = pd.DataFrame(dados)
            
            columns_order = [
                'CPF', 'NOME_FUNC', 'PRODUTO', 'BENEFICIO', 'VALOR_UNITARIO',
                'QUANTIDADE', 'VALOR_RECARGA_BENE', 'REPASSE_VT', 'DEPARTAMENTO',
                'CNPJ', 'ENDERECO', 'BAIRRO', 'CIDADE', 'UF', 'CEP',
                'TAXA', 'vencimento', 'periodos', 'periodo2'
            ]
            df = df[[c for c in columns_order if c in df.columns]]
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Faturamento')
            
            buffer.seek(0)
            response = Response(
                buffer.getvalue(),
                status=status.HTTP_200_OK,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="PLAN_FATURAMENTO_{date.today().strftime("%Y%m%d")}.xlsx"'
            return response
        
        return Response({
            'count': len(dados),
            'data': dados
        }, status=status.HTTP_200_OK)
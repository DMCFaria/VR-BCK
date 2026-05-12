import io
import re
from datetime import date, timedelta, datetime
from decimal import Decimal

import pandas as pd
from django.db.models import Sum
from django.http import HttpResponse
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
    """
    linhas = []
    seq = 1

    admin = Administradora.objects.filter(cnpj=administradora_cnpj).first()
    if not admin:
        return None, "Administradora não encontrada"

    # Header (TipoRec 00)
    linha_header = (
        f"00"  # TipoRec (2)
        f"011"  # Versao (3)
        f"{administradora_cnpj.zfill(14)}"  # CNPJ/Código Cliente (14)
        f"{admin.razao_social[:40]:<40}"  # Razão Social Cliente (40)
        f"{' ' * 282}"  # FILLER (282)
        f"{str(seq).zfill(9)}"  # Número da linha (9)
    )
    linhas.append(linha_header)
    seq += 1

    # Buscar condomínios vinculados
    query = VinculoCondominio.objects.filter(administradora=admin)
    if data_competencia:
        query = query.filter(
            condominio__movimentacaobeneficio__data_competencia=data_competencia
        ).distinct()

    vinculos = query.select_related('condominio').prefetch_related('gerentes')

    for vinculo in vinculos:
        condominio = vinculo.condominio

        # Local Entrega (TipoRec 10)
        numero_condo = str(condominio.numero or '').strip()
        if not numero_condo:
            numero_condo = ''
        linha_local = (
            f"10"
            f"{administradora_cnpj.zfill(14)}"
            f"{condominio.cnpj[:30]:<30}"
            f"{condominio.nome[:80]:<80}"
            f"{'AV'[:20]:<20}"
            f"{(condominio.endereco or '')[:40]:<40}"
            f"{numero_condo[:6]:<6}"
            f"{(condominio.complemento or '')[:20]:<20}"
            f"{(condominio.bairro or '')[:30]:<30}"
            f"{(condominio.cidade or '')[:30]:<30}"
            f"{(condominio.estado or '')[:2]:<2}"
            f"{(condominio.cep or '').replace('-', '')[:8]:<8}"
            f"{' ' * 30}"
            f"{' ' * 29}"
            f"{str(seq).zfill(9)}"
        )
        linhas.append(linha_local)
        seq += 1

        # Associação CNPJ ao Local Entrega (TipoRec 11)
        linha_assoc = (
            f"11"
            f"{administradora_cnpj.zfill(14)}"
            f"{condominio.cnpj[:30]:<30}"
            f"{administradora_cnpj.zfill(14)}"
            f"{admin.razao_social[:24]:<24}"
            f"{'suportevr@grupofedcorp.com.br'[:70]:<70}"
            f"{' ' * 187}"
            f"{str(seq).zfill(9)}"
        )
        linhas.append(linha_assoc)
        seq += 1

        # Responsáveis pelo Local de Entrega (TipoRec 12)
        gerentes = vinculo.gerentes.all()
        emails_gerentes = [g.email for g in gerentes if g.email][:3]
        if not emails_gerentes:
            emails_gerentes = ['suportevr@grupofedcorp.com.br']

        email1 = emails_gerentes[0][:60] if len(emails_gerentes) > 0 else ' ' * 60
        email2 = emails_gerentes[1][:60] if len(emails_gerentes) > 1 else email1
        email3 = emails_gerentes[2][:60] if len(emails_gerentes) > 2 else email1

        linha_resp = (
            f"12"
            f"{administradora_cnpj.zfill(14)}"
            f"{condominio.cnpj[:30]:<30}"
            f"{email1:<60}"
            f"{' ' * 43}"
            f"{email2:<60}"
            f"{' ' * 43}"
            f"{email3:<60}"
            f"{' ' * 29}"
            f"{str(seq).zfill(9)}"
        )
        linhas.append(linha_resp)
        seq += 1

    # Buscar movimentações
    mov_query = MovimentacaoBeneficio.objects.filter(
        empresa_cnpj__vinculocondominio__administradora=admin
    ).select_related('produto_codigo', 'funcionario_cpf', 'empresa_cnpj')

    if data_competencia:
        mov_query = mov_query.filter(data_competencia=data_competencia)

    # ⭐⭐⭐ REMOVER DUPLICAÇÃO: Apenas UM bloco de registros 30, 50 e 60 ⭐⭐⭐
    
    # Beneficiário (TipoRec 30)
    funcionarios_vistos = set()
    for mov in mov_query:
        func = mov.funcionario_cpf
        cond = mov.empresa_cnpj

        if func.cpf in funcionarios_vistos:
            continue
        funcionarios_vistos.add(func.cpf)

        data_nasc = ''
        if func.data_nascimento:
            data_nasc = func.data_nascimento.strftime('%d%m%Y')
        else:
            data_nasc = '00000000'

        linha_benef = (
            f"30"
            f"{administradora_cnpj.zfill(14)}"
            f"{func.cpf[:11]:<11}"
            f"{cond.cnpj[:30]:<30}"
            f"{' ' * 12}"
            f"CONDOMINIO"
            f"{func.nome[:40]:<40}"
            f"{' '[:24]:<24}"
            f"{data_nasc}"
            f"{' ' * 187}"
            f"{str(seq).zfill(9)}"
        )
        linhas.append(linha_benef)
        seq += 1

    # ⭐⭐⭐ APENAS UM BLOCO PARA REGISTROS 50 e 60 ⭐⭐⭐
    from itertools import groupby
    from operator import attrgetter

    movimentacoes_ordenadas = mov_query.order_by('produto_codigo__codigo_produto')

    for prod_codigo, movimentacoes_grupo in groupby(movimentacoes_ordenadas, key=attrgetter('produto_codigo.codigo_produto')):
        prod_cod = prod_codigo[:3].upper()
        mov_list = list(movimentacoes_grupo)

        # Registro 50 - Produto Voucher
        data_agend = data_competencia if data_competencia else date.today()
        linha_prod = (
            f"50"
            f"{administradora_cnpj.zfill(14)}"
            f"{prod_cod:<3}"
            f"{data_agend.strftime('%d%m%Y')}"
            f"{' ' * 314}"
            f"{str(seq).zfill(9)}"
        )
        linhas.append(linha_prod)
        seq += 1

        # Registros 60 - Benefícios Voucher
        for mov in mov_list:
            func = mov.funcionario_cpf
            valor = float(mov.valor_beneficio)
            valor_str = f"{valor:.2f}".replace('.', '').zfill(11)

            linha_beneficio = (
                f"60"
                f"{administradora_cnpj.zfill(14)}"
                f"{prod_cod:<3}"
                f"{func.cpf.zfill(11)}"
                f"{' ' * 40}"
                f"{valor_str}"
                f"{' ' * 260}"
                f"{str(seq).zfill(9)}"
            )
            linhas.append(linha_beneficio)
            seq += 1

    # Trailler (TipoRec 99)
    linha_trailler = (
        f"99"
        f"{administradora_cnpj.zfill(14)}"
        f"{' ' * 325}"
        f"{str(seq).zfill(9)}"
    )
    linhas.append(linha_trailler)

    return '\n'.join(linhas), None


def gerar_faturamento(importacao_id=None, data_inicio=None, data_fim=None, administradora_cnpj=None, condominio_cnpj=None):
    """
    Gera dados para planilha de faturamento.
    Se importacao_id for passado, filtra apenas pelas movimentações dessa importação.
    """
    query = MovimentacaoBeneficio.objects.select_related(
        'empresa_cnpj', 'funcionario_cpf', 'produto_codigo'
    )

    if importacao_id:
        query = query.filter(importacao_id=importacao_id)
    else:
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
        
        produto_display = prod.get_tipo_display_or_codigo()

        dados.append({
            'CPF': func.cpf,
            'NOME_FUNC': func.nome,
            'PRODUTO': produto_display,
            'BENEFICIO': None,
            'CEP_FUNC': func.cep or '',
            'ENDERECO_FUNC': func.endereco_rua or '',
            'NUMERO_FUNC': func.endereco_numero or '',
            'COMPLEMENTO_FUNC': func.endereco_complemento or '',
            'BAIRRO_FUNC': func.endereco_bairro or '',
            'VALOR_UNITARIO': float(valor_unitario),
            'QUANTIDADE': mov.quantidade_dias,
            'VALOR_RECARGA_BENE': float(mov.valor_beneficio),
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
            'periodos': periodos.split('-')[0],
            'periodo2': periodos.split('-')[1]
        })
    
    return dados


class ExportTxtCompraView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, *args, **kwargs):
        importacao_id = request.query_params.get('importacao_id')
        data_competencia_str = request.query_params.get('data_competencia')

        if not importacao_id:
            return Response(
                {'detail': 'Parâmetro importacao_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from beneficios.models import Importacao

        try:
            importacao = Importacao.objects.get(id=importacao_id)
        except Importacao.DoesNotExist:
            return Response(
                {'detail': 'Importação não encontrada.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get administradora_cnpj from importacao
        if not importacao.administradora:
            return Response(
                {'detail': 'Importação não possui administradora vinculada.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        administradora_cnpj = importacao.administradora.cnpj

        # Get data_competencia from query params or from importacao's movements
        data_competencia = None
        if data_competencia_str:
            try:
                data_competencia = datetime.strptime(data_competencia_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'detail': 'Formato de data_competencia inválido. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Try to get data_competencia from the first movement of the importacao
            first_mov = importacao.movimentacoes.first()
            if first_mov:
                data_competencia = first_mov.data_competencia
            else:
                data_competencia = date.today()

        # Generate TXT
        txt_content, error = gerar_txt_compra(administradora_cnpj, data_competencia)
        
        if error:
            return Response(
                {'detail': error},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Return TXT file
        response = HttpResponse(txt_content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="PEDIDO_VR_{date.today().strftime("%Y%m%d")}.txt"'
        return response


class ExportFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, *args, **kwargs):
        importacao_id = request.query_params.get('importacao_id')

        if not importacao_id:
            return Response(
                {'detail': 'Parâmetro importacao_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from beneficios.models import Importacao

        try:
            importacao = Importacao.objects.get(id=importacao_id)
        except Importacao.DoesNotExist:
            return Response(
                {'detail': 'Importação não encontrada.'},
                status=status.HTTP_404_NOT_FOUND
            )

        dados = gerar_faturamento(importacao_id=importacao_id)

        if not dados:
            return Response(
                {'detail': 'Nenhuma movimentação encontrada para esta importação.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            df = pd.DataFrame(dados)
            
            # Verificar se o DataFrame não está vazio
            if df.empty:
                return Response(
                    {'detail': 'Nenhum dado para exportar.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Definir colunas
            columns_order = [
                'CPF', 'NOME_FUNC', 'PRODUTO', 'BENEFICIO', 'VALOR_UNITARIO',
                'QUANTIDADE', 'VALOR_RECARGA_BENE', 'REPASSE_VT', 'DEPARTAMENTO',
                'CNPJ', 'ENDERECO', 'BAIRRO', 'CIDADE', 'UF', 'CEP',
                'TAXA', 'vencimento', 'periodos', 'periodo2'
            ]
            
            # Filtrar apenas colunas que existem
            existing_columns = [c for c in columns_order if c in df.columns]
            df = df[existing_columns]

            output = io.BytesIO()
            
            # Tentar com xlsxwriter primeiro (mais estável)
            try:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Faturamento')
            except Exception as e:
                # Fallback para openpyxl
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Faturamento')
            
            output.seek(0)
            
            # Verificar se o buffer não está vazio
            if output.getbuffer().nbytes == 0:
                return Response(
                    {'detail': 'Erro ao gerar arquivo Excel: buffer vazio.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
            # Usar filename com .xlsx e aspas para evitar problemas
            filename = f"PLAN_FATURAMENTO_{importacao_id}_{date.today().strftime('%Y%m%d')}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            return response
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao gerar Excel: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Erro ao gerar planilha: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
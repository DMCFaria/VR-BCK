import logging
from django.utils import timezone

from rest_framework import viewsets, views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Prefetch

from core.fedhub.services.fedhub_service import FedhubService
from .models import Produto, MovimentacaoBeneficio, Importacao
from .serializers import (
    ImportacaoComMovimentacoesSerializer,
    ProdutoSerializer,
    MovimentacaoBeneficioSerializer,
    ImportacaoDetailSerializer,
)

logger = logging.getLogger(__name__)

class ProdutoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, criar, atualizar e deletar Produtos.
    Rotas: /api/benefits/produtos/
    """
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'codigo_produto'


class MovimentacaoBeneficioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, criar, atualizar e deletar Movimentações de Benefício.
    Rotas: /api/benefits/movimentacoes/
    """
    queryset = MovimentacaoBeneficio.objects.order_by('-id').all()
    serializer_class = MovimentacaoBeneficioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        funcionario_cpf = self.request.query_params.get('cpf', None)
        if funcionario_cpf is not None:
            queryset = queryset.filter(funcionario_cpf__cpf=funcionario_cpf)
        return queryset


class AlterarStatusImportacaoView(views.APIView):
    """
    View para alterar o status de uma importação.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, pk):
        try:
            importacao = Importacao.objects.get(id=pk)
        except Importacao.DoesNotExist:
            return Response(
                {"detail": "Importação não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        novo_status = request.data.get('status')
        
        # Mapeamento de status do frontend para o backend
        status_mapping = {
            'aprovado': 'AGUARDANDO_FATURAMENTO',
            'em_faturamento': 'EM_FATURAMENTO',
            'faturado': 'COMPLETED',
            'cancelado': 'CANCELADO',
        }
        
        status_backend = status_mapping.get(novo_status)
        
        if not status_backend:
            # Tenta usar o status diretamente se já estiver no formato do backend
            valid_statuses = [choice[0] for choice in Importacao.STATUS_CHOICES]
            if novo_status in valid_statuses:
                status_backend = novo_status
            else:
                return Response(
                    {"detail": f"Status inválido: {novo_status}. Opções: aprovado, em_faturamento, faturado, cancelado"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Se for cancelado, verifica se tem motivo
        motivo = request.data.get('motivo', '')
        if status_backend == 'CANCELADO' and not motivo:
            return Response(
                {"detail": "Informe o motivo do cancelamento."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Guarda o status anterior para verificar se mudou para COMPLETED
        status_anterior = importacao.status
        
        importacao.status = status_backend
        importacao.save()
        
        # Se houver motivo, registra nos erros
        if motivo:
            erros = importacao.erros or []
            erros.append({
                "tipo": "CANCELAMENTO",
                "motivo": motivo,
                "data": str(timezone.now().date()),
                "usuario": request.user.email if request.user else None
            })
            importacao.erros = erros
            importacao.save()
        
        logger.info(f"Importação {pk} alterada para status: {status_backend}")
        
        fedhub_service = FedhubService()
        
        # SÓ ENVIA E-MAIL SE O STATUS FOR COMPLETED (FATURADO)
        if status_backend == 'COMPLETED' and status_anterior != 'COMPLETED':
            try:
                # Buscar a administradora e seus contatos
                administradora = importacao.administradora
                
                # Buscar os dados da importação para montar o e-mail
                movimentacoes = MovimentacaoBeneficio.objects.filter(importacao=importacao)
                
                # Agrupar por empresa/condomínio para obter totais
                empresas_unicas = movimentacoes.values('empresa_cnpj').distinct().count()
                funcionarios_unicos = movimentacoes.values('funcionario_cpf').distinct().count()
                total_registros = movimentacoes.count()
                valor_total = float(importacao.valor_total) if importacao.valor_total else 0
                
                # Extrair competência da importação (assumindo que existe campo competencia)
                competencia = getattr(importacao, 'competencia', '')
                competencia_mes = competencia.month if competencia else ''
                competencia_ano = competencia.year if competencia else ''
                competencia_str = f"{competencia_mes}/{competencia_ano}" if competencia_mes and competencia_ano else "—"
                
                # Dados para o e-mail do cliente
                # IMPORTANTE: Você precisa ter o e-mail do cliente final em algum lugar
                # Pode ser no modelo Importacao ou no perfil do cliente
                email_cliente = request.data.get('email_cliente')  # Pode vir no payload
                nome_cliente = request.data.get('nome_cliente', administradora.nome if administradora else 'Cliente')
                
                # Se não veio no payload, tenta buscar do relacionamento
                if not email_cliente and administradora:
                    # Supondo que administradora tenha um método para pegar e-mail do cliente
                    # Ou você pode ter um campo email_cliente na Importacao
                    email_cliente = getattr(importacao, 'email_cliente', None)
                
                dados_faturamento = {
                    'cliente_nome': nome_cliente,
                    'cliente_email': email_cliente,
                    'arquivo_nome': getattr(importacao.file_upload, 'file', 'faturamento.xlsx').name if hasattr(importacao, 'file_upload') else 'faturamento.xlsx',
                    'data_faturamento': timezone.now().strftime('%d/%m/%Y %H:%M'),
                    'competencia': competencia_str,
                    'total_registros': total_registros,
                    'total_funcionarios': funcionarios_unicos,
                    'total_condominios': empresas_unicas,
                    'valor_total': valor_total,
                    'faturamento_id': importacao.id,
                    'vencimento': request.data.get('vencimento', getattr(importacao, 'vencimento', '')),
                    'periodo_inicio': request.data.get('periodo_inicio', ''),
                    'periodo_fim': request.data.get('periodo_fim', ''),
                    'numero_nota_fiscal': request.data.get('numero_nota_fiscal', ''),
                    'link_boleto': request.data.get('link_boleto', ''),
                    'link_nota_fiscal': request.data.get('link_nota_fiscal', ''),
                }
                
                # Envia e-mail para o cliente final
                if email_cliente:
                    email_enviado_cliente = fedhub_service.enviar_email_cliente_faturamento(
                        email=email_cliente,
                        user=request.user,
                        dados_processamento=dados_faturamento
                    )
                    logger.info(f"Email de faturamento enviado para cliente {email_cliente}: {email_enviado_cliente}")
                else:
                    logger.warning(f"Email do cliente não informado para importação {pk}")
                
                # Opcional: Envia também e-mail de confirmação para a administradora
                email_enviado_admin = fedhub_service.enviar_email_upload(
                    email=request.user.email,
                    user=request.user,
                    dados_processamento={
                        "arquivo_nome": getattr(importacao.file_upload, 'file', 'faturamento.xlsx').name if hasattr(importacao, 'file_upload') else 'faturamento.xlsx',
                        "data_envio": timezone.now().strftime('%d/%m/%Y %H:%M'),
                        "competencia": competencia_str,
                        "total_registros": total_registros,
                        "total_funcionarios": funcionarios_unicos,
                        "total_condominios": empresas_unicas,
                        "valor_total": valor_total,
                        "tipo_processamento": "Faturamento Concluído",
                        "faturamento_id": importacao.id,
                        "vencimento": request.data.get('vencimento', ''),
                        "periodo_inicio": request.data.get('periodo_inicio', ''),
                        "periodo_fim": request.data.get('periodo_fim', '')
                    }
                )
                logger.info(f"Email de confirmação enviado para administradora {request.user.email}: {email_enviado_admin}")
                
            except Exception as e:
                logger.error(f"Erro ao enviar e-mails de faturamento para importação {pk}: {str(e)}")
                # Não falha a operação principal se o e-mail der erro
        
        return Response({
            "id": importacao.id,
            "status": status_backend,
            "status_display": dict(Importacao.STATUS_CHOICES).get(status_backend, status_backend),
            "message": f"Status alterado para {status_backend} com sucesso."
        }, status=status.HTTP_200_OK)


class UltimaImportacaoMovimentacoesView(views.APIView):
    """
    Rota para buscar as movimentações da última importação da administradora do usuário.
    Retorna os dados no formato esperado pelo endpoint /api/confirmed/ para reutilização.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        administradora = getattr(user, 'administradora', None)
        
        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ultima_importacao = Importacao.objects.filter(
            administradora=administradora,
            status='COMPLETED'
        ).order_by('-data_importacao').first()

        if not ultima_importacao:
            return Response(
                {"detail": "Nenhuma importação encontrada para esta administradora."},
                status=status.HTTP_404_NOT_FOUND
            )

        movimentacoes = MovimentacaoBeneficio.objects.filter(
            importacao=ultima_importacao
        ).select_related(
            'empresa_cnpj',
            'funcionario_cpf',
            'produto_codigo'
        )

        condos_dict = {}
        for mov in movimentacoes:
            cnpj = mov.empresa_cnpj.cnpj
            if cnpj not in condos_dict:
                condos_dict[cnpj] = {
                    'nome': mov.empresa_cnpj.nome,
                    'cnpj': cnpj,
                    'valor_condo': 0,
                    'rua': mov.empresa_cnpj.endereco or '',
                    'numero': mov.empresa_cnpj.numero or '',
                    'complemento': mov.empresa_cnpj.complemento or '',
                    'bairro': mov.empresa_cnpj.bairro or '',
                    'cidade': mov.empresa_cnpj.cidade or '',
                    'estado': mov.empresa_cnpj.estado or '',
                    'cep': mov.empresa_cnpj.cep or '',
                    'funcionarios': {}
                }

            cpf = mov.funcionario_cpf.cpf
            if cpf not in condos_dict[cnpj]['funcionarios']:
                condos_dict[cnpj]['funcionarios'][cpf] = {
                    'nome': mov.funcionario_cpf.nome,
                    'cpf': cpf,
                    'matricula': mov.funcionario_cpf.matricula or '',
                    'departamento': mov.funcionario_cpf.departamento or '',
                    'funcao': mov.funcionario_cpf.funcao or '',
                    'data_nascimento': str(mov.funcionario_cpf.data_nascimento) if mov.funcionario_cpf.data_nascimento else '',
                    'valor_bene': 0,
                    'movimentacoes': []
                }

            valor = round(float(mov.valor_beneficio), 2)
            condos_dict[cnpj]['funcionarios'][cpf]['valor_bene'] = round(condos_dict[cnpj]['funcionarios'][cpf]['valor_bene'] + valor, 2)
            condos_dict[cnpj]['valor_condo'] = round(condos_dict[cnpj]['valor_condo'] + valor, 2)

            condos_dict[cnpj]['funcionarios'][cpf]['movimentacoes'].append({
                'produto': mov.produto_codigo.nome,
                'codigo_produto': mov.produto_codigo.codigo_produto,
                'valor': valor
            })

        condominios = []
        for cnpj, condo_data in condos_dict.items():
            condo_data['funcionarios'] = list(condo_data['funcionarios'].values())
            condominios.append(condo_data)

        return Response({
            'condominios': condominios,
            'importacao_id': ultima_importacao.id,
            'data_importacao': ultima_importacao.data_importacao.isoformat()
        })


class ImportacaoListView(views.APIView):
    """
    Rota para listar o histórico de importações da administradora do usuário.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        administradora = getattr(user, 'administradora', None)

        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        movimentacoes_qs = MovimentacaoBeneficio.objects.select_related(
            'empresa_cnpj',
            'funcionario_cpf',
            'produto_codigo'
        )

        importacoes = Importacao.objects.filter(
            administradora=administradora
        ).prefetch_related(
            Prefetch('movimentacoes', queryset=movimentacoes_qs)
        ).order_by('-data_importacao')

        serializer = ImportacaoComMovimentacoesSerializer(importacoes, many=True)

        return Response(serializer.data)


class ImportacaoDetailView(views.APIView):
    """
    Rota para ver os detalhes de uma importação específica,
    incluindo as movimentações associadas.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk):
        user = request.user
        administradora = getattr(user, 'administradora', None)

        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            importacao = Importacao.objects.filter(
                administradora=administradora,
                id=pk
            ).first()

            if not importacao:
                return Response(
                    {"detail": "Importação não encontrada."},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Importacao.DoesNotExist:
            return Response(
                {"detail": "Importação não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        importacao_serializer = ImportacaoDetailSerializer(importacao)

        movimentacoes = MovimentacaoBeneficio.objects.filter(
            importacao=importacao
        ).select_related(
            'empresa_cnpj',
            'funcionario_cpf',
            'produto_codigo'
        )

        movimentacoes_data = []
        for mov in movimentacoes:
            movimentacoes_data.append({
                'id': mov.id,
                'empresa_cnpj': mov.empresa_cnpj.cnpj,
                'empresa_nome': mov.empresa_cnpj.nome,
                'funcionario_cpf': mov.funcionario_cpf.cpf,
                'funcionario_nome': mov.funcionario_cpf.nome,
                'produto_codigo': mov.produto_codigo.codigo_produto,
                'produto_nome': mov.produto_codigo.nome,
                'data_competencia': str(mov.data_competencia),
                'valor_beneficio': float(mov.valor_beneficio),
                'quantidade_dias': mov.quantidade_dias
            })

        return Response({
            'importacao': importacao_serializer.data,
            'movimentacoes': movimentacoes_data,
            'total_movimentacoes': len(movimentacoes_data)
        })
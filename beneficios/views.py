import logging
from django.utils import timezone

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.services.fedhub_service import FedhubService
from .models import Produto, MovimentacaoBeneficio, Importacao, Boleto, Faturamento
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
            'aprovado': 'APROVADO',
            'em_faturamento': 'EM_FATURAMENTO',
            'faturado': 'FATURADO',
            'comprado': 'COMPRADO',
            'pago_parcialmente': 'PAGO_PARCIALMENTE',
            'cancelado': 'CANCELADO',
            'pendente': 'PENDING',
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

        if status_backend == 'CANCELADO':
            from beneficios.models import Faturamento, Boleto
            from django.conf import settings
            import requests

            faturamentos = Faturamento.objects.filter(importacao=importacao)
            for fat in faturamentos:
                fat.status = 'FAILED'
                fat.save(update_fields=['status'])
                
                boletos = Boleto.objects.filter(faturamento=fat).exclude(NFs_id__isnull=True).exclude(NFs_id='')
                ids_integracao = [b.NFs_id for b in boletos]
                
                if ids_integracao:
                    try:
                        api_url = getattr(settings, 'NFSE_API_URL', 'https://fedcorp-nfs-e-django-ebh2e.ondigitalocean.app/api/nfse/emissao/vr/')
                        from urllib.parse import urljoin, urlparse
                        parsed_uri = urlparse(api_url)
                        base_api = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                        cancel_url = urljoin(base_api, "/api/nfse/cancela/nfse/")
                        
                        payload = {
                            "notas": [{"id_integracao": nfs_id} for nfs_id in ids_integracao]
                        }
                        headers = {
                            'Content-Type': 'application/json',
                            'X-API-KEY': getattr(settings, 'NFSE_X_API_KEY', 'fedcorp_static_token_secure_xyz123'),
                        }
                        
                        response = requests.post(cancel_url, json=payload, headers=headers, timeout=30)
                        response.raise_for_status()
                        logger.info(f"Cancelamento de {len(ids_integracao)} notas enviado com sucesso para NFS-e-Django.")
                    except Exception as e_cancel:
                        logger.error(f"Erro ao cancelar notas para faturamento #{fat.id}: {str(e_cancel)}")
        
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
                nome_cliente = request.data.get('nome_cliente', administradora.razao_social if administradora else 'Cliente')
                
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


class MarcarResponsavelView(views.APIView):
    """
    Marca ou desmarca o responsável por uma importação.
    Usado para evitar que duas faturistas trabalhem na mesma importação.
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

        user = request.user
        acao = request.data.get('acao', 'marcar')

        if acao == 'marcar':
            if importacao.responsavel and importacao.responsavel != user:
                return Response(
                    {"detail": f"Importação já está sendo processada por {importacao.responsavel.nome or importacao.responsavel.email}.",
                     "responsavel": importacao.responsavel.id,
                     "responsavel_nome": importacao.responsavel.nome or importacao.responsavel.email},
                    status=status.HTTP_409_CONFLICT
                )
            importacao.responsavel = user
            importacao.save(update_fields=['responsavel'])
            return Response({
                "message": "Importação marcada como sua.",
                "responsavel": user.id,
                "responsavel_nome": user.nome or user.email
            }, status=status.HTTP_200_OK)

        elif acao == 'desmarcar':
            if importacao.responsavel and importacao.responsavel != user:
                return Response(
                    {"detail": "Apenas o responsável pode desmarcar."},
                    status=status.HTTP_403_FORBIDDEN
                )
            importacao.responsavel = None
            importacao.save(update_fields=['responsavel'])
            return Response({
                "message": "Importação desmarcada.",
                "responsavel": None
            }, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Ação inválida. Use 'marcar' ou 'desmarcar'."},
            status=status.HTTP_400_BAD_REQUEST
        )


class ReenviarEmailView(views.APIView):
    """
    Reenvia o e-mail de boletos para o cliente.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            importacao = Importacao.objects.get(id=pk)
        except Importacao.DoesNotExist:
            return Response(
                {"detail": "Importação não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        if importacao.status not in ('FATURADO', 'BOLETO_VR_ENVIADO'):
            return Response(
                {"detail": "O e-mail só pode ser reenviado para pedidos com status FATURADO ou BOLETO_VR_ENVIADO."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from upload.tasks import _disparar_email_boleto_cliente
        try:
            result = _disparar_email_boleto_cliente.delay(importacao.id)
            logger.info(f"[REENVIAR_EMAIL] Task agendada para importacao_id={importacao.id}")
        except Exception as e:
            logger.warning(f"[REENVIAR_EMAIL] Falha ao agendar task: {e}")
            result = None

        return Response({
            "message": "E-mail de boleto será reenviado.",
            "importacao_id": importacao.id,
            "status": importacao.status,
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
        administradora = getattr(user, 'administradora_ativa', None)
        
        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ultima_importacao = Importacao.objects.filter(
            administradora=administradora,
            status__in=['COMPLETED', 'FATURADO']
        )
        if user.tipo == "adm":
            ultima_importacao = ultima_importacao.exclude(usuario__tipo__in=["dep", "dev"])
        if user.tipo == "dep":
            ultima_importacao = ultima_importacao.exclude(usuario__tipo__in=["adm", "dev"])
        ultima_importacao = ultima_importacao.order_by('-data_importacao').first()
   
   
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
            
        data = {
            "condominios": condominios,
            "importacao_id": ultima_importacao.id,
            "data_importacao": ultima_importacao.data_importacao.isoformat()
        }
        
        logger.info(f"Última importação encontrada: ID {ultima_importacao.id}, Data {ultima_importacao.data_importacao}, Total Movimentações: {movimentacoes.count()}")
        logger.debug(f"Dados formatados para resposta: {data}")

        return Response({
            'condominios': condominios,
            'importacao_id': ultima_importacao.id,
            'data_importacao': ultima_importacao.data_importacao.isoformat()
        })


class UltimaMovimentacaoDashboard(views.APIView):
    """
    View para buscar a última movimentação com dados agrupados para o dashboard.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request):
        user = request.user
        administradora = getattr(user, 'administradora_ativa', None)
        
        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Busca a última importação
        ultima_importacao = Importacao.objects.filter(
            administradora=administradora
        )
        if user.tipo == "adm":
            ultima_importacao = ultima_importacao.exclude(usuario__tipo__in=["dep", "dev"])
        if user.tipo == "dep":
            ultima_importacao = ultima_importacao.exclude(usuario__tipo__in=["adm", "dev"])
        ultima_importacao = ultima_importacao.order_by('-data_importacao').first()
        
        if not ultima_importacao:
            return Response(
                {"detail": "Nenhuma importação encontrada para esta administradora."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Busca movimentações com dados relacionados
        movimentacoes = MovimentacaoBeneficio.objects.filter(
            importacao=ultima_importacao
        ).select_related(
            'empresa_cnpj',
            'funcionario_cpf',
            'produto_codigo'
        )
        
        # Agrupa por condomínio
        condos_dict = {}
        for mov in movimentacoes:
            cnpj = mov.empresa_cnpj.cnpj
            
            if cnpj not in condos_dict:
                condos_dict[cnpj] = {
                    # REMOVA a linha 'id' ou use cnpj como id
                    'cnpj': cnpj,  # Use cnpj como identificador
                    'nome': mov.empresa_cnpj.nome,
                    'endereco': mov.empresa_cnpj.endereco or '',
                    'numero': mov.empresa_cnpj.numero or '',
                    'complemento': mov.empresa_cnpj.complemento or '',
                    'bairro': mov.empresa_cnpj.bairro or '',
                    'cidade': mov.empresa_cnpj.cidade or '',
                    'estado': mov.empresa_cnpj.estado or '',
                    'cep': mov.empresa_cnpj.cep or '',
                    'valor_total': 0,
                    'funcionarios': {}
                }
            
            cpf = mov.funcionario_cpf.cpf
            if cpf not in condos_dict[cnpj]['funcionarios']:
                condos_dict[cnpj]['funcionarios'][cpf] = {
                    'cpf': cpf,  # Use cpf como identificador
                    'nome': mov.funcionario_cpf.nome,
                    'matricula': mov.funcionario_cpf.matricula or '',
                    'departamento': mov.funcionario_cpf.departamento or '',
                    'funcao': mov.funcionario_cpf.funcao or '',
                    'data_nascimento': str(mov.funcionario_cpf.data_nascimento) if mov.funcionario_cpf.data_nascimento else '',
                    'valor_total': 0,
                    'movimentacoes': []
                }
            
            valor = float(mov.valor_beneficio)
            condos_dict[cnpj]['funcionarios'][cpf]['valor_total'] += valor
            condos_dict[cnpj]['valor_total'] += valor
            
            condos_dict[cnpj]['funcionarios'][cpf]['movimentacoes'].append({
                'id': mov.id,
                'produto': mov.produto_codigo.nome,
                'codigo_produto': mov.produto_codigo.codigo_produto,
                'valor': valor,
                'data_competencia': str(mov.data_competencia),
                'quantidade_dias': mov.quantidade_dias
            })
        
        # Converte para lista e ordena
        condominios = []
        for cnpj, condo_data in condos_dict.items():
            condo_data['funcionarios'] = list(condo_data['funcionarios'].values())
            # Ordena funcionários por nome
            condo_data['funcionarios'].sort(key=lambda x: x['nome'])
            condominios.append(condo_data)
        
        # Ordena condomínios por nome
        condominios.sort(key=lambda x: x['nome'])
        
        # Prepara resposta formatada
        response_data = {
            'id': ultima_importacao.id,
            'data_importacao': ultima_importacao.data_importacao.isoformat(),
            'status': ultima_importacao.status,
            'status_display': dict(Importacao.STATUS_CHOICES).get(ultima_importacao.status, ultima_importacao.status),
            'valor_total': float(ultima_importacao.valor_total or 0),
            'total_registros': ultima_importacao.total_registros,
            'registros_processados': ultima_importacao.registros_processados,
            'data_vencimento': str(ultima_importacao.data_vencimento) if ultima_importacao.data_vencimento else None,
            'vigencia_inicio': str(ultima_importacao.vigencia_inicio) if ultima_importacao.vigencia_inicio else None,
            'vigencia_fim': str(ultima_importacao.vigencia_fim) if ultima_importacao.vigencia_fim else None,
            'condominios': condominios,
            'total_condominios': len(condominios),
            'total_funcionarios': sum(len(c['funcionarios']) for c in condominios),
            'total_movimentacoes': movimentacoes.count(),
            'importacao_nome': f"IMP-{ultima_importacao.id}",
            'tipo_importacao': ultima_importacao.modelo_importacao,
            # Planilhas no S3. A editada só existe quando o usuário corrigiu
            # dados na confirmação; o card da visão geral prioriza ela e cai na
            # original quando não houver.
            'arquivo_s3': ultima_importacao.arquivo_s3,
            'arquivo_s3_editado': ultima_importacao.arquivo_s3_editado,
        }
        
        logger.info(f"Dashboard - Última importação: ID {ultima_importacao.id}, "
                   f"Valor Total: {response_data['valor_total']}, "
                   f"Condomínios: {response_data['total_condominios']}, "
                   f"Funcionários: {response_data['total_funcionarios']}, "
                   f"Movimentações: {response_data['total_movimentacoes']}")
        
        return Response(response_data, status=status.HTTP_200_OK)
            
            
class ImportacaoListView(views.APIView):
    """
    Rota para listar o histórico de importações.
    Suporta paginação via query params ?page=1&limit=20.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @extend_schema(operation_id='beneficios_importacoes_list')
    def get(self, request):
        from datetime import timedelta
        from django.db.models import Prefetch
        from django.utils import timezone
        from beneficios.models import Faturamento, FaturamentoDocumento

        user = request.user
        administradora = getattr(user, 'administradora_ativa', None)

        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtro: últimos 30 dias
        data_limite = timezone.now() - timedelta(days=30)

        if user.tipo == "dev" or user.tipo == "fat":
            importacoes = Importacao.objects.filter(
                data_importacao__gte=data_limite
            ).select_related(
                'file_upload', 'usuario', 'administradora'
            ).order_by('-data_importacao')
        else:
            queryset = Importacao.objects.filter(
                administradora=administradora,
                data_importacao__gte=data_limite,
            ).select_related(
                'file_upload', 'usuario', 'administradora'
            )
            if user.tipo == "adm":
                queryset = queryset.exclude(usuario__tipo__in=["dep", "dev"])
            if user.tipo == "dep":
                queryset = queryset.exclude(usuario__tipo__in=["adm", "dev"])
            importacoes = queryset.order_by('-data_importacao')

        documentos_prefetch = Prefetch(
            'documentos',
            queryset=FaturamentoDocumento.objects.select_related('condominio'),
        )
        faturamentos_prefetch = Prefetch(
            'faturamentos',
            queryset=Faturamento.objects.prefetch_related(
                'arquivos_originais',
                documentos_prefetch,
                # boletos_rel alimenta get_data_credito() e _get_fatura_number()
                # no serializer; sem o prefetch cada importação dispara queries
                # próprias por faturamento.
                'boletos_rel',
            ),
        )
        importacoes = importacoes.prefetch_related(faturamentos_prefetch)

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            limit = max(int(request.query_params.get('limit', 20)), 1)
        except (TypeError, ValueError):
            limit = 20

        total = importacoes.count()
        pages = max((total + limit - 1) // limit, 1)
        page = min(page, pages)
        offset = (page - 1) * limit
        paginated = importacoes[offset:offset + limit]

        serializer = ImportacaoComMovimentacoesSerializer(paginated, many=True)

        logger.debug(f"ImportacaoListView: page={page}, limit={limit}, total={total}")

        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'pages': pages,
            'limit': limit,
        })


class PedidoCartaoView(views.APIView):
    """
    Cria e lista pedidos de cartão do usuário da administradora.
    POST: cria pedido (força administradora do user logado)
    GET: lista pedidos da administradora do user logado
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        from beneficios.serializers import PedidoCartaoSerializer

        user = request.user
        administradora = getattr(user, 'administradora_ativa', None)

        if not administradora:
            return Response(
                {'detail': 'Usuário não possui administradora vinculada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PedidoCartaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(administradora=administradora, criado_por=user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request):
        from beneficios.models import PedidoCartao
        from beneficios.serializers import PedidoCartaoSerializer

        user = request.user
        administradora = getattr(user, 'administradora_ativa', None)

        if not administradora:
            return Response(
                {'detail': 'Usuário não possui administradora vinculada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pedidos = PedidoCartao.objects.filter(
            administradora=administradora
        ).order_by('-created_at')

        serializer = PedidoCartaoSerializer(pedidos, many=True)
        return Response(serializer.data)


class PedidoCartaoOperacionalView(views.APIView):
    """
    Lista todos os pedidos de cartão para o time operacional.
    Apenas dev/fat podem acessar.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        from django.db.models import Q
        from beneficios.models import PedidoCartao
        from beneficios.serializers import PedidoCartaoSerializer

        user = request.user
        if user.tipo not in ('dev', 'fat'):
            return Response(
                {'detail': 'Acesso não autorizado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        pedidos = PedidoCartao.objects.select_related(
            'administradora', 'criado_por'
        ).order_by('-created_at')

        status_filtro = request.query_params.get('status')
        tipo_filtro = request.query_params.get('tipo')
        search = request.query_params.get('search', '').strip()

        if status_filtro:
            pedidos = pedidos.filter(status=status_filtro)
        if tipo_filtro:
            pedidos = pedidos.filter(tipo_pedido=tipo_filtro)
        if search:
            pedidos = pedidos.filter(
                Q(nome_completo__icontains=search)
                | Q(cpf__icontains=search)
                | Q(nome_condominio__icontains=search)
                | Q(administradora__razao_social__icontains=search)
            )

        serializer = PedidoCartaoSerializer(pedidos, many=True)
        return Response(serializer.data)


class PedidoCartaoStatusView(views.APIView):
    """
    Atualiza o status de um pedido de cartão.
    Apenas dev/fat podem acessar.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, pk):
        from beneficios.models import PedidoCartao
        from beneficios.serializers import PedidoCartaoSerializer

        user = request.user
        if user.tipo not in ('dev', 'fat'):
            return Response(
                {'detail': 'Acesso não autorizado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            pedido = PedidoCartao.objects.get(pk=pk)
        except PedidoCartao.DoesNotExist:
            return Response(
                {'detail': 'Pedido não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        novo_status = request.data.get('status')
        valid_statuses = [choice[0] for choice in PedidoCartao.STATUS_CHOICES]
        if novo_status not in valid_statuses:
            return Response(
                {'detail': f'Status inválido. Opções: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pedido.status = novo_status
        pedido.observacao = request.data.get('observacao', pedido.observacao)
        pedido.save(update_fields=['status', 'observacao', 'updated_at'])

        serializer = PedidoCartaoSerializer(pedido)
        return Response(serializer.data)

class ImportacaoDetailView(views.APIView):
    """
    Rota para ver os detalhes de uma importação específica,
    incluindo as movimentações associadas (paginadas via ?mov_page=1&mov_limit=100).
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk):
        user = request.user
        administradora = getattr(user, 'administradora_ativa', None)

        if user.tipo not in ("dev", "fat") and not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if user.tipo in ("dev", "fat"):
                queryset = Importacao.objects.filter(
                    id=pk
                ).select_related('file_upload', 'usuario', 'administradora')
            else:
                queryset = Importacao.objects.filter(
                    administradora=administradora,
                    id=pk
                ).select_related('file_upload', 'usuario', 'administradora')
                if user.tipo == "adm":
                    queryset = queryset.exclude(usuario__tipo__in=["dep", "dev"])
                if user.tipo == "dep":
                    queryset = queryset.exclude(usuario__tipo__in=["adm", "dev"])
            importacao = queryset.first()

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

        movimentacoes_qs = MovimentacaoBeneficio.objects.filter(
            importacao=importacao
        ).select_related(
            'empresa_cnpj',
            'funcionario_cpf',
            'produto_codigo'
        )

        total_mov = movimentacoes_qs.count()

        try:
            mov_page = max(int(request.query_params.get('mov_page', 1)), 1)
        except (TypeError, ValueError):
            mov_page = 1
        try:
            mov_limit = min(max(int(request.query_params.get('mov_limit', 100)), 1), 500)
        except (TypeError, ValueError):
            mov_limit = 100

        mov_pages = max((total_mov + mov_limit - 1) // mov_limit, 1)
        mov_page = min(mov_page, mov_pages)
        mov_offset = (mov_page - 1) * mov_limit
        paginated_mov = movimentacoes_qs[mov_offset:mov_offset + mov_limit]

        movimentacoes_data = []
        for mov in paginated_mov:
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
            'total_movimentacoes': total_mov,
            'mov_page': mov_page,
            'mov_pages': mov_pages,
            'mov_limit': mov_limit,
        })


class BoletoBaixaView(views.APIView):
    """
    View para atualizar a baixa de um Boleto específico (por ID na URL ou por identificador/documento no body).
    Autenticação por token estático X-API-KEY.
    """
    from rest_framework.permissions import AllowAny
    permission_classes = [AllowAny]
    authentication_classes = []

    def _get_boleto(self, request, pk=None):
        if pk:
            return Boleto.objects.filter(pk=pk).first()

        boleto_id = request.data.get('boleto_id') or request.data.get('id')
        documento = request.data.get('documento')
        identificador = request.data.get('identificador')

        if boleto_id:
            return Boleto.objects.filter(id=boleto_id).first()
        if documento:
            return Boleto.objects.filter(documento=documento).first()
        if identificador:
            return Boleto.objects.filter(identificador=identificador).first()

        return None

    def post(self, request, pk=None):
        from datetime import datetime
        from django.conf import settings
        
        # Validação do token estático X-API-KEY
        api_key = request.headers.get('X-API-KEY') or request.META.get('HTTP_X_API_KEY')
        expected_key = getattr(settings, 'NFSE_X_API_KEY', 'fedcorp_static_token_secure_xyz123')
        if api_key != expected_key:
            return Response(
                {"detail": "Acesso não autorizado. Chave de API inválida ou ausente."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        boleto = self._get_boleto(request, pk)
        if not boleto:
            return Response(
                {"detail": "Boleto não encontrado com as informações fornecidas."},
                status=status.HTTP_404_NOT_FOUND
            )

        status_recv = request.data.get('status')
        dt_baixa_str = request.data.get('dt_baixa') or request.data.get('dt_cancelamento')
        forma_pagamento = request.data.get('forma_pagamento')

        # Se vier 'baixa' explícito, respeitamos. Senão, deduzimos do status:
        # Se status for 'C' (Cancelado) ou semelhante, baixa = False. 
        # Se for 'A' (Aprovado), 'B' (Baixado) ou não informado, baixa = True.
        baixa = request.data.get('baixa')
        if baixa is not None:
            baixa_bool = str(baixa).lower() in ('true', '1', 'yes')
        else:
            baixa_bool = status_recv != 'C' if status_recv else True

        # Converter data de baixa
        dt_baixa = None
        if dt_baixa_str:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S'):
                try:
                    dt_baixa = datetime.strptime(dt_baixa_str.split(' ')[0], fmt).date()
                    break
                except ValueError:
                    pass
            if not dt_baixa:
                return Response(
                    {"detail": f"Formato de data inválido: {dt_baixa_str}. Use YYYY-MM-DD ou DD/MM/YYYY."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            if baixa_bool:
                dt_baixa = timezone.now().date()

        # Observação da baixa
        obs_baixa = request.data.get('obs_baixa')
        if not obs_baixa and forma_pagamento:
            obs_baixa = f"Pago via {forma_pagamento}"

        # Atualizar boleto
        boleto.baixa = baixa_bool
        boleto.dt_baixa = dt_baixa
        if status_recv:
            boleto.status = status_recv
        if obs_baixa:
            boleto.obs_baixa = obs_baixa
        
        boleto.save()

        return Response({
            "detail": "Baixa do Boleto atualizada com sucesso.",
            "boleto": {
                "id": boleto.id,
                "documento": boleto.documento,
                "identificador": boleto.identificador,
                "baixa": boleto.baixa,
                "status": boleto.status,
                "dt_baixa": boleto.dt_baixa.strftime('%Y-%m-%d') if boleto.dt_baixa else None,
                "obs_baixa": boleto.obs_baixa
            }
        }, status=status.HTTP_200_OK)

    def patch(self, request, pk=None):
        return self.post(request, pk)


class ListarBoletosView(views.APIView):
    """
    Retorna faturas no formato esperado pelo Kanban do Operacional.
    Agrupa Importacao + Faturamento + Boletos em estrutura coEstipulantes.
    Exclui importacoes PAGO com mais de 30 dias para reduzir carga.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))

        all_boletos = Boleto.objects.all()

        from collections import defaultdict
        grupos = defaultdict(list)
        for b in all_boletos:
            if b.fatura:
                grupos[b.fatura].append(b)

        faturas_ordenadas = sorted(grupos.keys(), reverse=True)
        total = len(faturas_ordenadas)
        total_pages = max(1, (total + limit - 1) // limit)
        faturas_page = faturas_ordenadas[(page - 1) * limit : page * limit]

        fedhub_status_map = {}
        try:
            fedhub = FedhubService()
            for fat_num in faturas_page[:10]:
                fedhub_boletos = fedhub.buscar_todos_boletos_por_fatura(fat_num)
                if isinstance(fedhub_boletos, list):
                    for fb in fedhub_boletos:
                        doc = fb.get("documento")
                        if doc:
                            fedhub_status_map[str(doc).strip()] = {
                                "status": fb.get("status"),
                                "baixa": bool(fb.get("baixa", False)),
                                "dt_baixa": fb.get("dt_baixa"),
                            }
        except Exception as e:
            logger.warning(f"Erro ao buscar status no FedHub: {e}")

        data = []
        for fat_num in faturas_page:
            boletos_grupo = grupos[fat_num]
            primeiro = boletos_grupo[0]

            boletos_list = []
            for b in boletos_grupo:
                doc_key = str(b.documento).strip() if b.documento else None
                fh = fedhub_status_map.get(doc_key, {}) if doc_key else {}
                boletos_list.append({
                    "id": b.id,
                    "documento": b.documento,
                    "cnpj_cobrado": b.cnpj_cobrado,
                    "nome_cobrado": b.nome_cobrado,
                    "fatura": b.fatura,
                    "valor": float(b.valor) if b.valor else 0.0,
                    "vencimento": b.vencimento.strftime('%Y-%m-%d') if b.vencimento else None,
                    "baixa": fh.get("baixa", b.baixa),
                    "dt_baixa": fh.get("dt_baixa", b.dt_baixa.strftime('%Y-%m-%d') if b.dt_baixa else None),
                    "status": fh.get("status", b.status),
                    "nosso_numero": b.nosso_numero,
                })

            importacao_status = None
            faturamento = primeiro.faturamento
            if faturamento:
                importacao = getattr(faturamento, 'importacao', None)
                importacao_status = importacao.status if importacao else None

            data.append({
                "id": fat_num,
                "administradora_nome": faturamento.administradora.razao_social if faturamento and faturamento.administradora else '-',
                "competencia": faturamento.competencia.strftime('%Y-%m-%d') if faturamento and faturamento.competencia else None,
                "valor_total": sum(bl["valor"] for bl in boletos_list),
                "status": importacao_status or 'PENDING',
                "status_display": importacao_status or 'Pendente',
                "data_vencimento": boletos_list[0]["vencimento"] if boletos_list else None,
                "boletos": boletos_list,
            })

        return Response({
            "data": data,
            "pages": total_pages,
            "total": total,
        })

class KanbanFaturasView(views.APIView):
    """
    Retorna faturas no formato esperado pelo Kanban do Operacional.
    Agrupa Importacao + Faturamento + Boletos em estrutura coEstipulantes.
    Exclui importações PAGO com mais de 30 dias para reduzir carga.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        from datetime import date, timedelta
        from django.db.models import Prefetch
        from beneficios.models import Faturamento, Boleto

        hoje = date.today()
        corte_pago = hoje - timedelta(days=30)

        boletos_prefetch = Prefetch(
            'boletos_rel',
            queryset=Boleto.objects.order_by('vencimento'),
        )
        faturamentos_prefetch = Prefetch(
            'faturamentos',
            queryset=Faturamento.objects.prefetch_related(boletos_prefetch),
        )

        importacoes = Importacao.objects.select_related(
            'administradora', 'usuario', 'file_upload'
        ).prefetch_related(faturamentos_prefetch).exclude(
            status__in=['CANCELADO']
        ).exclude(
            status='PAGO', data_importacao__lt=corte_pago
        ).order_by('-data_importacao')

        faturas = []

        for imp in importacoes:
            faturamentos_rel = list(imp.faturamentos.all())
            faturamento = faturamentos_rel[0] if faturamentos_rel else None
            boletos = list(faturamento.boletos_rel.all()) if faturamento else []

            admin = imp.administradora
            estipulante_nome = admin.razao_social if admin else ''
            estipulante_cnpj = admin.cnpj if admin else ''

            co_estipulantes = []
            for boleto in boletos:
                vencimento = boleto.vencimento.isoformat() if boleto.vencimento else None
                pago = boleto.baixa
                data_pagamento = boleto.dt_baixa.isoformat() if boleto.dt_baixa else None
                valor_cents = int(float(boleto.valor or 0) * 100)

                co_estipulantes.append({
                    'id': boleto.id,
                    'idx': boleto.id,
                    'name': boleto.nome_cobrado or '',
                    'nome': boleto.nome_cobrado or '',
                    'condominio': boleto.nome_cobrado or '',
                    'condominio_nome': boleto.nome_cobrado or '',
                    'cnpj': boleto.cnpj_cobrado or '',
                    'documento': boleto.cnpj_cobrado or '',
                    'cpf_cnpj': boleto.cnpj_cobrado or '',
                    'cpfCnpj': boleto.cnpj_cobrado or '',
                    'razao_social': boleto.nome_cobrado or '',
                    'valorCents': valor_cents,
                    'valor_cents': valor_cents,
                    'valorCentavos': valor_cents,
                    'valor_total': valor_cents,
                    'valor': valor_cents,
                    'total': valor_cents,
                    'dueDate': vencimento,
                    'due_date': vencimento,
                    'vencimento': vencimento,
                    'data_vencimento': vencimento,
                    'dt_vencimento': vencimento,
                    'dataCredito': None,
                    'data_credito': None,
                    'credito': None,
                    'paidAt': data_pagamento if pago else None,
                    'paid_at': data_pagamento if pago else None,
                    'data_pagamento': data_pagamento if pago else None,
                    'pago_em': data_pagamento if pago else None,
                    'dt_pagamento': data_pagamento if pago else None,
                    'sentToCP': False,
                    'sent_to_cp': False,
                    'enviado_cp': False,
                    'enviado_contas_pagar': False,
                    'enviadoContasPagar': False,
                    'formaPagamento': None,
                    'forma_pagamento': None,
                    'formaPagemento': None,
                })

            total_cents = int(float(imp.valor_total or 0) * 100)
            usuario = imp.usuario
            uploader_name = usuario.email if usuario else ''

            vencimento_imp = imp.data_vencimento.isoformat() if imp.data_vencimento else None
            recebimento_imp = imp.data_recebimento.isoformat() if imp.data_recebimento else None

            status_map = {
                'FATURADO': 'faturado',
                'CONFIRMAR_PAGAMENTO': 'atrasado',
                'BOLETO_VR_ENVIADO': 'aprovado',
                'PAGO': 'pago',
                'COMPLETED': 'pago',
            }
            kanban = status_map.get(imp.status, 'faturado')

            if boletos and all(boleto.baixa for boleto in boletos):
                kanban = 'pago'

            if imp.data_recebimento:
                amanha = hoje + timedelta(days=1)
                if imp.data_recebimento == amanha:
                    kanban = 'enviar_compra'

            faturas.append({
                'id': imp.id,
                'pk': imp.id,
                'codigo': imp.id,
                'numero': imp.id,
                'faturaNum': f'IMP-{imp.id}',
                'fatura_num': f'IMP-{imp.id}',
                'numero_fatura': f'IMP-{imp.id}',
                'emissao': imp.data_importacao.strftime('%Y-%m-%d') if imp.data_importacao else None,
                'data_emissao': imp.data_importacao.strftime('%Y-%m-%d') if imp.data_importacao else None,
                'createdAt': imp.data_importacao.isoformat() if imp.data_importacao else None,
                'created_at': imp.data_importacao.isoformat() if imp.data_importacao else None,
                'data_criacao': imp.data_importacao.isoformat() if imp.data_importacao else None,
                'estipulante': {
                    'name': estipulante_nome,
                    'nome': estipulante_nome,
                    'cnpj': estipulante_cnpj,
                },
                'estipulante_nome': estipulante_nome,
                'estipulante_cnpj': estipulante_cnpj,
                'administradora_nome': estipulante_nome,
                'uploaderName': uploader_name,
                'uploader_name': uploader_name,
                'usuario_nome': uploader_name,
                'responsavel_nome': uploader_name,
                'created_by_name': uploader_name,
                'uploaderId': usuario.id if usuario else None,
                'uploader_id': usuario.id if usuario else None,
                'usuario_id': usuario.id if usuario else None,
                'responsavel_id': usuario.id if usuario else None,
                'manualStatus': kanban,
                'manual_status': kanban,
                'status_manual': kanban,
                'totalCents': total_cents,
                'total_cents': total_cents,
                'valor_total_cents': total_cents,
                'valor_total': total_cents,
                'vencimento': vencimento_imp,
                'data_vencimento': vencimento_imp,
                'dueDate': vencimento_imp,
                'due_date': vencimento_imp,
                'recebimento': recebimento_imp,
                'data_recebimento': recebimento_imp,
                'coEstipulantes': co_estipulantes,
                'co_estipulantes': co_estipulantes,
                'condominios': co_estipulantes,
                'itens': co_estipulantes,
                '_importacao_status': imp.status,
                '_faturamento_status': faturamento.status if faturamento else None,
            })

        return Response({'data': faturas})


class KanbanBoletosView(views.APIView):
    """Retorna boletos no formato esperado pelo Kanban de Boletos VR."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        boletos = Boleto.objects.select_related('faturamento').order_by('-created_at')

        result = []
        for boleto in boletos:
            result.append({
                'id': boleto.id,
                'name': boleto.nome_cobrado or boleto.fatura or f'Boleto {boleto.id}',
                'file_name': boleto.fatura or '',
                'due_date': boleto.vencimento.isoformat() if boleto.vencimento else None,
                'value_cents': int(float(boleto.valor or 0) * 100),
                'paid_at': boleto.dt_baixa.isoformat() if boleto.baixa and boleto.dt_baixa else None,
                'uploaderName': '',
                'uploader_name': '',
            })

        return Response({'data': result})


class KanbanMoveFaturaView(views.APIView):
    """
    Move uma fatura para outra coluna do Kanban.
    PATCH /api/beneficios/kanban/{id}/move/
    Body: { "status": "faturado"|"atrasado"|"aprovado"|"pago" }
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, pk):
        try:
            importacao = Importacao.objects.get(id=pk)
        except Importacao.DoesNotExist:
            return Response(
                {'detail': 'Importação não encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get('status')
        kanban_to_importacao = {
            'faturado': 'FATURADO',
            'atrasado': 'CONFIRMAR_PAGAMENTO',
            'aprovado': 'BOLETO_VR_ENVIADO',
            'pago': 'PAGO',
        }

        importacao_status = kanban_to_importacao.get(new_status)
        if not importacao_status:
            return Response(
                {'detail': f'Status inválido: {new_status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        importacao.status = importacao_status
        importacao.save(update_fields=['status'])

        return Response({'success': True, 'status': new_status})


class KanbanNotificarCompraView(views.APIView):
    """
    Verifica faturas com data de crédito para amanhã e envia e-mail de notificação.
    GET /api/beneficios/kanban/notificar-compra/
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        from datetime import date, timedelta
        from django.conf import settings

        amanha = date.today() + timedelta(days=1)

        importacoes = Importacao.objects.filter(
            data_recebimento=amanha,
            status__in=['FATURADO', 'CONFIRMAR_PAGAMENTO', 'BOLETO_VR_ENVIADO'],
        ).select_related('administradora', 'usuario')

        if not importacoes.exists():
            return Response({
                'detail': 'Nenhuma fatura pendente para amanhã.',
                'count': 0,
            })

        fedhub_service = FedhubService()
        email_faturamento = getattr(settings, 'EMAIL_FATURAMENTO', None)
        enviados = 0

        for importacao in importacoes:
            admin = importacao.administradora
            admin_nome = admin.razao_social if admin else 'N/A'
            vencimento = (
                importacao.data_vencimento.strftime('%d/%m/%Y')
                if importacao.data_vencimento
                else '-'
            )
            recebimento = (
                importacao.data_recebimento.strftime('%d/%m/%Y')
                if importacao.data_recebimento
                else '-'
            )

            try:
                if email_faturamento:
                    fedhub_service.enviar_email_upload(
                        email=email_faturamento,
                        user=importacao.usuario,
                        dados_processamento={
                            'arquivo_nome': f'Compra VR - {admin_nome}',
                            'data_envio': date.today().strftime('%d/%m/%Y'),
                            'competencia': f'Recebimento: {recebimento}',
                            'total_registros': importacao.total_registros or 0,
                            'total_funcionarios': importacao.total_funcionarios or 0,
                            'total_condominios': 0,
                            'valor_total': float(importacao.valor_total or 0),
                            'tipo_processamento': 'Enviar Compra VR - Amanhã',
                            'faturamento_id': importacao.id,
                            'vencimento': vencimento,
                            'periodo_inicio': recebimento,
                            'periodo_fim': recebimento,
                        },
                    )
                    enviados += 1
            except Exception as exc:
                logger.error(
                    'Erro ao enviar notificação para importação %s: %s',
                    importacao.id,
                    exc,
                )

        return Response({
            'detail': f'{enviados} notificação(ões) enviada(s).',
            'count': enviados,
            'pendentes': importacoes.count(),
        })


class ImportarBaseCondominiosView(views.APIView):
    """
    Importa base de condomínios e funcionários via Excel.
    Não gera faturamento: apenas cria ou atualiza registros.

    POST /api/beneficios/importar-base/
    Body: multipart/form-data com arquivo Excel.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        from entidades.models import Condominio, Funcionario

        arquivo = request.FILES.get('file')
        administradora_id = request.data.get('administradora_id')

        if not arquivo:
            return Response(
                {'detail': 'Nenhum arquivo enviado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not arquivo.name.lower().endswith(('.xlsx', '.xls')):
            return Response(
                {'detail': 'Formato inválido. Envie um arquivo .xlsx ou .xls.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import openpyxl

            workbook = openpyxl.load_workbook(arquivo, data_only=True)
            worksheet = workbook.active
            headers = [str(cell.value or '').strip().lower() for cell in worksheet[1]]

            condominios_criados = 0
            condominios_atualizados = 0
            funcionarios_criados = 0
            funcionarios_atualizados = 0
            erros = []

            for row_idx, row in enumerate(
                worksheet.iter_rows(min_row=2, values_only=True),
                start=2,
            ):
                try:
                    data = dict(zip(headers, row))

                    cnpj = ''.join(
                        filter(str.isdigit, str(data.get('cnpj', '') or '').strip())
                    )
                    if not cnpj or len(cnpj) != 14:
                        continue

                    nome = str(
                        data.get('nome', '')
                        or data.get('razao_social', '')
                        or ''
                    ).strip()
                    if not nome:
                        continue

                    condominio, created = Condominio.objects.update_or_create(
                        cnpj=cnpj,
                        defaults={
                            'nome': nome,
                            'tipo_local': str(
                                data.get('tipo_local', '') or 'CONDOMINIO'
                            ).strip(),
                            'endereco': str(
                                data.get('endereco', '')
                                or data.get('rua', '')
                                or ''
                            ).strip(),
                            'numero': str(data.get('numero', '') or '').strip(),
                            'complemento': str(
                                data.get('complemento', '') or ''
                            ).strip(),
                            'bairro': str(data.get('bairro', '') or '').strip(),
                            'cidade': str(data.get('cidade', '') or '').strip(),
                            'estado': str(
                                data.get('estado', '')
                                or data.get('uf', '')
                                or ''
                            ).strip(),
                            'cep': str(data.get('cep', '') or '').strip(),
                        },
                    )

                    if created:
                        condominios_criados += 1
                    else:
                        condominios_atualizados += 1

                    if administradora_id:
                        from entidades.models import Administradora, VinculoCondominio

                        try:
                            administradora = Administradora.objects.get(
                                id=administradora_id
                            )
                            VinculoCondominio.objects.get_or_create(
                                administradora=administradora,
                                condominio=condominio,
                            )
                        except Administradora.DoesNotExist:
                            pass

                    cpf = ''.join(
                        filter(str.isdigit, str(data.get('cpf', '') or '').strip())
                    )
                    if cpf and len(cpf) == 11:
                        funcionario_nome = str(
                            data.get('funcionario_nome', '')
                            or data.get('nome_funcionario', '')
                            or ''
                        ).strip()

                        if funcionario_nome:
                            _, funcionario_criado = Funcionario.objects.update_or_create(
                                cpf=cpf,
                                defaults={
                                    'nome': funcionario_nome,
                                    'matricula': str(
                                        data.get('matricula', '') or ''
                                    ).strip(),
                                    'departamento': str(
                                        data.get('departamento', '') or ''
                                    ).strip(),
                                    'funcao': str(
                                        data.get('funcao', '')
                                        or data.get('cargo', '')
                                        or ''
                                    ).strip(),
                                    'sexo': str(
                                        data.get('sexo', '') or ''
                                    ).strip()[:1] or None,
                                    'telefone': str(
                                        data.get('telefone', '') or ''
                                    ).strip(),
                                    'email': str(
                                        data.get('email', '') or ''
                                    ).strip(),
                                    'condominio': condominio,
                                },
                            )

                            if funcionario_criado:
                                funcionarios_criados += 1
                            else:
                                funcionarios_atualizados += 1

                except Exception as exc:
                    erros.append(f'Linha {row_idx}: {exc}')

            return Response({
                'detail': 'Importação concluída.',
                'condominios_criados': condominios_criados,
                'condominios_atualizados': condominios_atualizados,
                'funcionarios_criados': funcionarios_criados,
                'funcionarios_atualizados': funcionarios_atualizados,
                'erros': erros[:20],
                'total_erros': len(erros),
            })

        except ImportError:
            return Response(
                {'detail': 'Biblioteca openpyxl não instalada no servidor.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            logger.error('Erro ao importar base: %s', exc)
            return Response(
                {'detail': f'Erro ao processar arquivo: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ExcluirBaseCondominiosView(views.APIView):
    """
    Exclui a base de condomínios e funcionários de uma administradora.
    DELETE /api/beneficios/excluir-base/{administradora_id}/
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, administradora_id):
        from entidades.models import (
            Administradora,
            VinculoCondominio,
            Condominio,
            Funcionario,
        )

        try:
            administradora = Administradora.objects.get(id=administradora_id)
        except Administradora.DoesNotExist:
            return Response(
                {'detail': 'Administradora não encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        vinculos = VinculoCondominio.objects.filter(administradora=administradora)
        condominio_ids = list(vinculos.values_list('condominio_id', flat=True))

        funcionarios_removidos = Funcionario.objects.filter(
            condominio_id__in=condominio_ids
        ).delete()[0]
        vinculos_removidos = vinculos.delete()[0]
        condominios_removidos = Condominio.objects.filter(
            cnpj__in=condominio_ids
        ).delete()[0]

        return Response({
            'detail': 'Base excluída com sucesso.',
            'condominios_removidos': condominios_removidos,
            'vinculos_removidos': vinculos_removidos,
            'funcionarios_removidos': funcionarios_removidos,
        })


class ConsultarBoletosView(views.APIView):
    """
    Lista faturas e boletos com filtros de status.
    GET /api/beneficios/boletos/?administradora_id=1&status=pago

    - dev/fat: visualiza todos os faturamentos;
    - adm: visualiza apenas faturas da administradora ativa;
    - importações pagas com mais de 30 dias são excluídas.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        from datetime import date, timedelta
        from django.db.models import Prefetch
        from beneficios.models import Faturamento, FaturamentoDocumento, Boleto

        user = request.user
        administradora_id = request.query_params.get('administradora_id')
        status_filtro = request.query_params.get('status')

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1

        try:
            limit = max(int(request.query_params.get('limit', 50)), 1)
        except (TypeError, ValueError):
            limit = 50

        if user.tipo == 'adm':
            administradora_ativa = getattr(user, 'administradora_ativa', None)
            if not administradora_ativa:
                return Response(
                    {'detail': 'Usuário não possui administradora vinculada.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            administradora_id = administradora_ativa.id
        elif user.tipo in ('dev', 'fat'):
            administradora_id = None

        hoje = date.today()
        corte_pago = hoje - timedelta(days=30)

        boletos_prefetch = Prefetch(
            'boletos_rel',
            queryset=Boleto.objects.order_by('vencimento'),
        )
        documentos_prefetch = Prefetch(
            'documentos',
            queryset=FaturamentoDocumento.objects.select_related('condominio'),
        )
        faturamentos_prefetch = Prefetch(
            'faturamentos',
            queryset=Faturamento.objects.prefetch_related(
                boletos_prefetch,
                documentos_prefetch,
            ),
        )

        importacoes_qs = Importacao.objects.select_related(
            'administradora', 'usuario'
        ).prefetch_related(faturamentos_prefetch).exclude(
            status__in=['CANCELADO']
        ).exclude(
            status='PAGO', data_importacao__lt=corte_pago
        )

        if administradora_id:
            importacoes_qs = importacoes_qs.filter(
                administradora_id=administradora_id
            )

        importacoes_qs = importacoes_qs.order_by('-data_importacao')

        total_importacoes = importacoes_qs.count()
        pages = max((total_importacoes + limit - 1) // limit, 1)
        page = min(page, pages)
        offset = (page - 1) * limit
        paginated_importacoes = importacoes_qs[offset:offset + limit]

        status_map = {
            'PAGO': 'Pago',
            'PENDENTE_PAGAMENTO': 'Pendente Pagamento',
            'PENDING': 'Pendente',
            'PROCESSING': 'Processando',
            'AGUARDANDO_FATURAMENTO': 'Aguardando Faturamento',
            'APROVADO': 'Aprovado',
            'FATURADO': 'Faturado',
            'CONFIRMAR_PAGAMENTO': 'Confirmar Pagamento',
            'BOLETO_VR_ENVIADO': 'Boleto VR Enviado',
            'COMPRADO': 'Comprado',
            'CANCELADO': 'Cancelado',
            'COMPLETED': 'Concluída',
            'FAILED': 'Falhou',
        }

        result = []
        for importacao in paginated_importacoes:
            faturamentos_rel = list(importacao.faturamentos.all())
            faturamento = faturamentos_rel[0] if faturamentos_rel else None
            administradora = importacao.administradora
            status_faturamento = faturamento.status if faturamento else 'PENDING'

            documentos = []
            boletos_data = []

            if faturamento:
                for documento in faturamento.documentos.all():
                    documentos.append({
                        'condominio_nome': (
                            documento.condominio.nome if documento.condominio else ''
                        ),
                        'condominio_cnpj': (
                            documento.condominio.cnpj if documento.condominio else ''
                        ),
                        'url_boleto': documento.url_boleto or '',
                        'url_nota_debito': documento.url_nota_debito or '',
                        'url_nota_fiscal': documento.url_nota_fiscal or '',
                    })

                for boleto in faturamento.boletos_rel.all():
                    boletos_data.append({
                        'id': boleto.id,
                        'nome_cobrado': boleto.nome_cobrado or '',
                        'cnpj_cobrado': boleto.cnpj_cobrado or '',
                        'documento': boleto.documento or '',
                        'fatura': boleto.fatura or '',
                        'vencimento': (
                            boleto.vencimento.isoformat()
                            if boleto.vencimento
                            else None
                        ),
                        'valor': float(boleto.valor) if boleto.valor else 0,
                        'baixa': boleto.baixa,
                        'dt_baixa': (
                            boleto.dt_baixa.isoformat()
                            if boleto.dt_baixa
                            else None
                        ),
                        'status': boleto.status or '',
                        'nosso_numero': boleto.nosso_numero or '',
                    })

                if boletos_data:
                    total_boletos = len(boletos_data)
                    boletos_pagos = sum(
                        1 for boleto in boletos_data if boleto['baixa']
                    )
                    if boletos_pagos == total_boletos:
                        status_faturamento = 'PAGO'
                    else:
                        status_faturamento = 'PENDENTE_PAGAMENTO'
                else:
                    status_faturamento = 'PENDENTE_PAGAMENTO'

            if status_filtro == 'pago' and status_faturamento != 'PAGO':
                continue
            if status_filtro == 'pendente' and status_faturamento == 'PAGO':
                continue

            if status_faturamento == 'PAGO':
                status_display = 'Pago'
            else:
                status_display = status_map.get(
                    importacao.status,
                    importacao.status,
                )

            result.append({
                'id': faturamento.id if faturamento else importacao.id,
                'faturamento_id': faturamento.id if faturamento else None,
                'competencia': (
                    faturamento.competencia.isoformat()
                    if faturamento and faturamento.competencia
                    else None
                ),
                'status': status_faturamento,
                'status_display': status_display,
                'progresso': faturamento.progresso if faturamento else 0,
                'valor_total': (
                    float(importacao.valor_total)
                    if importacao.valor_total
                    else 0
                ),
                'arquivo_unificado_url': (
                    faturamento.arquivo_unificado_url if faturamento else ''
                ),
                'importacao_id': importacao.id,
                'importacao_status': importacao.status,
                'administradora_id': (
                    administradora.id if administradora else None
                ),
                'administradora_nome': (
                    administradora.nome_fantasia
                    or administradora.razao_social
                    if administradora
                    else None
                ),
                'data_vencimento': (
                    importacao.data_vencimento.isoformat()
                    if importacao.data_vencimento
                    else None
                ),
                'data_recebimento': (
                    importacao.data_recebimento.isoformat()
                    if importacao.data_recebimento
                    else None
                ),
                'total_registros': importacao.total_registros or 0,
                'registros_processados': importacao.registros_processados or 0,
                'condominios': documentos,
                'boletos': boletos_data,
                'created_at': (
                    faturamento.criado_em.isoformat()
                    if faturamento and faturamento.criado_em
                    else (
                        importacao.data_importacao.isoformat()
                        if importacao.data_importacao
                        else None
                    )
                ),
            })

        return Response({
            'data': result,
            'total': total_importacoes,
            'page': page,
            'pages': pages,
            'limit': limit,
        })

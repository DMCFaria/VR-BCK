import logging
from django.utils import timezone

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
            'tipo_importacao': ultima_importacao.modelo_importacao
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

    def get(self, request):
        user = request.user
        administradora = getattr(user, 'administradora_ativa', None)

        if not administradora:
            return Response(
                {"detail": "Usuário não possui administradora vinculada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.tipo == "dev" or user.tipo == "fat":
            importacoes = Importacao.objects.select_related(
                'file_upload', 'usuario', 'administradora'
            ).order_by('-data_importacao')
        else:
            queryset = Importacao.objects.filter(administradora=administradora).select_related(
                'file_upload', 'usuario', 'administradora'
            )
            if user.tipo == "adm":
                queryset = queryset.exclude(usuario__tipo__in=["dep", "dev"])
            if user.tipo == "dep":
                queryset = queryset.exclude(usuario__tipo__in=["adm", "dev"])
            importacoes = queryset.order_by('-data_importacao')

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            limit = min(max(int(request.query_params.get('limit', 20)), 1), 100)
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
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        administradora_id = request.query_params.get('administradora_id')
        status_filter = request.query_params.get('status')

        all_boletos = Boleto.objects.select_related('faturamento', 'faturamento__importacao', 'faturamento__administradora').all()

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
            for fat_num in faturas_page:
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
            logger.warning(f"Erro ao buscar status no FedHub: {e}", exc_info=True)

        STATUS_DISPLAY = {
            'PAGO': 'Pago',
            'PENDENTE_PAGAMENTO': 'Pendente',
            'PENDING': 'Pendente',
            'FATURADO': 'Faturado',
            'COMPLETED': 'Concluído',
            'CANCELADO': 'Cancelado',
            'FAILED': 'Falhou',
        }

        data = []
        for fat_num in faturas_page:
            boletos_grupo = grupos[fat_num]
            primeiro = boletos_grupo[0]
            faturamento = primeiro.faturamento
            importacao = faturamento.importacao if faturamento else None

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

            importacao_status = importacao.status if importacao else None

            data.append({
                "id": faturamento.id if faturamento else fat_num,
                "administradora_nome": faturamento.administradora.nome if faturamento and faturamento.administradora else '-',
                "competencia": faturamento.competencia.strftime('%Y-%m-%d') if faturamento and faturamento.competencia else None,
                "valor_total": sum(bl["valor"] for bl in boletos_list),
                "status": importacao_status or 'PENDING',
                "status_display": STATUS_DISPLAY.get(importacao_status, importacao_status or 'Pendente'),
                "data_vencimento": boletos_list[0]["vencimento"] if boletos_list else None,
                "boletos": boletos_list,
            })

        if status_filter:
            sf = status_filter.lower()
            if sf in ('pago', 'paid'):
                data = [d for d in data if d['status'] in ('PAGO', 'COMPLETED')]
            elif sf in ('pendente', 'pending'):
                data = [d for d in data if d['status'] not in ('PAGO', 'COMPLETED')]

        return Response({
            "data": data,
            "pages": total_pages,
            "total": total,
        })
from rest_framework import viewsets, views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Prefetch
from .models import Produto, MovimentacaoBeneficio, Importacao
from .serializers import (
    ProdutoSerializer,
    MovimentacaoBeneficioSerializer,
    ImportacaoListSerializer,
    ImportacaoDetailSerializer,
    MovimentacaoReuseSerializer
)


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
                    'movimentacoes': []
                }

            condos_dict[cnpj]['funcionarios'][cpf]['movimentacoes'].append({
                'produto': mov.produto_codigo.nome,
                'codigo_produto': mov.produto_codigo.codigo_produto,
                'valor': float(mov.valor_beneficio)
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

        importacoes = Importacao.objects.filter(
            administradora=administradora
        ).order_by('-data_importacao')[:20]

        serializer = ImportacaoListSerializer(importacoes, many=True)
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
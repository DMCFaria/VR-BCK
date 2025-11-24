from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Produto, MovimentacaoBeneficio
from .serializers import ProdutoSerializer, MovimentacaoBeneficioSerializer

class ProdutoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, criar, atualizar e deletar Produtos.
    Rotas: /api/benefits/produtos/
    """
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'codigo_produto' # Define o código do produto como lookup para URLs


class MovimentacaoBeneficioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, criar, atualizar e deletar Movimentações de Benefício.
    Rotas: /api/benefits/movimentacoes/
    """
    queryset = MovimentacaoBeneficio.objects.order_by('-id').all()
    serializer_class = MovimentacaoBeneficioSerializer
    permission_classes = [IsAuthenticated]

    # O filtro pode ser útil, por exemplo, para buscar movimentações de um CPF
    def get_queryset(self):
        queryset = self.queryset
        funcionario_cpf = self.request.query_params.get('cpf', None)
        if funcionario_cpf is not None:
            queryset = queryset.filter(funcionario_cpf__cpf=funcionario_cpf)
        return queryset
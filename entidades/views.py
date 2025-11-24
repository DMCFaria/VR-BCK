from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Condominio, Funcionario
from .serializers import CondominioSerializer, FuncionarioSerializer

class CondominioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, criar, atualizar e deletar Condomínios.
    Rotas: /api/entities/condominios/
    """
    queryset = Condominio.objects.all()
    serializer_class = CondominioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cnpj' # Define o campo CNPJ como lookup para URLs


class FuncionarioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, criar, atualizar e deletar Funcionários.
    Rotas: /api/entities/funcionarios/
    """
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cpf' # Define o campo CPF como lookup para URLs
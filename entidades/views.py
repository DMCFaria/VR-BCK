from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente
from .serializers import (
    CondominioSerializer,
    FuncionarioSerializer,
    AdministradoraSerializer,
    VinculoCondominioSerializer,
    GerenteSerializer
)


class CondominioViewSet(viewsets.ModelViewSet):
    queryset = Condominio.objects.all()
    serializer_class = CondominioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cnpj'


class FuncionarioViewSet(viewsets.ModelViewSet):
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cpf'


class AdministradoraViewSet(viewsets.ModelViewSet):
    queryset = Administradora.objects.all()
    serializer_class = AdministradoraSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo is not None:
            queryset = queryset.filter(ativo=ativo.lower() == 'true')
        return queryset

    @action(detail=True, methods=['get'])
    def condominios(self, request, pk=None):
        administradora = self.get_object()
        vinculos = VinculoCondominio.objects.filter(administradora=administradora)
        serializer = VinculoCondominioSerializer(vinculos, many=True)
        return Response(serializer.data)


class GerenteViewSet(viewsets.ModelViewSet):
    queryset = Gerente.objects.all()
    serializer_class = GerenteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo is not None:
            queryset = queryset.filter(ativo=ativo.lower() == 'true')
        return queryset


class VinculoCondominioViewSet(viewsets.ModelViewSet):
    queryset = VinculoCondominio.objects.all()
    serializer_class = VinculoCondominioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        admin_id = self.request.query_params.get('administradora')
        condominio_cnpj = self.request.query_params.get('condominio')
        gerente_id = self.request.query_params.get('gerente')
        if admin_id:
            queryset = queryset.filter(administradora_id=admin_id)
        if condominio_cnpj:
            queryset = queryset.filter(condominio_id=condominio_cnpj)
        if gerente_id:
            queryset = queryset.filter(gerentes__id=gerente_id)
        return queryset

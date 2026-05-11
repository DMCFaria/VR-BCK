from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import logging

from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente
from .serializers import (
    CondominioSerializer,
    FuncionarioSerializer,
    AdministradoraSerializer,
    VinculoCondominioSerializer,
    GerenteSerializer
)

logger = logging.getLogger(__name__)

class CondominioViewSet(viewsets.ModelViewSet):
    queryset = Condominio.objects.all()
    serializer_class = CondominioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cnpj'

    def get_queryset(self):
        try:
            queryset = super().get_queryset()
            administradora_id = self.request.query_params.get('administradora')

            logger.info(
                f'[CondominioViewSet] GET queryset | administradora={administradora_id}'
            )

            if administradora_id:
                queryset = queryset.filter(
                    vinculocondominio__administradora_id=administradora_id
                ).distinct()

            logger.info(
                f'[CondominioViewSet] Total encontrados: {queryset.count()}'
            )

            return queryset

        except Exception as e:
            logger.exception(
                f'[CondominioViewSet] Erro no get_queryset: {str(e)}'
            )
            return Condominio.objects.none()

    def create(self, request, *args, **kwargs):
        logger.info(
            f'[CondominioViewSet] Payload recebido: {request.data}'
        )

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            logger.error(
                f'[CondominioViewSet] Erros serializer: {serializer.errors}'
            )

            return Response(
                serializer.errors,
                status=400
            )

        try:
            self.perform_create(serializer)

            logger.info(
                f'[CondominioViewSet] Condomínio criado com sucesso: {serializer.data}'
            )

            return Response(
                serializer.data,
                status=201
            )

        except Exception as e:
            logger.exception(
                f'[CondominioViewSet] Erro ao salvar condomínio: {str(e)}'
            )

            return Response(
                {'erro': str(e)},
                status=500
            )

class FuncionarioViewSet(viewsets.ModelViewSet):
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cpf'

    def create(self, request, *args, **kwargs):
        logger.info(f'[FuncionarioViewSet][CREATE] payload={request.data}')

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            logger.error(
                f'[FuncionarioViewSet][CREATE] errors={serializer.errors}'
            )
            return Response(serializer.errors, status=400)

        self.perform_create(serializer)

        logger.info(
            f'[FuncionarioViewSet][CREATE] salvo={serializer.data}'
        )

        return Response(serializer.data, status=201)

    def update(self, request, *args, **kwargs):
        logger.info(f'[FuncionarioViewSet][UPDATE] payload={request.data}')

        partial = kwargs.pop('partial', False)

        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )

        if not serializer.is_valid():
            logger.error(
                f'[FuncionarioViewSet][UPDATE] errors={serializer.errors}'
            )
            return Response(serializer.errors, status=400)

        self.perform_update(serializer)

        logger.info(
            f'[FuncionarioViewSet][UPDATE] salvo={serializer.data}'
        )

        return Response(serializer.data)

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
            queryset = queryset.filter(condominio__cnpj=condominio_cnpj)
        if gerente_id:
            queryset = queryset.filter(gerentes__id=gerente_id)
        return queryset

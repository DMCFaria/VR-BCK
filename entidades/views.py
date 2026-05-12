import json
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
        logger.info(f'[AdministradoraViewSet][LIST] Iniciando consulta')
        
        queryset = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        
        logger.info(f'[AdministradoraViewSet][LIST] Filtro ativo: {ativo}')
        
        if ativo is not None:
            ativo_bool = ativo.lower() == 'true'
            logger.info(f'[AdministradoraViewSet][LIST] Aplicando filtro ativo={ativo_bool}')
            queryset = queryset.filter(ativo=ativo_bool)
        
        logger.info(f'[AdministradoraViewSet][LIST] Total encontrado: {queryset.count()}')
        
        return queryset

    def create(self, request, *args, **kwargs):
        logger.info('='*60)
        logger.info('[AdministradoraViewSet][CREATE] INICIANDO CRIAÇÃO')
        logger.info(f'[AdministradoraViewSet][CREATE] Usuário: {request.user}')
        logger.info(f'[AdministradoraViewSet][CREATE] Payload recebido: {json.dumps(request.data, indent=2, ensure_ascii=False)}')
        
        # Log específico para campos importantes
        logger.info(f'[AdministradoraViewSet][CREATE] CNPJ: {request.data.get("cnpj")}')
        logger.info(f'[AdministradoraViewSet][CREATE] Razão Social: {request.data.get("razao_social")}')
        logger.info(f'[AdministradoraViewSet][CREATE] Ativo: {request.data.get("ativo")} (tipo: {type(request.data.get("ativo"))})')
        logger.info(f'[AdministradoraViewSet][CREATE] cartao_admin: {request.data.get("cartao_admin")} (tipo: {type(request.data.get("cartao_admin"))})')
        
        # Validação manual antes do serializer
        if not request.data.get('cnpj'):
            logger.error('[AdministradoraViewSet][CREATE] CNPJ é obrigatório')
            return Response({'error': 'CNPJ é obrigatório'}, status=400)
        
        if not request.data.get('razao_social'):
            logger.error('[AdministradoraViewSet][CREATE] Razão Social é obrigatória')
            return Response({'error': 'Razão Social é obrigatória'}, status=400)
        
        # Validação do cartao_admin (agora espera boolean)
        cartao_admin_value = request.data.get('cartao_admin')
        if cartao_admin_value is None:
            logger.error('[AdministradoraViewSet][CREATE] cartao_admin é obrigatório')
            return Response({'error': 'Local de recebimento do cartão é obrigatório'}, status=400)
        
        # Converte se veio como string (caso o frontend ainda mande string)
        if isinstance(cartao_admin_value, str):
            if cartao_admin_value.lower() == 'true':
                cartao_admin_value = True
            elif cartao_admin_value.lower() == 'false':
                cartao_admin_value = False
            else:
                logger.error(f"[AdministradoraViewSet][CREATE] cartao_admin inválido: {cartao_admin_value}")
                return Response({'error': 'cartao_admin deve ser true ou false'}, status=400)
            # Atualiza o request com o valor convertido
            request.data._mutable = True
            request.data['cartao_admin'] = cartao_admin_value
            request.data._mutable = False
        
        # Agora valida se é boolean
        if not isinstance(cartao_admin_value, bool):
            logger.error(f"[AdministradoraViewSet][CREATE] cartao_admin deve ser boolean, recebido: {type(cartao_admin_value)}")
            return Response({'error': 'cartao_admin deve ser true (administradora) ou false (condominio)'}, status=400)
        
        serializer = self.get_serializer(data=request.data)
        
        logger.info('[AdministradoraViewSet][CREATE] Validando serializer...')
        
        if not serializer.is_valid():
            logger.error('[AdministradoraViewSet][CREATE] Erros de validação:')
            for field, errors in serializer.errors.items():
                logger.error(f'  - {field}: {errors}')
            
            return Response({
                'error': 'Erro de validação',
                'details': serializer.errors
            }, status=400)
        
        logger.info('[AdministradoraViewSet][CREATE] Dados validados com sucesso')
        logger.info(f'[AdministradoraViewSet][CREATE] Dados limpos: {json.dumps(serializer.validated_data, indent=2, ensure_ascii=False, default=str)}')
        
        try:
            logger.info('[AdministradoraViewSet][CREATE] Tentando salvar no banco de dados...')
            
            self.perform_create(serializer)
            
            logger.info(f'[AdministradoraViewSet][CREATE] ✅ Administradora criada com ID: {serializer.instance.id}')
            logger.info(f'[AdministradoraViewSet][CREATE] cartao_admin salvo como: {serializer.instance.cartao_admin} ({"Administradora" if serializer.instance.cartao_admin else "Condomínio"})')
            logger.info(f'[AdministradoraViewSet][CREATE] Dados salvos: {json.dumps(serializer.data, indent=2, ensure_ascii=False)}')
            logger.info('='*60)
            
            return Response(serializer.data, status=201)
            
        except Exception as e:
            logger.exception(f'[AdministradoraViewSet][CREATE] ❌ Erro ao salvar: {str(e)}')
            logger.error('='*60)
            
            return Response({
                'error': 'Erro interno ao salvar administradora',
                'details': str(e)
            }, status=500)

    def update(self, request, *args, **kwargs):
        logger.info(f'[AdministradoraViewSet][UPDATE] ID: {kwargs.get("pk")}')
        logger.info(f'[AdministradoraViewSet][UPDATE] Payload: {request.data}')
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info(f'[AdministradoraViewSet][UPDATE] Instância atual: {instance}')
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            logger.error(f'[AdministradoraViewSet][UPDATE] Erros: {serializer.errors}')
            return Response(serializer.errors, status=400)
        
        try:
            self.perform_update(serializer)
            logger.info(f'[AdministradoraViewSet][UPDATE] ✅ Atualizado com sucesso')
            return Response(serializer.data)
        except Exception as e:
            logger.exception(f'[AdministradoraViewSet][UPDATE] ❌ Erro: {str(e)}')
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def condominios(self, request, pk=None):
        logger.info(f'[AdministradoraViewSet][CONDOMINIOS] ID: {pk}')
        
        administradora = self.get_object()
        vinculos = VinculoCondominio.objects.filter(administradora=administradora)
        
        logger.info(f'[AdministradoraViewSet][CONDOMINIOS] Encontrados {vinculos.count()} vínculos')
        
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

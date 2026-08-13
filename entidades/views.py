import json
from django.db.models import Prefetch, Q

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission, SAFE_METHODS
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
import logging

from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente, TaxaConfig
from .serializers import (
    CondominioSerializer,
    FuncionarioSerializer,
    AdministradoraSerializer,
    VinculoCondominioSerializer,
    GerenteSerializer,
    TaxaConfigSerializer
)

logger = logging.getLogger(__name__)

class IsDevFatOrAdministradoraOwnerOrReadOnly(BasePermission):
    """
    Permite leitura para qualquer usuário autenticado.
    Escrita (criar, alterar, excluir taxa) é EXCLUSIVA de dev/fat — regra de
    negócio confirmada na demanda do perfil supervisor: nenhum usuário de
    administradora (adm, dep, sup) configura taxa.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'tipo', None) in ('dev', 'fat')

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'tipo', None) in ('dev', 'fat')


class CondominioPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CondominioViewSet(viewsets.ModelViewSet):
    queryset = Condominio.objects.all()
    serializer_class = CondominioSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'cnpj'
    pagination_class = CondominioPagination

    def get_queryset(self):
        try:
            vinculos_prefetch = Prefetch(
                'vinculocondominio_set',
                queryset=VinculoCondominio.objects.select_related('administradora')
            )
            queryset = super().get_queryset().prefetch_related(vinculos_prefetch)

            administradora_id = self.request.user.administradora_ativa_id
            search = self.request.query_params.get('search')
            # mantém compatibilidade com chamadas antigas que usam ?cnpj=
            cnpj = self.request.query_params.get('cnpj')
            nome = self.request.query_params.get('nome')

            if not administradora_id:
                raise ValidationError({"error": "O parâmetro 'administradora' é obrigatório."})

            # Usuários comuns só veem condomínios vinculados à administradora ativa.
            # Usuários fat/dev veem todos.
            if self.request.user.tipo not in ['fat', 'dev']:
                queryset = queryset.filter(
                    vinculocondominio__administradora_id=administradora_id,
                ).distinct()

            if search:
                queryset = queryset.filter(
                    Q(cnpj__icontains=search) | Q(nome__icontains=search)
                )
            else:
                if cnpj:
                    queryset = queryset.filter(cnpj__icontains=cnpj)
                if nome:
                    queryset = queryset.filter(nome__icontains=nome)

            return queryset

        except Exception as e:
            logger.exception(f'[CondominioViewSet] Erro no get_queryset: {str(e)}')
            return Condominio.objects.none()

    def create(self, request, *args, **kwargs):
        # logger.info(
        #     f'[CondominioViewSet] Payload recebido: {request.data}'
        # )

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

            # logger.info(
            #     f'[CondominioViewSet] Condomínio criado com sucesso: {serializer.data}'
            # )

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
        # logger.info(f'[FuncionarioViewSet][CREATE] payload={request.data}')

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            logger.error(
                f'[FuncionarioViewSet][CREATE] errors={serializer.errors}'
            )
            return Response(serializer.errors, status=400)

        self.perform_create(serializer)

        # logger.info(
        #     f'[FuncionarioViewSet][CREATE] salvo={serializer.data}'
        # )

        return Response(serializer.data, status=201)

    def update(self, request, *args, **kwargs):
        # logger.info(f'[FuncionarioViewSet][UPDATE] payload={request.data}')

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

        # logger.info(
        #     f'[FuncionarioViewSet][UPDATE] salvo={serializer.data}'
        # )

        return Response(serializer.data)

class AdministradoraViewSet(viewsets.ModelViewSet):
    queryset = Administradora.objects.all()
    serializer_class = AdministradoraSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        ativo = self.request.query_params.get('ativo')

        if ativo is not None:
            ativo_bool = ativo.lower() == 'true'
            queryset = queryset.filter(ativo=ativo_bool)

        user = self.request.user
        if user.tipo not in ('fat', 'dev'):
            queryset = queryset.filter(usuarios=user)

        return queryset

    def create(self, request, *args, **kwargs):
        # logger.info('='*60)
        # logger.info('[AdministradoraViewSet][CREATE] INICIANDO CRIAÇÃO')
        # logger.info(f'[AdministradoraViewSet][CREATE] Usuário: {request.user}')
        # logger.info(f'[AdministradoraViewSet][CREATE] Payload recebido: {json.dumps(request.data, indent=2, ensure_ascii=False)}')
        
        # Log específico para campos importantes
        # logger.info(f'[AdministradoraViewSet][CREATE] CNPJ: {request.data.get("cnpj")}')
        # logger.info(f'[AdministradoraViewSet][CREATE] Razão Social: {request.data.get("razao_social")}')
        # logger.info(f'[AdministradoraViewSet][CREATE] Ativo: {request.data.get("ativo")} (tipo: {type(request.data.get("ativo"))})')
        # logger.info(f'[AdministradoraViewSet][CREATE] cartao_admin: {request.data.get("cartao_admin")} (tipo: {type(request.data.get("cartao_admin"))})')
        
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
                # logger.error(f"[AdministradoraViewSet][CREATE] cartao_admin inválido: {cartao_admin_value}")
                return Response({'error': 'cartao_admin deve ser true ou false'}, status=400)
            # Atualiza o request com o valor convertido
            request.data._mutable = True
            request.data['cartao_admin'] = cartao_admin_value
            request.data._mutable = False
        
        # Agora valida se é boolean
        if not isinstance(cartao_admin_value, bool):
            # logger.error(f"[AdministradoraViewSet][CREATE] cartao_admin deve ser boolean, recebido: {type(cartao_admin_value)}")
            return Response({'error': 'cartao_admin deve ser true (administradora) ou false (condominio)'}, status=400)
        
        serializer = self.get_serializer(data=request.data)
        
        # logger.info('[AdministradoraViewSet][CREATE] Validando serializer...')
        
        if not serializer.is_valid():
            logger.error('[AdministradoraViewSet][CREATE] Erros de validação:')
            for field, errors in serializer.errors.items():
                logger.error(f'  - {field}: {errors}')
            
            return Response({
                'error': 'Erro de validação',
                'details': serializer.errors
            }, status=400)
        
        # logger.info('[AdministradoraViewSet][CREATE] Dados validados com sucesso')
        # logger.info(f'[AdministradoraViewSet][CREATE] Dados limpos: {json.dumps(serializer.validated_data, indent=2, ensure_ascii=False, default=str)}')
        
        try:
            # logger.info('[AdministradoraViewSet][CREATE] Tentando salvar no banco de dados...')
            
            self.perform_create(serializer)
            
            # logger.info(f'[AdministradoraViewSet][CREATE] ✅ Administradora criada com ID: {serializer.instance.id}')
            # logger.info(f'[AdministradoraViewSet][CREATE] cartao_admin salvo como: {serializer.instance.cartao_admin} ({"Administradora" if serializer.instance.cartao_admin else "Condomínio"})')
            # logger.info(f'[AdministradoraViewSet][CREATE] Dados salvos: {json.dumps(serializer.data, indent=2, ensure_ascii=False)}')
            # logger.info('='*60)
            
            return Response(serializer.data, status=201)
            
        except Exception as e:
            logger.exception(f'[AdministradoraViewSet][CREATE] ❌ Erro ao salvar: {str(e)}')
            logger.error('='*60)
            
            return Response({
                'error': 'Erro interno ao salvar administradora',
                'details': str(e)
            }, status=500)

    def update(self, request, *args, **kwargs):
        # logger.info(f'[AdministradoraViewSet][UPDATE] ID: {kwargs.get("pk")}')
        # logger.info(f'[AdministradoraViewSet][UPDATE] Payload: {request.data}')
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # logger.info(f'[AdministradoraViewSet][UPDATE] Instância atual: {instance}')
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            logger.error(f'[AdministradoraViewSet][UPDATE] Erros: {serializer.errors}')
            return Response(serializer.errors, status=400)
        
        try:
            self.perform_update(serializer)
            # logger.info(f'[AdministradoraViewSet][UPDATE] ✅ Atualizado com sucesso')
            return Response(serializer.data)
        except Exception as e:
            logger.exception(f'[AdministradoraViewSet][UPDATE] ❌ Erro: {str(e)}')
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def condominios(self, request, pk=None):
        # logger.info(f'[AdministradoraViewSet][CONDOMINIOS] ID: {pk}')
        
        administradora = self.get_object()
        vinculos = VinculoCondominio.objects.filter(administradora=administradora)
        
        # logger.info(f'[AdministradoraViewSet][CONDOMINIOS] Encontrados {vinculos.count()} vínculos')
        
        serializer = VinculoCondominioSerializer(vinculos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='regra-valor')
    def buscar_regra_valor(self, request, pk=None):
        """
        GET /api/administradoras/{id}/regra-valor/
        Retorna a regra de valor da administradora (baseada no campo valor_max_beneficio)
        """
        try:
            administradora = self.get_object()
            
            # Converte o campo existente para o formato esperado pelo frontend
            regra_valor = {
                'id': administradora.id,
                'administradora_id': administradora.id,
                'ativo': administradora.valor_max_beneficio is not None and administradora.valor_max_beneficio < 9999.99,
                'valor_limite': float(administradora.valor_max_beneficio) if administradora.valor_max_beneficio != 9999.99 else None,
                'bloquear_acima_limite': administradora.valor_max_beneficio is not None and administradora.valor_max_beneficio < 9999.99,
                'd_mais': administradora.d_mais,
            }
            
            # Se o valor for o default (9999.99), considera como "sem regra"
            if administradora.valor_max_beneficio >= 9999.98:
                regra_valor['ativo'] = False
                regra_valor['valor_limite'] = None
                regra_valor['bloquear_acima_limite'] = False
            
            logger.info(f'[RegraValor] Buscada para admin {pk}: {regra_valor}')
            return Response(regra_valor)
            
        except Exception as e:
            logger.exception(f'[RegraValor] Erro ao buscar: {str(e)}')
            return Response(
                {'error': 'Erro ao buscar regra de valor', 'detail': str(e)},
                status=500
            )
    
    @buscar_regra_valor.mapping.post
    def criar_regra_valor(self, request, pk=None):
        """
        POST /api/administradoras/{id}/regra-valor/
        Cria/atualiza a regra de valor da administradora
        """
        try:
            administradora = self.get_object()
            
            # Valida o payload
            ativo = request.data.get('ativo', False)
            valor_limite = request.data.get('valor_limite')
            d_mais = request.data.get('d_mais')
            
            # Validações
            if ativo:
                if valor_limite is None:
                    return Response(
                        {'error': 'Valor limite é obrigatório quando a regra está ativa'},
                        status=400
                    )
                
                try:
                    valor_limite = float(valor_limite)
                    if valor_limite <= 0:
                        return Response(
                            {'error': 'Valor limite deve ser maior que zero'},
                            status=400
                        )
                except (TypeError, ValueError):
                    return Response(
                        {'error': 'Valor limite inválido'},
                        status=400
                    )
            else:
                # Se inativo, reseta para o valor padrão (sem bloqueio)
                valor_limite = 9999.99
            
            if d_mais is not None:
                try:
                    d_mais = int(d_mais)
                    if d_mais < 0 or d_mais > 99:
                        return Response(
                            {'error': 'D+ deve estar entre 0 e 99'},
                            status=400
                        )
                except (TypeError, ValueError):
                    return Response(
                        {'error': 'D+ inválido'},
                        status=400
                    )
            
            # Atualiza os campos na administradora
            administradora.valor_max_beneficio = valor_limite
            if d_mais is not None:
                administradora.d_mais = d_mais
            update_fields = ['valor_max_beneficio', 'updated_at']
            if d_mais is not None:
                update_fields.append('d_mais')
            administradora.save(update_fields=update_fields)
            
            # Prepara resposta no formato esperado
            response_data = {
                'id': administradora.id,
                'administradora_id': administradora.id,
                'ativo': ativo,
                'valor_limite': float(valor_limite) if ativo and valor_limite != 9999.99 else None,
                'bloquear_acima_limite': ativo,
                'd_mais': administradora.d_mais,
            }
            
            logger.info(f'[RegraValor] Criada/Atualizada para admin {pk}: {response_data}')
            return Response(response_data, status=200 if administradora.id else 201)
            
        except Exception as e:
            logger.exception(f'[RegraValor] Erro ao criar/atualizar: {str(e)}')
            return Response(
                {'error': 'Erro ao salvar regra de valor', 'detail': str(e)},
                status=500
            )
    
    @action(detail=True, methods=['put'], url_path='regra-valor/(?P<regra_id>[^/.]+)')
    def atualizar_regra_valor(self, request, pk=None, regra_id=None):
        """
        PUT /api/administradoras/{id}/regra-valor/{regra_id}/
        Atualiza a regra de valor (mesma lógica do POST, mas com ID explícito)
        """
        try:
            administradora = self.get_object()
            
            # Verifica se o ID da regra corresponde à administradora
            if int(regra_id) != administradora.id:
                return Response(
                    {'error': 'Regra não encontrada para esta administradora'},
                    status=404
                )
            
            # Reutiliza a mesma lógica do POST
            ativo = request.data.get('ativo', False)
            valor_limite = request.data.get('valor_limite')
            d_mais = request.data.get('d_mais')
            
            if ativo:
                if valor_limite is None:
                    return Response(
                        {'error': 'Valor limite é obrigatório quando a regra está ativa'},
                        status=400
                    )
                
                try:
                    valor_limite = float(valor_limite)
                    if valor_limite <= 0:
                        return Response(
                            {'error': 'Valor limite deve ser maior que zero'},
                            status=400
                        )
                except (TypeError, ValueError):
                    return Response(
                        {'error': 'Valor limite inválido'},
                        status=400
                    )
            else:
                valor_limite = 9999.99
            
            if d_mais is not None:
                try:
                    d_mais = int(d_mais)
                    if d_mais < 0 or d_mais > 99:
                        return Response(
                            {'error': 'D+ deve estar entre 0 e 99'},
                            status=400
                        )
                except (TypeError, ValueError):
                    return Response(
                        {'error': 'D+ inválido'},
                        status=400
                    )
            
            administradora.valor_max_beneficio = valor_limite
            if d_mais is not None:
                administradora.d_mais = d_mais
            update_fields = ['valor_max_beneficio', 'updated_at']
            if d_mais is not None:
                update_fields.append('d_mais')
            administradora.save(update_fields=update_fields)
            
            response_data = {
                'id': administradora.id,
                'administradora_id': administradora.id,
                'ativo': ativo,
                'valor_limite': float(valor_limite) if ativo and valor_limite != 9999.99 else None,
                'bloquear_acima_limite': ativo,
                'd_mais': administradora.d_mais,
            }
            
            logger.info(f'[RegraValor] Atualizada via PUT para admin {pk}: {response_data}')
            return Response(response_data)
            
        except Exception as e:
            logger.exception(f'[RegraValor] Erro ao atualizar via PUT: {str(e)}')
            return Response(
                {'error': 'Erro ao atualizar regra de valor', 'detail': str(e)},
                status=500
            )

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


class TaxaConfigViewSet(viewsets.ModelViewSet):
    queryset = TaxaConfig.objects.select_related('vinculo', 'produto').all()
    serializer_class = TaxaConfigSerializer
    permission_classes = [IsAuthenticated, IsDevFatOrAdministradoraOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        vinculo_id = self.request.query_params.get('vinculo')
        administradora_id = self.request.query_params.get('administradora')
        condominio_cnpj = self.request.query_params.get('condominio')
        produto_codigo = self.request.query_params.get('produto')
        tipo = self.request.query_params.get('tipo')
        ativo = self.request.query_params.get('ativo')

        if vinculo_id:
            queryset = queryset.filter(vinculo_id=vinculo_id)
        if administradora_id:
            queryset = queryset.filter(vinculo__administradora_id=administradora_id)
        if condominio_cnpj:
            queryset = queryset.filter(vinculo__condominio__cnpj=condominio_cnpj)
        if produto_codigo:
            queryset = queryset.filter(produto__codigo_produto=produto_codigo)
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if ativo is not None:
            queryset = queryset.filter(ativo=ativo.lower() == 'true')

        return queryset

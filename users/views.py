# users/views.py
from django.db.models import Q
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.fedhub.services.fedhub_service import FedhubService
from .models import CustomUser
from .serializers import CustomUserSerializer, UserRegistrationSerializer
from .permissions import PodeGerenciarUsuarios, TIPOS_GERENCIAVEIS_PELO_SUP
from entidades.models import Administradora
import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated

from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

class UserRegistrationAPIView(generics.CreateAPIView):
    """
    Permite o registro de um novo usuário.
    Aceita administradoras (lista de IDs) via payload.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated, PodeGerenciarUsuarios]

    def create(self, request, *args, **kwargs):
        logger.info(f"Recebendo criacao de usuario. Payload: {request.data}")

        administradoras_ids = request.data.get('administradoras', [])

        # Supervisor: só cria usuário na própria administradora. Se o payload
        # não trouxer vínculo, assume a administradora ativa do supervisor.
        if getattr(request.user, 'tipo', None) == 'sup':
            proprias = set(request.user.administradoras.values_list('id', flat=True))
            if not administradoras_ids:
                if not request.user.administradora_ativa_id:
                    return Response(
                        {"detail": "Supervisor sem administradora ativa."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                administradoras_ids = [request.user.administradora_ativa_id]
            elif not {int(i) for i in administradoras_ids}.issubset(proprias):
                return Response(
                    {"detail": "Supervisor só pode vincular usuários à própria administradora."},
                    status=status.HTTP_403_FORBIDDEN
                )

        administradoras = []
        for admin_id in administradoras_ids:
            try:
                administradoras.append(Administradora.objects.get(id=admin_id))
            except Administradora.DoesNotExist:
                return Response(
                    {"detail": f"Administradora com ID {admin_id} nao encontrada"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        temporary_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user = serializer.save(
            password=temporary_password,
            primeiro_acesso=True
        )

        if administradoras:
            user.administradoras.set(administradoras)
            user.administradora_ativa = administradoras[0]
            user.save(update_fields=['administradora_ativa'])

        logger.info(f"Usuario criado: {user.email} - Administradoras: {[a.razao_social for a in administradoras]}")

        try:
            fedhub_service = FedhubService()
            admin_nome = administradoras[0].razao_social if administradoras else None
            email_enviado = fedhub_service.enviar_email_usuario_criado(
                email=user.email,
                user=user,
                senha_temporaria=temporary_password,
                dados_usuario={
                    'nome': user.nome,
                    'tipo': user.tipo,
                    'administradora': admin_nome
                }
            )
        except Exception as e:
            logger.error(f"Erro ao enviar email de boas-vindas: {str(e)}")
            email_enviado = False

        headers = self.get_success_headers(serializer.data)
        response_data = serializer.data
        response_data['email_enviado'] = email_enviado
        response_data['primeiro_acesso'] = True

        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    Retorna os dados do usuário logado e permite a atualização.
    """
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class LoginApiView(TokenObtainPairView):
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return response

class CustomTokenRefreshView(TokenRefreshView):
    """
    Endpoint para renovar o access token a partir de um refresh token válido.
    """
    def post(self, request, *args, **kwargs):
        logger.info("🔄 Solicitação de refresh token recebida.")
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            logger.info("✅ Access token renovado com sucesso.")
        else:
            logger.warning(f"⚠️ Falha ao renovar o access token. Status: {response.status_code}")
        return response

class UserListView(generics.ListAPIView):
    """
    Lista todos os usuários com opção de filtrar por administradora.
    """
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CustomUser.objects.all()

        # Perfis de administradora só enxergam usuários das próprias
        # administradoras (dev/fat continuam vendo tudo).
        if getattr(self.request.user, 'tipo', None) not in ('dev', 'fat'):
            queryset = queryset.filter(
                administradoras__in=self.request.user.administradoras.all()
            ).distinct()

        administradora_id = self.request.query_params.get('administradora')
        if administradora_id:
            try:
                queryset = queryset.filter(administradoras__id=int(administradora_id))
            except ValueError:
                pass

        tipo = self.request.query_params.get('tipo')
        if tipo and tipo not in ['fat', 'dev']:
            queryset = queryset.filter(tipo=tipo)

        # A tela de usuários envia ?search= com o texto do campo de busca.
        # O parâmetro era ignorado aqui: a lista voltava inteira e o filtro
        # parecia não funcionar.
        #
        # Busca nos três campos que a tabela exibe (UsuarioTable.jsx mostra
        # `username || nome` numa coluna e `email` na outra), senão o usuário
        # digita o que está vendo na tela e não encontra nada.
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search)
                | Q(username__icontains=search)
                | Q(email__icontains=search)
            )

        return queryset

class UserDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """
    Recupera, atualiza ou deleta um usuário específico via ID (pk).
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated, PodeGerenciarUsuarios]
    http_method_names = ['get', 'put', 'patch', 'delete'] 

    def update(self, request, *args, **kwargs):
        logger.info(f"✏️ Atualizando usuário ID {kwargs.get('pk')}. Payload: {request.data}")
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Permite atualização parcial dos campos"""
        logger.info(f"📝 Atualização parcial usuário ID {kwargs.get('pk')}. Payload: {request.data}")
        return super().partial_update(request, *args, **kwargs)
    
    def perform_update(self, serializer):
        serializer.save()

def _bloqueio_vinculo_para_sup(request, user_alvo, administradora_id):
    """
    Guarda das views de vínculo para o supervisor: só usuários adm/dep e só
    a própria administradora; operações em massa (sem administradora_id)
    são exclusivas de dev/fat. Retorna Response de erro ou None.
    """
    if getattr(request.user, 'tipo', None) != 'sup':
        return None
    if user_alvo.tipo not in TIPOS_GERENCIAVEIS_PELO_SUP:
        return Response(
            {"detail": "Supervisor só pode gerenciar usuários adm e dep."},
            status=status.HTTP_403_FORBIDDEN
        )
    if not administradora_id:
        return Response(
            {"detail": "Informe a administradora (operação em massa é exclusiva da Fedcorp)."},
            status=status.HTTP_403_FORBIDDEN
        )
    proprias = set(request.user.administradoras.values_list('id', flat=True))
    if int(administradora_id) not in proprias:
        return Response(
            {"detail": "Supervisor só pode operar vínculos da própria administradora."},
            status=status.HTTP_403_FORBIDDEN
        )
    return None


class VincularAdministradoraView(APIView):
    """
    Endpoint para vincular/desvincular um usuario a uma administradora (M2M).
    POST com administradora_id = vincula (adiciona a M2M).
    POST sem administradora_id = desvincula todas.
    """
    permission_classes = [permissions.IsAuthenticated, PodeGerenciarUsuarios]

    def post(self, request, pk):
        try:
            user = CustomUser.objects.get(pk=pk)
            administradora_id = request.data.get('administradora_id')

            bloqueio = _bloqueio_vinculo_para_sup(request, user, administradora_id)
            if bloqueio:
                return bloqueio

            if administradora_id:
                try:
                    administradora = Administradora.objects.get(id=administradora_id)
                    user.administradoras.add(administradora)
                    if not user.administradora_ativa:
                        user.administradora_ativa = administradora
                        user.save(update_fields=['administradora_ativa'])
                    message = f"Usuario {user.email} vinculado a administradora {administradora.razao_social}"
                except Administradora.DoesNotExist:
                    return Response(
                        {"error": "Administradora nao encontrada."},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                user.administradoras.clear()
                user.administradora_ativa = None
                user.save(update_fields=['administradora_ativa'])
                message = f"Usuario {user.email} desvinculado de todas as administradoras"

            logger.info(message)
            return Response(
                {"message": message, "administradora_id": administradora_id},
                status=status.HTTP_200_OK
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario nao encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
                  
class DesvincularAdministradoraView(APIView):
    """
    Remove o vinculo de um usuario com uma administradora especifica (ou todas).
    POST com administradora_id = remove daquela administradora.
    POST sem administradora_id = remove de todas.
    """
    permission_classes = [permissions.IsAuthenticated, PodeGerenciarUsuarios]

    def post(self, request, pk):
        try:
            user = CustomUser.objects.get(pk=pk)
            administradora_id = request.data.get('administradora_id')

            bloqueio = _bloqueio_vinculo_para_sup(request, user, administradora_id)
            if bloqueio:
                return bloqueio

            if administradora_id:
                try:
                    administradora = Administradora.objects.get(id=administradora_id)
                    user.administradoras.remove(administradora)
                    if user.administradora_ativa_id == administradora.id:
                        user.administradora_ativa = user.administradoras.first()
                        user.save(update_fields=['administradora_ativa'])
                    message = f"Usuario {user.email} desvinculado da administradora {administradora.razao_social}"
                except Administradora.DoesNotExist:
                    return Response(
                        {"error": "Administradora nao encontrada."},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                user.administradoras.clear()
                user.administradora_ativa = None
                user.save(update_fields=['administradora_ativa'])
                message = f"Usuario {user.email} desvinculado de todas as administradoras"

            logger.info(message)
            return Response(
                {"message": message},
                status=status.HTTP_200_OK
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario nao encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
            
class SetAdministradoraAtivaView(APIView):
    """
    Define qual administradora esta ativa para o usuario logado.
    POST { administradora_id: int }
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        administradora_id = request.data.get('administradora_id')

        if not administradora_id:
            return Response(
                {"detail": "administradora_id e obrigatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.administradoras.filter(id=administradora_id).exists():
            return Response(
                {"detail": "Voce nao possui acesso a esta administradora."},
                status=status.HTTP_403_FORBIDDEN
            )

        user.administradora_ativa_id = administradora_id
        user.save(update_fields=['administradora_ativa_id'])

        admin = user.administradoras.get(id=administradora_id)
        return Response({
            "message": f"Administradora ativa alterada para {admin.razao_social}",
            "administradora_ativa": {
                "id": admin.id,
                "razao_social": admin.razao_social,
                "nome_fantasia": admin.nome_fantasia,
            }
        }, status=status.HTTP_200_OK)


class PasswordView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        
        # Se NÃO for primeiro acesso, verifica a senha antiga
        if not user.primeiro_acesso:
            if not old_password or not user.check_password(old_password):
                return Response(
                    {"detail": "Senha antiga incorreta."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        # Valida a nova senha
        if not new_password:
            return Response(
                {"detail": "Nova senha é obrigatória."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if len(new_password) < 6:
            return Response(
                {"detail": "A senha deve ter no mínimo 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Altera a senha e marca primeiro_acesso como False
        user.set_password(new_password)
        user.primeiro_acesso = False
        user.save()
        
        return Response(
            {"detail": "Senha alterada com sucesso."}, 
            status=status.HTTP_200_OK
        )

class SolicitarResetSenhaView(APIView):
    """
    View para solicitar reset de senha.
    Gera um token e envia email com link para redefinição.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get("email")
        
        logger.info(f"Solicitação de reset de senha para email: {email}")
        
        if not email:
            return Response(
                {"detail": "E-mail é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = CustomUser.objects.get(email=email)
            logger.info(f"Usuário encontrado: {user.email}")
        except CustomUser.DoesNotExist:
            logger.warning(f"Usuário não encontrado para o email: {email}")
            # Por segurança, retorna mensagem genérica
            return Response(
                {"detail": "Se o e-mail estiver cadastrado, você receberá as instruções."},
                status=status.HTTP_200_OK
            )
        
        # Gerar token único
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(64))
        
        # Salvar token no usuário
        user.reset_password_token = token
        user.reset_password_token_created_at = timezone.now()
        user.reset_password_token_expires_at = timezone.now() + timezone.timedelta(hours=24)
        user.save(update_fields=[
            'reset_password_token',
            'reset_password_token_created_at',
            'reset_password_token_expires_at'
        ])
        
        # Enviar email via Gateway
        try:
            service = FedhubService()
            
            email_enviado = service.enviar_email_recuperacao_senha(
                email=user.email,
                user=user
            )
            
            if email_enviado:
                logger.info(f"E-mail de recuperação enviado com sucesso para: {user.email}")
            else:
                logger.error(f"Falha ao enviar e-mail de recuperação para: {user.email}")
                
            return Response(
                {
                    "status": "success",
                    "message": "Em breve você receberá um e-mail com as instruções para resetar sua senha. Cheque sua caixa de entrada e também a caixa de spam.",
                    "email_enviado": email_enviado
                },
                status=status.HTTP_200_OK
            )
                    
        except Exception as e:
            logger.error(f"Erro ao chamar Gateway: {str(e)}")
            return Response(
                {
                    "status": "error",
                    "message": "Falha ao processar a solicitação. Tente novamente mais tarde."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ValidarTokenResetView(APIView):
    """
    View para validar se o token de reset é válido.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        """Valida se o token de reset é válido (busca pelo token diretamente)"""
        logger.info(f"Validando token de reset: {token[:20]}...")
        
        # Buscar usuário pelo token
        try:
            user = CustomUser.objects.get(reset_password_token=token)
        except CustomUser.DoesNotExist:
            logger.warning(f"Token não encontrado: {token[:20]}...")
            return Response(
                {"valid": False, "detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se o token não expirou
        if not user.reset_password_token_expires_at:
            logger.warning(f"Token sem data de expiração para usuário: {user.email}")
            return Response(
                {"valid": False, "detail": "Link inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.reset_password_token_expires_at < timezone.now():
            logger.warning(f"Token expirado para usuário: {user.email}")
            return Response(
                {"valid": False, "detail": "Link expirado. Solicite um novo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Token válido para usuário: {user.email}")
        return Response(
            {"valid": True, "detail": "Token válido.", "user_id": user.id},
            status=status.HTTP_200_OK
        )

class ResetarSenhaView(APIView):
    """
    View para redefinir a senha usando o token.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get("token")
        nova_senha = request.data.get("nova_senha")
        
        logger.info(f"Solicitação de reset de senha para token: {token[:20] if token else 'None'}...")
        
        if not token or not nova_senha:
            return Response(
                {"detail": "Dados incompletos."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(nova_senha) < 6:
            return Response(
                {"detail": "A senha deve ter no mínimo 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar usuário pelo token
        try:
            user = CustomUser.objects.get(reset_password_token=token)
        except CustomUser.DoesNotExist:
            logger.warning(f"Token não encontrado: {token[:20]}...")
            return Response(
                {"detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar expiração
        if not user.reset_password_token_expires_at:
            logger.warning(f"Token sem data de expiração para usuário: {user.email}")
            return Response(
                {"detail": "Link inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.reset_password_token_expires_at < timezone.now():
            logger.warning(f"Token expirado para usuário: {user.email}")
            return Response(
                {"detail": "Link expirado. Solicite um novo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Redefinir a senha
        user.set_password(nova_senha)
        user.last_password_reset = timezone.now()
        user.password_reset_count += 1
        user.primeiro_acesso = False  # Marca que não é mais primeiro acesso
        
        # Limpar o token após uso (IMPORTANTE: não pode reusar)
        user.reset_password_token = None
        user.reset_password_token_created_at = None
        user.reset_password_token_expires_at = None
        user.save(update_fields=[
            'reset_password_token',
            'reset_password_token_created_at',
            'reset_password_token_expires_at',
            'password',
            'last_password_reset',
            'password_reset_count',
            'primeiro_acesso'
        ])
        
        logger.info(f"Senha redefinida com sucesso para usuário: {user.email}")
        
        return Response(
            {"detail": "Senha redefinida com sucesso."},
            status=status.HTTP_200_OK
        )
        
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        credential = request.data.get("credential")

        if not credential:
            return Response(
                {"detail": "Credential não enviada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # valida token google
            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                "765602112412-336nt6annegl11j5s3ffm5lie68a975q.apps.googleusercontent.com"
            )

            email = idinfo.get("email")
            nome = idinfo.get("name")

            if not email:
                return Response(
                    {"detail": "Email não encontrado."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # O Google só AUTENTICA usuários já cadastrados pela Fedcorp.
            # A auto-criação anterior (get_or_create) permitia que qualquer
            # conta Google do mundo virasse usuário 'adm' — cadeia de
            # escalação registrada na revisão da demanda do perfil supervisor.
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                logger.warning(f"Login Google recusado para conta não cadastrada: {email}")
                return Response(
                    {"detail": "Conta não cadastrada no portal. Solicite acesso à Fedcorp."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if nome and not user.nome:
                user.nome = nome
                user.save(update_fields=["nome"])

            # gera jwt
            refresh = RefreshToken.for_user(user)

            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            })

        except ValueError:
            return Response(
                {"detail": "Token Google inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
                      

        
class ReenviarEmailBoasVindasSelfView(APIView):
    """
    Permite que o próprio usuário solicite o reenvio do email de boas-vindas.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"detail": "E-mail é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Verificar se o usuário já está ativo (já fez login)
            # if not user.primeiro_acesso:
            #     return Response({
            #         "status": "warning",
            #         "message": "Este usuário já acessou o sistema. Use a opção 'Esqueci minha senha' para redefinir a senha."
            #     }, status=status.HTTP_200_OK)
            
        except CustomUser.DoesNotExist:
            # Não revelar se o usuário existe ou não (segurança)
            logger.info(f"Tentativa de reenvio para email não cadastrado: {email}")
            return Response({
                "status": "success",
                "message": "Se este e-mail estiver cadastrado, você receberá as instruções em breve."
            }, status=status.HTTP_200_OK)
        
        # Enviar email (mesmo código do método anterior)
        try:
            fedhub_service = FedhubService()
            
            # Gerar nova senha temporária
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            temporary_password = ''.join(secrets.choice(alphabet) for _ in range(12))
            user.set_password(temporary_password)
            user.primeiro_acesso = True
            user.save()
            
            administradora_nome = user.administradora_ativa.razao_social if user.administradora_ativa else None
            
            email_enviado = fedhub_service.enviar_email_usuario_criado(
                email=user.email,
                user=user,
                senha_temporaria=temporary_password,
                dados_usuario={
                    'nome': user.nome,
                    'tipo': user.tipo,
                    'administradora': administradora_nome
                }
            )
            
            if email_enviado:
                logger.info(f"📧 Email reenviado para: {user.email}")
                return Response({
                    "status": "success",
                    "message": "Email reenviado com sucesso! Verifique sua caixa de entrada e spam."
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": "error",
                    "detail": "Falha ao enviar email. Tente novamente mais tarde."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"❌ Erro ao reenviar email: {str(e)}")
            return Response({
                "status": "error",
                "detail": f"Erro ao reenviar email: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

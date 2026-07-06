# users/views.py
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.fedhub.services.fedhub_service import FedhubService
from .models import CustomUser
from .serializers import CustomUserSerializer, UserRegistrationSerializer
from .permissions import IsAdminUserType
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
    Agora aceita administradora via payload corretamente.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]

    def create(self, request, *args, **kwargs):
        logger.info(f"📝 Recebendo criação de usuário. Payload: {request.data}")
        
        # Garantir que a administradora seja tratada corretamente
        administradora_id = request.data.get('administradora')
        
        if administradora_id:
            try:
                administradora = Administradora.objects.get(id=administradora_id)
                logger.info(f"✅ Administradora encontrada: {administradora.razao_social} (ID: {administradora_id})")
            except Administradora.DoesNotExist:
                logger.warning(f"⚠️ Administradora ID {administradora_id} não encontrada")
                return Response(
                    {"detail": f"Administradora com ID {administradora_id} não encontrada"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            administradora = None
            logger.info("ℹ️ Nenhuma administradora informada")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 🔐 Gerar senha temporária aleatória
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        temporary_password = "ADCsvmndovgr01fsd" if not request.data.get('password') else request.data.get('password')
        
        # Salvar com a administradora específica e senha temporária
        user = serializer.save(
            administradora=administradora,
            password=temporary_password,  # Define a senha temporária
            primeiro_acesso=True  # Marca como primeiro acesso
        )
        
        logger.info(f"✅ Usuário criado: {user.email} - Administradora: {administradora.razao_social if administradora else 'Nenhuma'}")
        
        # 📧 Enviar email de boas-vindas com as credenciais
        try:
            fedhub_service = FedhubService()
            email_enviado = fedhub_service.enviar_email_usuario_criado(
                email=user.email,
                user=user,
                senha_temporaria=temporary_password,
                dados_usuario={
                    'nome': user.nome,
                    'tipo': user.tipo,
                    'administradora': administradora.razao_social if administradora else None
                }
            )
            
            if email_enviado:
                logger.info(f"📧 Email de boas-vindas enviado para: {user.email}")
            else:
                logger.warning(f"⚠️ Falha ao enviar email de boas-vindas para: {user.email}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email de boas-vindas: {str(e)}")
            # Não interrompe o fluxo - o usuário ainda é criado mesmo se o email falhar
        
        headers = self.get_success_headers(serializer.data)
        
        # Retorna os dados do usuário incluindo info do email
        response_data = serializer.data
        response_data['email_enviado'] = email_enviado if 'email_enviado' in locals() else False
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
        
        
        # Filtro por administradora (via query param)
        administradora_id = self.request.query_params.get('administradora')
        if administradora_id:
            try:
                queryset = queryset.filter(administradora_id=int(administradora_id))
                logger.info(f"Filtrando usuários por administradora ID: {administradora_id}")
            except ValueError:
                pass
        
        # Filtro por tipo de usuário
        tipo = self.request.query_params.get('tipo')
        logger.info(self.request.query_params)
        logger.info(f"Filtrando usuários por tipo: {tipo}")
        if tipo and tipo not in ['fat', 'dev']:
            queryset = queryset.filter(tipo=tipo)
        
        logger.info(f"Total de usuários encontrados: {queryset.count()}")
        return queryset

class UserDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """
    Recupera, atualiza ou deleta um usuário específico via ID (pk).
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]
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

class VincularAdministradoraView(APIView):
    """
    Endpoint específico para vincular/desvincular um usuário a uma administradora.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]

    def post(self, request, pk):
        try:
            user = CustomUser.objects.get(pk=pk)
            administradora_id = request.data.get('administradora_id')
            
            if administradora_id:
                try:
                    administradora = Administradora.objects.get(id=administradora_id)
                    user.administradora = administradora
                    message = f"Usuário {user.email} vinculado à administradora {administradora.razao_social}"
                except Administradora.DoesNotExist:
                    return Response(
                        {"error": "Administradora não encontrada."},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                user.administradora = None
                message = f"Usuário {user.email} desvinculado da administradora"
            
            user.save()
            logger.info(f"✅ {message}")
            return Response(
                {"message": message, "administradora_id": administradora_id},
                status=status.HTTP_200_OK
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
                  
class DesvincularAdministradoraView(APIView):
    """
    Remove o vínculo de um usuário com sua administradora.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]

    def post(self, request, pk):
        try:
            user = CustomUser.objects.get(pk=pk)
            user.administradora = None
            user.save()
            logger.info(f"✅ Usuário {user.email} desvinculado da administradora")
            return Response(
                {"message": f"Usuário {user.email} desvinculado da administradora com sucesso."},
                status=status.HTTP_200_OK
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
            
# users/views.py - Atualize o PasswordView
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

            # cria ou pega usuário
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "nome": nome,
                }
            )

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
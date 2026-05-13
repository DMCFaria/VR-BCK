# users/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import CustomUser
from .serializers import CustomUserSerializer, UserRegistrationSerializer
from .permissions import IsAdminUserType
from entidades.models import Administradora
import logging

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
        
        # Salvar com a administradora específica
        user = serializer.save(administradora=administradora)
        
        logger.info(f"✅ Usuário criado: {user.email} - Administradora: {administradora.razao_social if administradora else 'Nenhuma'}")
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

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

class UserListView(generics.ListAPIView):
    """
    Lista todos os usuários com opção de filtrar por administradora.
    """
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]

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
        if tipo:
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

    def update(self, request, *args, **kwargs):
        logger.info(f"✏️ Atualizando usuário ID {kwargs.get('pk')}. Payload: {request.data}")
        return super().update(request, *args, **kwargs)
    
    def perform_update(self, serializer):
        serializer.save()

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
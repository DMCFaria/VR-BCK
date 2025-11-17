from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView 
from .models import CustomUser
from .serializers import CustomUserSerializer, UserRegistrationSerializer
from .permissions import CreateUserPermission

class UserRegistrationAPIView(generics.CreateAPIView):
    """
    Permite o registro de um novo usuário.
    Permissão: Qualquer um (Permite a criação de novos usuários).
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [CreateUserPermission]


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    Retorna os dados do usuário logado e permite a atualização.
    Permissão: Apenas usuários autenticados.
    """
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """
        Retorna o objeto CustomUser associado à requisição (usuário logado).
        """
        return self.request.user
    
    
class LoginApiView(TokenObtainPairView):
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return response

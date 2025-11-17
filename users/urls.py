from django.urls import path
from .views import UserRegistrationAPIView, CurrentUserView, LoginApiView

urlpatterns = [
    path('login/', LoginApiView.as_view(), name='user-login'),
    # Rota para registro de novos usuários
    path('register/', UserRegistrationAPIView.as_view(), name='user-register'),
    
    # Rota para obter/atualizar dados do usuário logado
    path('me/', CurrentUserView.as_view(), name='current-user'),
    
]
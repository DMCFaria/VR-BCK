from django.urls import path
from .views import (
    DesvincularAdministradoraView,
    GoogleLoginView,
    PasswordView,
    ReenviarEmailBoasVindasSelfView,
    ResetarSenhaView,
    SolicitarResetSenhaView,
    UserRegistrationAPIView, 
    CurrentUserView, 
    LoginApiView, 
    CustomTokenRefreshView,
    UserListView, 
    UserDetailUpdateDeleteView,
    ValidarTokenResetView, 
    VincularAdministradoraView
)

urlpatterns = [
    path('login/', LoginApiView.as_view(), name='user-login'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('register/', UserRegistrationAPIView.as_view(), name='user-register'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path("password/", PasswordView.as_view(), name="user-password"),
    
    # As rotas abaixo parecem estar faltando no seu urls.py:
    path('list/', UserListView.as_view(), name='user_list'),
    path('<int:pk>/', UserDetailUpdateDeleteView.as_view(), name='user_detail'),
    path('<int:pk>/vincular-adm/', VincularAdministradoraView.as_view(), name='vincular-adm'),
    path('<int:pk>/desvincular-adm/', DesvincularAdministradoraView.as_view(), name='desvincular-adm'),
    
    path('reenviar-email-boas-vindas/', ReenviarEmailBoasVindasSelfView.as_view(), name='reenviar-email-boas-vindas'),
    path('solicitar-reset-senha/', SolicitarResetSenhaView.as_view(), name='solicitar-reset-senha'),
    path('validar-token-reset/<str:token>/', ValidarTokenResetView.as_view(), name='validar-token-reset'),
    path('resetar-senha/', ResetarSenhaView.as_view(), name='resetar-senha'),
    
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
]
from django.urls import path
from .views import (
    DesvincularAdministradoraView,
    GoogleLoginView,
    PasswordView,
    UserRegistrationAPIView, 
    CurrentUserView, 
    LoginApiView, 
    UserListView, 
    UserDetailUpdateDeleteView, 
    VincularAdministradoraView
)

urlpatterns = [
    path('login/', LoginApiView.as_view(), name='user-login'),
    path('register/', UserRegistrationAPIView.as_view(), name='user-register'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path("password/", PasswordView.as_view(), name="user-password"),
    
    # As rotas abaixo parecem estar faltando no seu urls.py:
    path('list/', UserListView.as_view(), name='user_list'),
    path('<int:pk>/', UserDetailUpdateDeleteView.as_view(), name='user_detail'),
    path('<int:pk>/vincular-adm/', VincularAdministradoraView.as_view(), name='vincular-adm'),
    path('<int:pk>/desvincular-adm/', DesvincularAdministradoraView.as_view(), name='desvincular-adm'),
    
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
]
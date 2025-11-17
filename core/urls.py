from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView, # Opcional, para verificar a validade do token
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ----------------------------------------------------
    # Rotas de Autenticação JWT (Endpoint para Login/Token)
    # ----------------------------------------------------
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),


    # ----------------------------------------------------
    # Rotas do seu App de Usuários (Registro, Detalhes)
    # ----------------------------------------------------
    path('api/users/', include('users.urls')),
]
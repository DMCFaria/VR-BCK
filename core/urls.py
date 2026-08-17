from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView, # Opcional, para verificar a validade do token
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ----------------------------------------------------
    # Documentação da API (OpenAPI 3 / Swagger)
    # ----------------------------------------------------
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),


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
    path('api/upload/', include('upload.urls')),
    path('api/entidades/', include('entidades.urls')), 
    path('api/beneficios/', include('beneficios.urls')),
    path('api/consultas/', include('consultas.urls'))
]
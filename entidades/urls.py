from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CondominioViewSet,
    FuncionarioViewSet,
    AdministradoraViewSet,
    VinculoCondominioViewSet
)

router = DefaultRouter()
router.register(r'condominios', CondominioViewSet)
router.register(r'funcionarios', FuncionarioViewSet)
router.register(r'administradoras', AdministradoraViewSet)
router.register(r'vinculos', VinculoCondominioViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

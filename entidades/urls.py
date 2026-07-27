from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CondominioViewSet,
    FuncionarioViewSet,
    AdministradoraViewSet,
    VinculoCondominioViewSet,
    GerenteViewSet,
    TaxaConfigViewSet
)

router = DefaultRouter()
router.register(r'condominios', CondominioViewSet)
router.register(r'funcionarios', FuncionarioViewSet)
router.register(r'administradoras', AdministradoraViewSet)
router.register(r'gerentes', GerenteViewSet)
router.register(r'vinculos', VinculoCondominioViewSet)
router.register(r'taxas-config', TaxaConfigViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

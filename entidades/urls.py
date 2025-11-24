from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CondominioViewSet, FuncionarioViewSet

# Cria um router e registra nossos ViewSets
router = DefaultRouter()
router.register(r'condominios', CondominioViewSet)
router.register(r'funcionarios', FuncionarioViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
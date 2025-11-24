from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProdutoViewSet, MovimentacaoBeneficioViewSet

# Cria um router e registra nossos ViewSets
router = DefaultRouter()
router.register(r'produtos', ProdutoViewSet)
router.register(r'movimentacoes', MovimentacaoBeneficioViewSet, basename='movimentacao')

urlpatterns = [
    # Inclui as rotas geradas pelo router (list/create/retrieve/update/delete)
    path('', include(router.urls)),
]
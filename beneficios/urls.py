from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProdutoViewSet,
    MovimentacaoBeneficioViewSet,
    UltimaImportacaoMovimentacoesView,
    ImportacaoListView,
    ImportacaoDetailView
)

router = DefaultRouter()
router.register(r'produtos', ProdutoViewSet)
router.register(r'movimentacoes', MovimentacaoBeneficioViewSet, basename='movimentacao')

urlpatterns = [
    path('', include(router.urls)),
    path('importacoes/ultima/', UltimaImportacaoMovimentacoesView.as_view(), name='ultima-importacao'),
    path('importacoes/', ImportacaoListView.as_view(), name='importacao-list'),
    path('importacoes/<int:pk>/', ImportacaoDetailView.as_view(), name='importacao-detail'),
]
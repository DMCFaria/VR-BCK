from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlterarStatusImportacaoView,
    ProdutoViewSet,
    MovimentacaoBeneficioViewSet,
    UltimaImportacaoMovimentacoesView,
    ImportacaoListView,
    ImportacaoDetailView,
    UltimaMovimentacaoDashboard,
    BoletoBaixaView,
    KanbanFaturasView,
    KanbanBoletosView,
    KanbanMoveFaturaView,
)

router = DefaultRouter()
router.register(r'produtos', ProdutoViewSet)
router.register(r'movimentacoes', MovimentacaoBeneficioViewSet, basename='movimentacao')

urlpatterns = [
    path('', include(router.urls)),
    path('importacoes/ultima/', UltimaImportacaoMovimentacoesView.as_view(), name='ultima-importacao'),
    path('importacoes/', ImportacaoListView.as_view(), name='importacao-list'),
    path('importacoes/<int:pk>/', ImportacaoDetailView.as_view(), name='importacao-detail'),
    path('importacoes/<int:pk>/status/', AlterarStatusImportacaoView.as_view(), name='alterar-status-importacao'),
    
    path('importacoes/ultima-movimentacao/', UltimaMovimentacaoDashboard.as_view(), name='ultima-movimentacao'),
    path('boletos/baixa/', BoletoBaixaView.as_view(), name='boleto-baixa-generica'),
    path('boletos/<int:pk>/baixa/', BoletoBaixaView.as_view(), name='boleto-baixa'),

    path('kanban/faturas/', KanbanFaturasView.as_view(), name='kanban-faturas'),
    path('kanban/boletos/', KanbanBoletosView.as_view(), name='kanban-boletos'),
    path('kanban/<int:pk>/move/', KanbanMoveFaturaView.as_view(), name='kanban-move'),
]
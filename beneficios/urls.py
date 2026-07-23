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
    KanbanNotificarCompraView,
    ImportarBaseCondominiosView,
    ExcluirBaseCondominiosView,
    ConsultarBoletosView,
    PedidoCartaoView,
    PedidoCartaoOperacionalView,
    PedidoCartaoStatusView,
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
    path('kanban/notificar-compra/', KanbanNotificarCompraView.as_view(), name='kanban-notificar-compra'),

    path('importar-base/', ImportarBaseCondominiosView.as_view(), name='importar-base-condominios'),
    path('excluir-base/<int:administradora_id>/', ExcluirBaseCondominiosView.as_view(), name='excluir-base-condominios'),

    path('boletos/', ConsultarBoletosView.as_view(), name='consultar-boletos'),

    path('pedidos-cartao/', PedidoCartaoView.as_view(), name='pedidos-cartao'),
    path('pedidos-cartao/operacional/', PedidoCartaoOperacionalView.as_view(), name='pedidos-cartao-operacional'),
    path('pedidos-cartao/<int:pk>/status/', PedidoCartaoStatusView.as_view(), name='pedidos-cartao-status'),
]
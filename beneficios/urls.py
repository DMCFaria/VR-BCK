from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlterarStatusImportacaoView,
    BoletoBaixaView,
    ConsultarBoletosView,
    ExcluirBaseCondominiosView,
    ImportacaoDetailView,
    ImportacaoListView,
    ImportarBaseCondominiosView,
    KanbanBoletosView,
    KanbanFaturasView,
    KanbanMoveFaturaView,
    KanbanNotificarCompraView,
    ListarBoletosView,
    MarcarResponsavelView,
    MovimentacaoBeneficioViewSet,
    PedidoCartaoOperacionalView,
    PedidoCartaoStatusView,
    PedidoCartaoView,
    ProdutoViewSet,
    UltimaImportacaoMovimentacoesView,
    UltimaMovimentacaoDashboard,
)


router = DefaultRouter()

router.register(
    r'produtos',
    ProdutoViewSet,
)

router.register(
    r'movimentacoes',
    MovimentacaoBeneficioViewSet,
    basename='movimentacao',
)


urlpatterns = [
    path('', include(router.urls)),

    # Importações
    path(
        'importacoes/ultima/',
        UltimaImportacaoMovimentacoesView.as_view(),
        name='ultima-importacao',
    ),
    path(
        'importacoes/',
        ImportacaoListView.as_view(),
        name='importacao-list',
    ),
    path(
        'importacoes/<int:pk>/',
        ImportacaoDetailView.as_view(),
        name='importacao-detail',
    ),
    path(
        'importacoes/<int:pk>/status/',
        AlterarStatusImportacaoView.as_view(),
        name='alterar-status-importacao',
    ),
    path(
        'importacoes/<int:pk>/responsavel/',
        MarcarResponsavelView.as_view(),
        name='marcar-responsavel',
    ),
    path(
        'importacoes/ultima-movimentacao/',
        UltimaMovimentacaoDashboard.as_view(),
        name='ultima-movimentacao',
    ),

    # Boletos
    path(
        'boletos/',
        ListarBoletosView.as_view(),
        name='listar-boletos',
    ),
    path(
        'boletos/baixa/',
        BoletoBaixaView.as_view(),
        name='boleto-baixa-generica',
    ),
    path(
        'boletos/<int:pk>/baixa/',
        BoletoBaixaView.as_view(),
        name='boleto-baixa',
    ),

    # Rota separada para não duplicar "boletos/"
    path(
        'consulta-boletos/',
        ConsultarBoletosView.as_view(),
        name='consultar-boletos',
    ),

    # Kanban
    path(
        'kanban/faturas/',
        KanbanFaturasView.as_view(),
        name='kanban-faturas',
    ),
    path(
        'kanban/boletos/',
        KanbanBoletosView.as_view(),
        name='kanban-boletos',
    ),
    path(
        'kanban/<int:pk>/move/',
        KanbanMoveFaturaView.as_view(),
        name='kanban-move',
    ),
    path(
        'kanban/notificar-compra/',
        KanbanNotificarCompraView.as_view(),
        name='kanban-notificar-compra',
    ),

    # Base de condomínios
    path(
        'importar-base/',
        ImportarBaseCondominiosView.as_view(),
        name='importar-base-condominios',
    ),
    path(
        'excluir-base/<int:administradora_id>/',
        ExcluirBaseCondominiosView.as_view(),
        name='excluir-base-condominios',
    ),

    # Pedidos de cartão
    path(
        'pedidos-cartao/',
        PedidoCartaoView.as_view(),
        name='pedidos-cartao',
    ),
    path(
        'pedidos-cartao/operacional/',
        PedidoCartaoOperacionalView.as_view(),
        name='pedidos-cartao-operacional',
    ),
    path(
        'pedidos-cartao/<int:pk>/status/',
        PedidoCartaoStatusView.as_view(),
        name='pedidos-cartao-status',
    ),
]
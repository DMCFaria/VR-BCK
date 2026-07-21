from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FaturaViewSet,
    FaturaParseView,
    FaturaParseBoletoView,
    FaturaUploadView,
    FaturaPagoTodosView,
    FaturaMoveView,
    FaturaEnviaCPView,
    FaturaGerarBoletoVRView,
    FaturaUploadBoletoVRView,
    CoEstipulantePagoView,
    FaturaCommentsView,
    FaturaBoletoVRPdfView,
    CoEstipulanteBoletoVRPdfView,
    CoEstipulanteBoletoOriginalPdfView,
    BoletoViewSet,
    BoletoUploadView,
    BoletoUploadersView,
    BoletoPagoView,
    BoletoMarkPaidView,
    BoletoDownloadView,
    ReportUploadsPdfView,
)

router = DefaultRouter()
router.register(r'faturas', FaturaViewSet)
router.register(r'boletos', BoletoViewSet)

urlpatterns = [
    path('', include(router.urls)),

    path('faturas/parse/', FaturaParseView.as_view(), name='fatura-parse'),
    path('faturas/parse-boleto/', FaturaParseBoletoView.as_view(), name='fatura-parse-boleto'),
    path('faturas/upload/', FaturaUploadView.as_view(), name='fatura-upload'),
    path('faturas/<int:pk>/pago-todos/', FaturaPagoTodosView.as_view(), name='fatura-pago-todos'),
    path('faturas/<int:pk>/move/', FaturaMoveView.as_view(), name='fatura-move'),
    path('faturas/<int:pk>/enviar-contas-pagar/', FaturaEnviaCPView.as_view(), name='fatura-enviar-cp'),
    path('faturas/<int:pk>/gerar-boleto-vr/', FaturaGerarBoletoVRView.as_view(), name='fatura-gerar-boleto-vr'),
    path('faturas/<int:pk>/upload-boleto-vr/', FaturaUploadBoletoVRView.as_view(), name='fatura-upload-boleto-vr'),
    path('faturas/<int:pk>/coestipulante/<int:idx>/pago/', CoEstipulantePagoView.as_view(), name='coestipulante-pago'),
    path('faturas/<int:pk>/comments/', FaturaCommentsView.as_view(), name='fatura-comments'),
    path('faturas/<int:pk>/boleto-vr-file/pdf/', FaturaBoletoVRPdfView.as_view(), name='fatura-boleto-vr-pdf'),
    path('faturas/<int:pk>/coestipulante/<int:idx>/boleto-vr/pdf/', CoEstipulanteBoletoVRPdfView.as_view(), name='coestipulante-boleto-vr-pdf'),
    path('faturas/<int:pk>/coestipulante/<int:idx>/boleto-original/pdf/', CoEstipulanteBoletoOriginalPdfView.as_view(), name='coestipulante-boleto-original-pdf'),

    path('boletos/upload/', BoletoUploadView.as_view(), name='boleto-upload'),
    path('boletos/uploaders/', BoletoUploadersView.as_view(), name='boleto-uploaders'),
    path('boletos/<int:pk>/pago/', BoletoPagoView.as_view(), name='boleto-pago'),
    path('boletos/<int:pk>/mark-paid/', BoletoMarkPaidView.as_view(), name='boleto-mark-paid'),
    path('boletos/<int:pk>/download/', BoletoDownloadView.as_view(), name='boleto-download'),

    path('reports/uploads.pdf', ReportUploadsPdfView.as_view(), name='report-uploads-pdf'),
]

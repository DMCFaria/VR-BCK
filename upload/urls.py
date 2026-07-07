from django.urls import path

from upload.vt_confirm import ConfirmVTView
from upload.vt_upload import UploadVTView
from .confirmed import ConfirmationView
from .upload import UploadView
from .EXCEL.template import baixar_template_VR, baixar_template_VT
from .export import ExportTxtCompraView, ExportFaturamentoView, ExportVTCompraView, GetImportacaoSelectDataView
from .faturamento import UploadFaturamentoView, StatusFaturamentoView
from .download_views import DownloadArquivoView, DownloadFaturamentoView, DownloadBoletosView, DownloadNotasDebitoView, DownloadNotasFiscaisView, DownloadBoletoOriginalView, DownloadNotaDebitoOriginalView, DownloadNotaFiscalOriginalView, DownloadTodosOriginaisView, DownloadNotasEmitidasView
from .views_nfse import NfseWebhookView


urlpatterns = [
    
    path('', UploadView.as_view(), name='file-upload'),
    path('confirm/', ConfirmationView.as_view(), name='confirm_data'),
    
    path('vt/', UploadVTView.as_view(), name='vt-upload'),
    path('vt/confirm/', ConfirmVTView.as_view(), name='vt-confirm'),
    
    #EXCEL ROUTE
    path('download-excel-vr/', baixar_template_VR, name='download_template'),
    path('download-excel-vt/', baixar_template_VT, name='download_template'),

    # EXPORT ROUTES
    path('export/txt-compra/', ExportTxtCompraView.as_view(), name='export_txt_compra'),
    path('export/faturamento/', ExportFaturamentoView.as_view(), name='export_faturamento'),
    path('export/vt-compra/', ExportVTCompraView.as_view(), name='export_vt_compra'),

    # FATURAMENTO ROUTES
    path('faturamento/upload/', UploadFaturamentoView.as_view(), name='upload_faturamento'),
    path('faturamento/<int:faturamento_id>/status/', StatusFaturamentoView.as_view(), name='faturamento_status'),

    # DOWNLOAD ROUTES
    path('faturamento/<int:faturamento_id>/download/', DownloadFaturamentoView.as_view(), name='download_faturamento_all'),
    path('faturamento/<int:faturamento_id>/download/boletos/', DownloadBoletosView.as_view(), name='download_boletos'),
    path('faturamento/<int:faturamento_id>/download/notas-debito/', DownloadNotasDebitoView.as_view(), name='download_notas_debito'),
    path('faturamento/<int:faturamento_id>/download/notas-fiscais/', DownloadNotasFiscaisView.as_view(), name='download_notas_fiscais'),
    path('faturamento/<int:faturamento_id>/download/boleto-original/', DownloadBoletoOriginalView.as_view(), name='download_boleto_original'),
    path('faturamento/<int:faturamento_id>/download/nota-debito-original/', DownloadNotaDebitoOriginalView.as_view(), name='download_nota_debito_original'),
    path('faturamento/<int:faturamento_id>/download/nota-fiscal-original/', DownloadNotaFiscalOriginalView.as_view(), name='download_nota_fiscal_original'),
    path('faturamento/<int:faturamento_id>/download/originais/', DownloadTodosOriginaisView.as_view(), name='download_originais'),
    path('faturamento/<int:faturamento_id>/download/notas-emitidas/', DownloadNotasEmitidasView.as_view(), name='download_notas_emitidas'),

    path('importacao/<int:importacao_id>/download/', DownloadArquivoView.as_view(), name='download_importacao_arquivo'),
    path('importacao/<int:importacao_id>/select-data/', GetImportacaoSelectDataView.as_view(), name='importacao_select_data'),

    # NFSE ROUTES
    path('nfse/webhook/', NfseWebhookView.as_view(), name='nfse_webhook'),

]
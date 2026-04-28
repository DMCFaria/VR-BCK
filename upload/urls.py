from django.urls import path
from .confirmed import ConfirmationView
from .upload import UploadView
from .EXCEL.template import baixar_template_excel
from .export import ExportTxtCompraView, ExportFaturamentoView
from .faturamento import UploadFaturamentoView, StatusFaturamentoView
from .download_views import DownloadFaturamentoView, DownloadBoletosView, DownloadNotasDebitoView, DownloadNotasFiscaisView


urlpatterns = [
    
    path('', UploadView.as_view(), name='file-upload'),
    path('confirm/', ConfirmationView.as_view(), name='confirm_data'),
    
    #EXCEL ROUTE
    path('download-excel-template/', baixar_template_excel, name='download_template'),
    
    # EXPORT ROUTES
    path('export/txt-compra/', ExportTxtCompraView.as_view(), name='export_txt_compra'),
    path('export/faturamento/', ExportFaturamentoView.as_view(), name='export_faturamento'),

    # FATURAMENTO ROUTES
    path('faturamento/upload/', UploadFaturamentoView.as_view(), name='upload_faturamento'),
    path('faturamento/<int:faturamento_id>/status/', StatusFaturamentoView.as_view(), name='faturamento_status'),

    # DOWNLOAD ROUTES
    path('faturamento/<int:faturamento_id>/download/', DownloadFaturamentoView.as_view(), name='download_faturamento_all'),
    path('faturamento/<int:faturamento_id>/download/boletos/', DownloadBoletosView.as_view(), name='download_boletos'),
    path('faturamento/<int:faturamento_id>/download/notas-debito/', DownloadNotasDebitoView.as_view(), name='download_notas_debito'),
    path('faturamento/<int:faturamento_id>/download/notas-fiscais/', DownloadNotasFiscaisView.as_view(), name='download_notas_fiscais'),
]
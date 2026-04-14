from django.urls import path
from .confirmed import ConfirmedUploadsListView,ConfirmationView
from .upload import UploadView
from .EXCEL.template import baixar_template_excel



urlpatterns = [
    
    path('', UploadView.as_view(), name='file-upload'),
    path('confirm/', ConfirmationView.as_view(), name='confirm_data'),
    path('list-confirmed/', ConfirmedUploadsListView.as_view(), name='get_data'),
    
    #EXCEL ROUTE
    path('download-excel-template/', baixar_template_excel, name='download_template'),
]

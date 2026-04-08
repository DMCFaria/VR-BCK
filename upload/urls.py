from django.urls import path
from .confirmed import ConfirmedUploadsListView,ConfirmationView
from .upload import UploadView



urlpatterns = [
    
    path('', UploadView.as_view(), name='file-upload'),
    path('confirm/', ConfirmationView.as_view(), name='confirm_data'),
    path('list-confirmed/', ConfirmedUploadsListView.as_view(), name='get_data')
]

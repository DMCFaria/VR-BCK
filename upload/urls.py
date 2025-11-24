from django.urls import path
from .views import UploadView, ConfirmationView
from .confirmed import ConfirmedUploadsListView


urlpatterns = [
    
    path('', UploadView.as_view(), name='file-upload'),
    
    
    path('confirm/', ConfirmationView.as_view(), name='confirm_data'),
    path('confirmed/', ConfirmedUploadsListView.as_view(), name='get_data')
]

from django.urls import path
from .views import UploadView

urlpatterns = [
    
    path('', UploadView.as_view(), name='file-upload'),
    
    
   # path('<int:pk>/confirm/', ConfirmUploadView.as_view(), name='file-confirm'),
]
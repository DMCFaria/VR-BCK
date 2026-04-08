from django.urls import path
from .views import UserRegistrationAPIView, CurrentUserView, LoginApiView, UserListView, UserDetailUpdateDeleteView

urlpatterns = [
    path('login/', LoginApiView.as_view(), name='user-login'),
    path('register/', UserRegistrationAPIView.as_view(), name='user-register'),
    path('me/', CurrentUserView.as_view(), name='current-user'),

    # As rotas abaixo parecem estar faltando no seu urls.py:
    path('list/', UserListView.as_view(), name='user_list'),
    path('<int:pk>/', UserDetailUpdateDeleteView.as_view(), name='user_detail')
]
from django.urls import path
from consultas.views import BuscarAdministradoras, BuscarAdministradorasPorCNPJ, BuscarPessoasPorCNPJ, GoogleLoginView

urlpatterns = [
    path('administradoras/', BuscarAdministradoras.as_view(), name='buscar_administradoras'),
    path('administradoras/por-cnpj/<str:cnpj>/', BuscarAdministradorasPorCNPJ.as_view(), name='buscar_administradoras_por_cnpj'),
    
    path('pessoas/por-cnpj/<str:cnpj>/', BuscarPessoasPorCNPJ.as_view(), name='buscar_pessoas_por_cnpj'),
    
    path('recuperar-google-auth/', GoogleLoginView.as_view(), name='recuperar_google_auth'),
]

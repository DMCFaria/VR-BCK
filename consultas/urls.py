from django.urls import path
from consultas.views import BuscarAdministradoras, BuscarAdministradorasPorCNPJ

urlpatterns = [
    path('administradoras/', BuscarAdministradoras.as_view(), name='buscar_administradoras'),
    path('administradoras/por-cnpj/<str:cnpj>/', BuscarAdministradorasPorCNPJ.as_view(), name='buscar_administradoras_por_cnpj'),
]

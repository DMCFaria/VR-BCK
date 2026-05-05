import logging
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.services.fedhub_service import FedhubService

logger = logging.getLogger(__name__)

class BuscarAdministradoras(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs): 
        service = FedhubService()
        dados = service.buscar_administradoras()
        
        # logger.info(f"Dados retornados do serviço de administradoras: {dados}")

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Nenhuma administradora encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })
        
class BuscarAdministradorasPorNome(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, nome: str, *args, **kwargs):
        
        service = FedhubService()
        dados = service.buscar_administradora_por_nome(nome)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Administradora não encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })

class BuscarAdministradorasPorCNPJ(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, cnpj: str, *args, **kwargs):
        service = FedhubService()
        dados = service.buscar_administradora_por_cnpj(cnpj)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Administradora não encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })


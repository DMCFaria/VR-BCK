import logging
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.services.fedhub_service import FedhubService
from users.models import CustomUser

from rest_framework import status

from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework_simplejwt.tokens import RefreshToken

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

class BuscarPessoasPorCNPJ(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, cnpj: str, *args, **kwargs):
        service = FedhubService()
        dados = service.buscar_pessoa_por_cnpj(cnpj)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Nenhuma pessoa encontrada para o CNPJ fornecido"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })
        
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        credential = request.data.get("credential")

        if not credential:
            return Response(
                {"detail": "Credential não enviada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # valida token google
            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                "YOUR_GOOGLE_CLIENT_ID"  # Substitua pelo seu Client ID do Google
            )

            email = idinfo.get("email")
            nome = idinfo.get("nome")

            if not email:
                return Response(
                    {"detail": "Email não encontrado."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # cria ou busca usuário
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    "email": email,
                    "nome": nome,
                }
            )
            
            if not user:
                return Response(
                    {"detail": "Usuário não encontrado. Favor contactar o suporte."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # gera jwt
            refresh = RefreshToken.for_user(user)

            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "email": user.email,
                    "nome": user.nome,
                }
            })

        except ValueError:
            return Response(
                {"detail": "Token Google inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
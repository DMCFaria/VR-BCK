import logging
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import VTCofirmationSerializer

logger = logging.getLogger(__name__)

class ConfirmVTView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data 
        logger.info(f"Recebido payload para confirmação de VT: {payload}")
        
        file_id = payload.get("file_upload_id")

        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        serializer = VTCofirmationSerializer(data=payload)
        
        if serializer.is_valid():
            # Para VT, apenas retornamos os dados validados
            # Não processamos nenhum benefício
            return Response({
                "detail": "Dados de Vale Transporte validados com sucesso.",
                "status": "VALIDATED",
                "summary": payload.get("summary", {}),
                "dados_validados": payload.get("dados_validados", [])
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
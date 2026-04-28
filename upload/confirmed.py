from rest_framework import serializers
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import ProcessamentoFinalSerializer
from .models import FileUpload
from beneficios.models import Importacao


class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data 
        file_id = payload.get("file_upload_id")

        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        try:
            file_upload = FileUpload.objects.get(id=file_id)
            if file_upload.process_status == "COMPLETED":
                return Response(
                    {"detail": "Este arquivo já foi processado anteriormente."}, 
                    status=status.HTTP_400_BAD_REQUEST 
                )
        except FileUpload.DoesNotExist:
            return Response({"detail": "Arquivo não encontrado."}, status=404)

        serializer = ProcessamentoFinalSerializer(data=payload)

        if serializer.is_valid():
            try:
                result = serializer.save(processed_by=request.user)
                return Response({
                    "detail": "Dados gravados com sucesso.",
                    "registros_processados": result.get("count"),
                    "importacao_id": result.get("importacao_id"),
                    "status": "COMPLETED"
                }, status=status.HTTP_200_OK)
            except Exception as e:
                FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                Importacao.objects.filter(file_upload_id=file_id, status='PROCESSING').update(status='FAILED')
                return Response({"detail": f"Erro interno: {str(e)}"}, status=400) 

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
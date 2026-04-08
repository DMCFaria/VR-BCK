from django.db import models
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from .models import ProcessedFile
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import ProcessamentoFinalSerializer
from .models import FileUpload

class ConfirmedUploadsSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo ConfirmedUploads.
    """
    class Meta:
        model = ProcessedFile
        fields = '__all__' 

class ConfirmedUploadsListView(ListAPIView):
    """
    View para listar todos os uploads confirmados.
    Permite requisições GET.
    """
    queryset = ProcessedFile.objects.all()
    serializer_class = ConfirmedUploadsSerializer

class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]
    def post(self, request, *args, **kwargs):
        payload = request.data 
        file_id = payload.get("file_upload_id")

        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        # O Serializer agora fará a transação atômica e o lock do registro
        serializer = ProcessamentoFinalSerializer(data=payload)

        if serializer.is_valid():
            try:
                # Passamos o usuário logado para o save
                result = serializer.save(processed_by=request.user)
                
                return Response(
                    {
                        "detail": "Dados gravados com sucesso.",
                        "registros_processados": result.get("count"),
                        "status": "COMPLETED"
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                 # Caso ocorra erro, o status é gerido aqui ou dentro do Serializer
                 FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                 return Response({"detail": f"Erro interno ao gravar: {str(e)}"}, status=500)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
from django.db import models
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from .models import ProcessedFile

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
   
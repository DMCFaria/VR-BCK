from rest_framework import serializers
from .models import Produto, MovimentacaoBeneficio

class ProdutoSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo Produto (Catálogo de Benefícios).
    """
    class Meta:
        model = Produto
        fields = '__all__'
        read_only_fields = ('codigo_produto',) # Código do produto é a chave primária

class MovimentacaoBeneficioSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo MovimentacaoBeneficio (Transações).
    """
    class Meta:
        model = MovimentacaoBeneficio
        fields = '__all__'
        # O campo 'id' será gerado automaticamente como chave primária
from rest_framework import serializers
from django.db import transaction

# Importa os modelos dos novos apps
from entidades.models import Condominio, Funcionario
from beneficios.models import Produto, MovimentacaoBeneficio
from .models import FileUpload # O modelo de rastreio do upload

# --- SERIALIZERS DE ENTIDADES BASE (Para criação/atualização) ---

class CondominioSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Condominio (Entidade CNPJ).
    Usado para garantir que o CNPJ seja criado ou atualizado antes da movimentação.
    """
    class Meta:
        model = Condominio
        # Campos que podem vir do JSON (Header ou Produtos/Funcionario)
        fields = ['cnpj', 'nome', 'tipo_local', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep']

class FuncionarioSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Funcionario (Entidade CPF).
    Usado para garantir que o CPF seja criado ou atualizado.
    """
    # A data de nascimento deve vir no formato YYYY-MM-DD para ser salva,
    # mas o parser precisa garantir que o formato DDMMAAAA do TXT seja convertido antes de ser passado ao serializer.
    data_nascimento = serializers.DateField(format="%Y%m%d", input_formats=["%Y%m%d"]) 

    class Meta:
        model = Funcionario
        # O CNPJ virá do contexto da Movimentação/Condomínio
        fields = [
            'cpf', 'matricula', 'nome', 'funcao', 'data_nascimento', 
            'sexo', 'mae', 'cep', 'endereco_rua', 'endereco_numero', 
            'endereco_complemento', 'endereco_bairro'
        ]

class ProdutoSerializer(serializers.ModelSerializer):
    """
    Serializer para o catálogo de Produto (Entidade Código).
    """
    class Meta:
        model = Produto
        fields = ['codigo_produto', 'nome']

# --- SERIALIZER DE TRANSAÇÃO (O FATO) ---

class MovimentacaoBeneficioSerializer(serializers.ModelSerializer):
    """
    Serializer principal para a Movimentação.
    Contém a lógica de 'upsert' (cria ou atualiza) para entidades relacionadas.
    """
    # Define os campos de FKs como CharFields no input, pois virão como strings (CNPJ, CPF, Codigo)
    empresa_cnpj = serializers.CharField(source='empresa_cnpj_id', max_length=14)
    funcionario_cpf = serializers.CharField(source='funcionario_cpf_id', max_length=11)
    produto_codigo = serializers.CharField(source='produto_codigo_id', max_length=15)
    
    # A data de competência é crucial e virá do header do arquivo.
    data_competencia = serializers.DateField(format="%Y%m%d", input_formats=["%Y%m%d"]) 

    class Meta:
        model = MovimentacaoBeneficio
        fields = [
            'empresa_cnpj', 'funcionario_cpf', 'produto_codigo', 'data_competencia', 
            'valor_beneficio', 'quantidade_dias'
        ]

    def validate_data_competencia(self, value):
        # Garante que a data de competência é o primeiro dia do mês.
        if value.day != 1:
            raise serializers.ValidationError("A data de competência deve ser o primeiro dia do mês (Ex: 2025-09-01).")
        return value

# --- SERIALIZER DO ARQUIVO DE UPLOAD (Existente) ---

class FileUploadSerializer(serializers.ModelSerializer):
    """
    Serializer para rastrear o objeto FileUpload (o arquivo em si e o status).
    """
    class Meta:
        model = FileUpload
        fields = ['id', 'file', 'uploaded_at', 'process_status', 'summary_data']
        read_only_fields = ['uploaded_at', 'process_status', 'summary_data']

# --- LÓGICA DE PERSISTÊNCIA COMPLEXA (Salvando todas as entidades) ---

class ProcessamentoFinalSerializer(serializers.Serializer):
    """
    Serializer customizado para orquestrar o salvamento em todas as tabelas.
    Usado no endpoint de Confirmação (POST /confirm/).
    """
    movimentacoes = MovimentacaoBeneficioSerializer(many=True, required=True)
    condominios = CondominioSerializer(many=True, required=True)
    funcionarios = FuncionarioSerializer(many=True, required=True)
    produtos = ProdutoSerializer(many=True, required=True)
    
    # O ID do FileUpload original para rastreabilidade
    file_upload_id = serializers.IntegerField(write_only=True) 

    def create(self, validated_data):
        """
        Salva todos os Condomínios, Funcionários, Produtos e Movimentações
        dentro de uma única transação de banco de dados (atomicidade).
        """
        # A transação garante que, se qualquer save falhar, tudo é revertido.
        with transaction.atomic():
            
            # 1. UPSERT de Condomínios (Base: CNPJ)
            for data in validated_data.pop('condominios'):
                Condominio.objects.update_or_create(
                    cnpj=data['cnpj'],
                    defaults=data
                )

            # 2. UPSERT de Produtos (Base: codigo_produto)
            for data in validated_data.pop('produtos'):
                Produto.objects.update_or_create(
                    codigo_produto=data['codigo_produto'],
                    defaults=data
                )

            # 3. UPSERT de Funcionários (Base: CPF)
            for data in validated_data.pop('funcionarios'):
                # Note: O campo 'matricula' é UNIQUE mas não PK, então usamos update_or_create
                # baseado no CPF (PK)
                Funcionario.objects.update_or_create(
                    cpf=data['cpf'],
                    defaults=data
                )

            # 4. Criação das Movimentações (Base: Chave Composta)
            movimentacoes_criadas = []
            for data in validated_data.pop('movimentacoes'):
                # Aqui, estamos usando a restrição unique_together para garantir que
                # não se crie registros duplicados para a mesma competência.
                
                movimentacao, created = MovimentacaoBeneficio.objects.update_or_create(
                    empresa_cnpj_id=data['empresa_cnpj_id'],
                    funcionario_cpf_id=data['funcionario_cpf_id'],
                    produto_codigo_id=data['produto_codigo_id'],
                    data_competencia=data['data_competencia'],
                    defaults={
                        'valor_beneficio': data['valor_beneficio'],
                        'quantidade_dias': data['quantidade_dias'],
                    }
                )
                movimentacoes_criadas.append(movimentacao)
                
            # 5. Marca o FileUpload como 'PROCESSADO' (ou COMPLETED)
            file_upload_instance = FileUpload.objects.get(pk=validated_data['file_upload_id'])
            file_upload_instance.process_status = 'COMPLETED'
            file_upload_instance.save()
            
            return {"count": len(movimentacoes_criadas), "status": file_upload_instance.process_status}

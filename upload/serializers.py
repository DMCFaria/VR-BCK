from rest_framework import serializers
from django.db import transaction
from entidades.models import Condominio, Funcionario
from beneficios.models import Produto, MovimentacaoBeneficio
from .models import FileUpload, ProcessedFile

# --- SERIALIZER DO ARQUIVO DE UPLOAD ---

class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        # CORREÇÃO: Adicionamos uploaded_by aos fields
        fields = ['id', 'file', 'uploaded_at', 'process_status', 'summary_data', 'uploaded_by']
        # CORREÇÃO: Marcamos uploaded_at, process_status e uploaded_by como read_only
        read_only_fields = ['uploaded_at', 'process_status', 'summary_data', 'uploaded_by']


# --- SERIALIZERS DE PROCESSAMENTO ---

class MovimentacaoDetalhadaSerializer(serializers.Serializer):
    cpf_func = serializers.CharField(max_length=14)
    nome_func = serializers.CharField(max_length=255)
    
    produto_codigo = serializers.CharField(max_length=20)
    produto = serializers.CharField(max_length=255) 

    cnpj = serializers.CharField(max_length=20)
    departamento = serializers.CharField(max_length=255)
    
    valor_recarga_bene = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantidade = serializers.IntegerField()
    vencimento = serializers.DateField(format="%Y-%m-%d")
    
    endereco = serializers.CharField(required=False, allow_blank=True)
    bairro = serializers.CharField(required=False, allow_blank=True)
    cidade = serializers.CharField(required=False, allow_blank=True)
    uf = serializers.CharField(required=False, allow_blank=True)
    cep = serializers.CharField(required=False, allow_blank=True)
    matricula = serializers.CharField(required=False, allow_blank=True)
    funcao = serializers.CharField(required=False, allow_blank=True)
    
    data_nascimento = serializers.DateField(format="%Y-%m-%d", required=False, allow_null=True)
    
    beneficio_nome = serializers.CharField(required=False)
    valor_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    repasse_vt = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    taxa = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    periodos = serializers.CharField(required=False)
    periodo2 = serializers.CharField(required=False)


class ProcessamentoFinalSerializer(serializers.Serializer):
    movimentacoes_detalhada = MovimentacaoDetalhadaSerializer(many=True)
    file_upload_id = serializers.IntegerField()
    novos_registros = serializers.JSONField(required=False)

    def create(self, validated_data):
        rows = validated_data.get('movimentacoes_detalhada', [])
        file_upload_id = validated_data.get('file_upload_id')
        
        processed_by_user = validated_data.get('processed_by')

        condominios_cache = {}
        funcionarios_cache = {}
        produtos_cache = {}

        with transaction.atomic():
            count_movimentacoes = 0
            
            for row in rows:
                # 1. CONDOMÍNIO
                cnpj = row['cnpj']
                if cnpj not in condominios_cache:
                    condominio, _ = Condominio.objects.update_or_create(
                        cnpj=cnpj,
                        defaults={
                            'nome': row['departamento'],
                            'endereco': row.get('endereco', ''),
                            'bairro': row.get('bairro', ''),
                            'cidade': row.get('cidade', ''),
                            'estado': row.get('uf', ''),
                            'cep': row.get('cep', ''),
                            'tipo_local': 'CONDOMINIO'
                        }
                    )
                    condominios_cache[cnpj] = condominio
                else:
                    condominio = condominios_cache[cnpj]

                # 2. FUNCIONÁRIO
                cpf = row['cpf_func']
                if cpf not in funcionarios_cache:
                    funcionario, _ = Funcionario.objects.update_or_create(
                        cpf=cpf,
                        defaults={
                            'nome': row['nome_func'],
                            'matricula': row.get('matricula', ''),
                            'funcao': row.get('funcao', ''),
                            'data_nascimento': row.get('data_nascimento'), 
                            'departamento': row['departamento']
                        } 
                    )
                    funcionarios_cache[cpf] = funcionario
                else:
                    funcionario = funcionarios_cache[cpf]
                
                # 3. PRODUTO
                produto_codigo = row['produto_codigo']
                if produto_codigo not in produtos_cache:
                    produto, _ = Produto.objects.update_or_create(
                        codigo_produto=produto_codigo,
                        defaults={'nome': row['produto']}
                    )
                    produtos_cache[produto_codigo] = produto
                else:
                    produto = produtos_cache[produto_codigo]

                # 4. MOVIMENTAÇÃO
                MovimentacaoBeneficio.objects.update_or_create(
                    empresa_cnpj=condominio,
                    funcionario_cpf=funcionario,
                    produto_codigo=produto,
                    data_competencia=row['vencimento'],
                    defaults={
                        'valor_beneficio': row['valor_recarga_bene'],
                        'quantidade_dias': row['quantidade']
                    }
                )
                count_movimentacoes += 1

            # 5. ATUALIZA STATUS E CRIA REGISTRO EM PROCESSED FILE
            if file_upload_id:
                try:
                    f = FileUpload.objects.get(id=file_upload_id)
                    f.process_status = 'COMPLETED'
                    f.save()
                    
                    if processed_by_user:
                        ProcessedFile.objects.create(
                            file=f,
                            processed_by=processed_by_user
                        )
                        
                except FileUpload.DoesNotExist:
                    pass

            return {
                "count": count_movimentacoes, 
                "status": "COMPLETED"
            }
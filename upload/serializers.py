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
    produto_codigo = serializers.CharField(max_length=50)
    produto = serializers.CharField(max_length=255) 
    cnpj = serializers.CharField(max_length=20)
    departamento = serializers.CharField(max_length=255)
    
    vencimento = serializers.DateField(input_formats=['%d/%m/%Y', '%Y-%m-%d'])
    valor_recarga_bene = serializers.DecimalField(max_digits=12, decimal_places=2)
    quantidade = serializers.IntegerField()
    
    endereco = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bairro = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cidade = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    uf = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cep = serializers.CharField(required=False, allow_blank=True, allow_null=True)   
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
        print(f"DEBUG: Recebi {len(rows)} linhas validadas")
        file_upload_id = validated_data.get('file_upload_id')
        processed_by_user = validated_data.get('processed_by')
        
        dados_da_requisicao = validated_data.copy()
        dados_da_requisicao.pop('processed_by', None) 

        condominios_cache = {}
        funcionarios_cache = {}
        produtos_cache = {}
        
        # Lista para acumular objetos para o bulk_create
        movimentacoes_para_inserir = []

        # Usamos select_for_update para travar a linha do FileUpload durante a transação
        with transaction.atomic():
            try:
                file_upload_instance = FileUpload.objects.select_for_update().get(id=file_upload_id)
            except FileUpload.DoesNotExist:
                raise serializers.ValidationError({"file_upload_id": "Upload não encontrado."})

            if file_upload_instance.process_status == 'COMPLETED':
                raise serializers.ValidationError({"detail": "Este arquivo já foi processado anteriormente."})

            # Registro mestre
            processamento_final_instance = ProcessedFile.objects.create(
                file=file_upload_instance,
                processed_by=processed_by_user,
                dados_requisicao=dados_da_requisicao 
            )

            for row in rows:
                # 1. Condomínio (Mantemos update_or_create pois são poucos registros e há dependência)
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

                # 2. Funcionário
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

                # 3. Produto
                produto_codigo = row['produto_codigo']
                if produto_codigo not in produtos_cache:
                    produto, _ = Produto.objects.update_or_create(
                        codigo_produto=produto_codigo,
                        defaults={'nome': row['produto']}
                    )
                    produtos_cache[produto_codigo] = produto
                else:
                    produto = produtos_cache[produto_codigo]

                # 4. Preparação para o Bulk Insert (Não salva no banco ainda)
                movimentacoes_para_inserir.append(
                    MovimentacaoBeneficio(
                        empresa_cnpj=condominio,
                        funcionario_cpf=funcionario,
                        produto_codigo=produto,
                        data_competencia=row['vencimento'],
                        valor_beneficio=row['valor_recarga_bene'],
                        quantidade_dias=row['quantidade']
                    )
                )

            # Executa a inserção de todas as movimentações em uma única query
            MovimentacaoBeneficio.objects.bulk_create(movimentacoes_para_inserir, ignore_conflicts=True)

            # Atualiza status final
            file_upload_instance.process_status = 'COMPLETED'
            file_upload_instance.save()
            
            return {
                "count": len(movimentacoes_para_inserir), 
                "status": "COMPLETED"
            }
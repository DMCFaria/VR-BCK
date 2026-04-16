from rest_framework import serializers
from django.db import transaction
from entidades.models import Condominio, Funcionario, VinculoCondominio
from beneficios.models import Produto, MovimentacaoBeneficio
from .models import FileUpload, ProcessedFile


class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = ['id', 'file', 'uploaded_at', 'process_status', 'summary_data', 'uploaded_by']
        read_only_fields = ['uploaded_at', 'process_status', 'summary_data', 'uploaded_by']


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


class MovimentacaoSerializer(serializers.Serializer):
    produto = serializers.CharField(max_length=255)
    valor = serializers.DecimalField(max_digits=12, decimal_places=2)


class FuncionarioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cpf = serializers.CharField(max_length=14)
    matricula = serializers.CharField(max_length=50)
    departamento = serializers.CharField(max_length=255)
    funcao = serializers.CharField(max_length=100)
    data_nascimento = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    valor_bene = serializers.DecimalField(max_digits=12, decimal_places=2)
    movimentacoes = MovimentacaoSerializer(many=True)


class CondominioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cnpj = serializers.CharField(max_length=20)
    valor_condo = serializers.DecimalField(max_digits=12, decimal_places=2)
    funcionarios = FuncionarioSerializer(many=True)


class CondominiosDataSerializer(serializers.Serializer):
    condominios = CondominioSerializer(many=True)
    file_upload_id = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    summary = serializers.DictField(required=False)


class ProcessamentoFinalSerializer(serializers.Serializer):
    condominios = CondominioSerializer(many=True)
    file_upload_id = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    summary = serializers.DictField(required=False)
    novos_registros = serializers.JSONField(required=False)

    def _get_ou_criar_vinculo(self, condominio, administradora):
        vinculo, created = VinculoCondominio.objects.get_or_create(
            condominio=condominio,
            administradora=administradora
        )
        return vinculo

    def create(self, validated_data):
        from django.db.models import Q
        
        condominios_data = validated_data.get('condominios', [])
        file_upload_id = validated_data.get('file_upload_id')
        processed_by_user = validated_data.get('processed_by')
        
        dados_da_requisicao = validated_data.copy()
        dados_da_requisicao.pop('processed_by', None)
        
        def _normalize_date(val):
            if val is None:
                return None
            val_str = str(val)
            invalid_dates = {'0001-01-01', '0000-00-00', '0020-00-00', '1900-01-01'}
            if val_str in invalid_dates or val_str.startswith('000') or val_str == '00-00-0000':
                return None
            return val
        
        def _convert_decimals(obj):
            if isinstance(obj, dict):
                return {k: _convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [_convert_decimals(item) for item in obj]
            elif hasattr(obj, '__float__'):
                return float(obj)
            return obj
        
        def _sanitize_data(obj):
            if isinstance(obj, dict):
                return {k: _sanitize_data(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [_sanitize_data(item) for item in obj]
            elif isinstance(obj, str) and obj in {'0001-01-01', '0000-00-00', '0020-00-00', '1900-01-01'}:
                return None
            return obj
        
        dados_da_requisicao = _convert_decimals(_sanitize_data(dados_da_requisicao)) 
        
        administradora = getattr(processed_by_user, 'administradora', None)
        if not administradora:
            raise serializers.ValidationError({
                "detail": "Usuário não possui administradora vinculada."
            })
        
        raw_data_comp = validated_data.get('summary', {}).get('data_competencia_arquivo')
        data_competencia = None
        if raw_data_comp:
            data_competencia = _normalize_date(raw_data_comp)
        
        if not data_competencia:
            for c in condominios_data:
                for f in c.get('funcionarios', []):
                    dt = _normalize_date(f.get('data_nascimento'))
                    if dt:
                        data_competencia = dt
                        break
                if data_competencia:
                    break
        
        if not data_competencia:
            from datetime import date
            data_competencia = str(date.today())
        
        cnpj_list = [c['cnpj'] for c in condominios_data]
        cpf_list = list(set(f['cpf'] for c in condominios_data for f in c.get('funcionarios', [])))
        produtos_raw = [(m['produto'][:50] if m.get('produto') else 'SEM_PRODUTO', m.get('produto', '')) 
                        for c in condominios_data for f in c.get('funcionarios', []) for m in f.get('movimentacoes', [])]
        prod_key_list = list(set(k for k, _ in produtos_raw))
        
        existing_condos = {c.cnpj: c for c in Condominio.objects.filter(cnpj__in=cnpj_list)}
        existing_funcs = {f.cpf: f for f in Funcionario.objects.filter(cpf__in=cpf_list)}
        existing_prods = {p.codigo_produto: p for p in Produto.objects.filter(codigo_produto__in=prod_key_list)}
        
        condos_to_create = []
        funcs_to_create = []
        prods_to_create = []
        
        for condo in condominios_data:
            if condo['cnpj'] not in existing_condos:
                condos_to_create.append(Condominio(
                    cnpj=condo['cnpj'],
                    nome=condo['nome'],
                    tipo_local='CONDOMINIO'
                ))
        
        for c in condominios_data:
            for f in c.get('funcionarios', []):
                if f['cpf'] not in existing_funcs:
                    funcs_to_create.append(Funcionario(
                        cpf=f['cpf'],
                        nome=f['nome'],
                        matricula=f.get('matricula', ''),
                        funcao=f.get('funcao', ''),
                        data_nascimento=_normalize_date(f.get('data_nascimento')),
                        departamento=f.get('departamento', '')
                    ))
        
        prod_map = {}
        for key, nome in produtos_raw:
            if key not in prod_map:
                prod_map[key] = nome
        
        for key, nome in prod_map.items():
            if key not in existing_prods:
                prods_to_create.append(Produto(codigo_produto=key, nome=nome))
        
        Condominio.objects.bulk_create(condos_to_create, ignore_conflicts=True)
        Funcionario.objects.bulk_create(funcs_to_create, ignore_conflicts=True)
        Produto.objects.bulk_create(prods_to_create, ignore_conflicts=True)
        
        existing_condos = {c.cnpj: c for c in Condominio.objects.filter(cnpj__in=cnpj_list)}
        existing_funcs = {f.cpf: f for f in Funcionario.objects.filter(cpf__in=cpf_list)}
        existing_prods = {p.codigo_produto: p for p in Produto.objects.filter(codigo_produto__in=prod_key_list)}
        
        condos_to_vinc = [c for c in cnpj_list if not VinculoCondominio.objects.filter(
            administradora=administradora, condominio_id=c).exists()]
        if condos_to_vinc:
            vinculos = [VinculoCondominio(administradora=administradora, condominio_id=c) for c in condos_to_vinc]
            VinculoCondominio.objects.bulk_create(vinculos, ignore_conflicts=True)
        
        collection_keys = []
        for condo in condominios_data:
            condo_obj = existing_condos[condo['cnpj']]
            for func in condo.get('funcionarios', []):
                func_obj = existing_funcs[func['cpf']]
                for mov in func.get('movimentacoes', []):
                    prod_key = (mov.get('produto') or '')[:50] or 'SEM_PRODUTO'
                    prod_obj = existing_prods.get(prod_key)
                    if prod_obj:
                        collection_keys.append((
                            condo_obj.pk, func_obj.pk, prod_obj.pk, data_competencia, mov.get('valor', 0)
                        ))
        
        if collection_keys:
            existing_movs = set(
                MovimentacaoBeneficio.objects.filter(
                    empresa_cnpj_id__in=[k[0] for k in collection_keys],
                    funcionario_cpf_id__in=[k[1] for k in collection_keys],
                    produto_codigo_id__in=[k[2] for k in collection_keys],
                    data_competencia=data_competencia
                ).values_list('empresa_cnpj_id', 'funcionario_cpf_id', 'produto_codigo_id', 'data_competencia')
            )
            
            novos_registros = [
                MovimentacaoBeneficio(
                    empresa_cnpj_id=cnpj_pk, funcionario_cpf_id=cpf_pk,
                    produto_codigo_id=prod_pk, data_competencia=dt_comp,
                    valor_beneficio=valor, quantidade_dias=1
                )
                for cnpj_pk, cpf_pk, prod_pk, dt_comp, valor in collection_keys
                if (cnpj_pk, cpf_pk, prod_pk, dt_comp) not in existing_movs
            ]
            
            MovimentacaoBeneficio.objects.bulk_create(novos_registros, ignore_conflicts=True)
        else:
            novos_registros = []
        
        with transaction.atomic():
            try:
                file_upload_instance = FileUpload.objects.select_for_update().get(id=file_upload_id)
            except FileUpload.DoesNotExist:
                raise serializers.ValidationError({"file_upload_id": "Upload não encontrado."})

            if file_upload_instance.process_status == 'COMPLETED':
                raise serializers.ValidationError({"detail": "Este arquivo já foi processado anteriormente."})

            ProcessedFile.objects.create(
                file=file_upload_instance,
                processed_by=processed_by_user,
                dados_requisicao=dados_da_requisicao 
            )

            file_upload_instance.process_status = 'COMPLETED'
            file_upload_instance.save()
        
        return {"count": len(novos_registros), "status": "COMPLETED"}


class FaturamentoExportSerializer(serializers.Serializer):
    CPF = serializers.CharField()
    NOME_FUNC = serializers.CharField()
    PRODUTO = serializers.CharField()
    BENEFICIO = serializers.CharField()
    VALOR_UNITARIO = serializers.DecimalField(max_digits=10, decimal_places=2)
    QUANTIDADE = serializers.IntegerField()
    VALOR_RECARGA_BENE = serializers.DecimalField(max_digits=12, decimal_places=2)
    REPASSE_VT = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    DEPARTAMENTO = serializers.CharField()
    CNPJ = serializers.CharField()
    ENDERECO = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    BAIRRO = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    CIDADE = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    UF = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    CEP = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    TAXA = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    vencimento = serializers.DateField(required=False, allow_null=True)
    periodos = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    periodo2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)

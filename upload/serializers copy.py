import logging

from rest_framework import serializers
from .models import FileUpload

logger = logging.getLogger(__name__)

class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = ['id', 'file', 'uploaded_at', 'process_status', 'summary_data', 'uploaded_by']
        read_only_fields = ['uploaded_at', 'process_status', 'summary_data', 'uploaded_by']
        extra_kwargs = {'file': {'required': False, 'allow_null': True}}

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
    codigo_produto = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    valor = serializers.DecimalField(max_digits=12, decimal_places=2)

class FuncionarioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cpf = serializers.CharField(max_length=14)
    matricula = serializers.CharField(max_length=50)
    departamento = serializers.CharField(max_length=255)
    funcao = serializers.CharField(max_length=100)
    data_nascimento = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cep = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True)
    endereco_rua = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    endereco_numero = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    endereco_complemento = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    endereco_bairro = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    valor_bene = serializers.DecimalField(max_digits=12, decimal_places=2)
    movimentacoes = MovimentacaoSerializer(many=True)

class CondominioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cnpj = serializers.CharField(max_length=20)
    valor_condo = serializers.DecimalField(max_digits=12, decimal_places=2)
    rua = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    numero = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    complemento = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bairro = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cidade = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    estado = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cep = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    funcionarios = FuncionarioSerializer(many=True)

class CondominiosDataSerializer(serializers.Serializer):
    condominios = CondominioSerializer(many=True)
    file_upload_id = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    summary = serializers.DictField(required=False)

class ProcessamentoFinalSerializer(serializers.Serializer):
    condominios = CondominioSerializer(many=True)
    file_upload_id = serializers.IntegerField(required=False)
    importacao_id = serializers.IntegerField(required=False)
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    summary = serializers.DictField(required=False)
    novos_registros = serializers.JSONField(required=False)
    linhas_com_erro = serializers.ListField(required=False, allow_empty=True)
    data_vencimento = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    vencimento = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    vigencia_inicio = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    inicio_vigencia = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    vigencia_fim = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    fim_vigencia = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    periodo_inicio = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    periodo_fim = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)

    def validate(self, data):
        if not data.get('file_upload_id') and not data.get('importacao_id'):
            raise serializers.ValidationError({
                "detail": "Informe file_upload_id ou importacao_id."
            })
        summary = data.get('summary', {})
        if 'vencimento' not in data and 'vencimento' in summary:
            data['vencimento'] = summary['vencimento']
        if 'periodo_inicio' not in data and 'periodo_inicio' in summary:
            data['periodo_inicio'] = summary['periodo_inicio']
        if 'periodo_fim' not in data and 'periodo_fim' in summary:
            data['periodo_fim'] = summary['periodo_fim']
        if data.get('vencimento') and not data.get('data_vencimento'):
            data['data_vencimento'] = data.pop('vencimento')
        elif 'vencimento' in data:
            data.pop('vencimento')
        if data.get('inicio_vigencia') and not data.get('vigencia_inicio'):
            data['vigencia_inicio'] = data.pop('inicio_vigencia')
        elif 'inicio_vigencia' in data:
            data.pop('inicio_vigencia')
        if data.get('fim_vigencia') and not data.get('vigencia_fim'):
            data['vigencia_fim'] = data.pop('fim_vigencia')
        elif 'fim_vigencia' in data:
            data.pop('fim_vigencia')
        if data.get('periodo_inicio') and not data.get('vigencia_inicio'):
            data['vigencia_inicio'] = data.pop('periodo_inicio')
        elif 'periodo_inicio' in data:
            data.pop('periodo_inicio')
        if data.get('periodo_fim') and not data.get('vigencia_fim'):
            data['vigencia_fim'] = data.pop('periodo_fim')
        elif 'periodo_fim' in data:
            data.pop('periodo_fim')
        return data

    def create(self, validated_data):
        from decimal import Decimal
        from django.db import transaction

        condominios_data = validated_data.get('condominios', [])
        file_upload_id = validated_data.get('file_upload_id')
        importacao_id_origem = validated_data.get('importacao_id')
        processed_by_user = validated_data.get('processed_by')
        total_funcionarios = validated_data.get('summary', {}).get('total_funcionarios', 0)

        # ========== 1. GARANTIR FILE_UPLOAD_ID ==========
        if not file_upload_id and importacao_id_origem:
            last_fu = FileUpload.objects.order_by('-id').first()
            new_id = (last_fu.id + 1) if last_fu else 1
            fu = FileUpload.objects.create(
                id=new_id,
                uploaded_by=processed_by_user,
                process_status='PENDING'
            )
            file_upload_id = fu.id
        
        # ========== 2. EXTRAIR VALOR TOTAL DO PAYLOAD (FONTE DA VERDADE) ==========
        summary = validated_data.get('summary', {})
        valor_total_payload = Decimal(str(summary.get('valor_total_beneficios', 0)))
        
        # ========== 3. EXTRAIR COMPETÊNCIA DO PAYLOAD ==========
        competencia_mes = validated_data.get('competencia_mes')
        competencia_ano = validated_data.get('competencia_ano')
        data_competencia = None
        
        if competencia_mes and competencia_ano:
            from datetime import datetime
            try:
                data_competencia = datetime(int(competencia_ano), int(competencia_mes), 1).date()
            except:
                pass
        
        # Fallback: usar vencimento ou periodo_inicio
        if not data_competencia:
            vencimento = validated_data.get('data_vencimento')
            if vencimento:
                data_competencia = vencimento.replace(day=1)
        
        if not data_competencia:
            periodo_inicio = validated_data.get('periodo_inicio') or validated_data.get('vigencia_inicio')
            if periodo_inicio:
                data_competencia = periodo_inicio.replace(day=1)
        
        if not data_competencia:
            from datetime import date
            data_competencia = date.today()
        
        # ========== 4. VALIDAÇÕES INICIAIS ==========
        administradora = getattr(processed_by_user, 'administradora', None)
        if not administradora:
            raise serializers.ValidationError({
                "detail": "Usuário não possui administradora vinculada."
            })
        
        # ========== 5. PREPARAR LISTS PARA BULK OPERATIONS ==========
        cnpj_list = [c['cnpj'] for c in condominios_data]
        cpf_list = list(set(f['cpf'] for c in condominios_data for f in c.get('funcionarios', [])))
        
        # Extrair produtos únicos
        produtos_raw = []
        for c in condominios_data:
            for f in c.get('funcionarios', []):
                for m in f.get('movimentacoes', []):
                    codigo = m.get('codigo_produto') or ''
                    produto = m.get('produto') or ''
                    if codigo:
                        key = codigo.strip()[:50]
                    elif produto:
                        key = produto.strip()[:50]
                    else:
                        key = 'SEM_PRODUTO'
                    produtos_raw.append((key, produto if produto else key))
        prod_key_list = list(set(k for k, _ in produtos_raw))
        
        # ========== 6. BUSCAR ENTIDADES EXISTENTES ==========
        from entidades.models import Condominio, Funcionario, VinculoCondominio
        from beneficios.models import Produto, MovimentacaoBeneficio, Importacao
        from .models import FileUpload
        
        existing_condos = {c.cnpj: c for c in Condominio.objects.filter(cnpj__in=cnpj_list)}
        existing_funcs = {f.cpf: f for f in Funcionario.objects.filter(cpf__in=cpf_list)}
        existing_prods = {p.codigo_produto: p for p in Produto.objects.filter(codigo_produto__in=prod_key_list)}
        
        # ========== 7. CRIAR/ATUALIZAR CONDOMÍNIOS ==========
        condos_to_create = []
        condos_to_update = []
        
        for condo in condominios_data:
            if condo['cnpj'] not in existing_condos:
                condos_to_create.append(Condominio(
                    cnpj=condo['cnpj'],
                    nome=condo['nome'],
                    tipo_local='CONDOMINIO',
                    endereco=condo.get('rua', ''),
                    numero=condo.get('numero', ''),
                    complemento=condo.get('complemento', ''),
                    bairro=condo.get('bairro', ''),
                    cidade=condo.get('cidade', ''),
                    estado=condo.get('estado', ''),
                    cep=condo.get('cep', '')
                ))
            else:
                condo_obj = existing_condos[condo['cnpj']]
                updated = False
                if condo.get('rua') and not condo_obj.endereco:
                    condo_obj.endereco = condo['rua']
                    updated = True
                if updated:
                    condos_to_update.append(condo_obj)
        
        if condos_to_create:
            Condominio.objects.bulk_create(condos_to_create, ignore_conflicts=True)
        if condos_to_update:
            Condominio.objects.bulk_update(condos_to_update, ['endereco'])
        
        # ========== 8. CRIAR/ATUALIZAR FUNCIONÁRIOS ==========
        funcs_to_create = []
        funcs_to_update = []
        
        def _normalize_date(val):
            if val is None:
                return None
            val_str = str(val)
            invalid_dates = {'0001-01-01', '0000-00-00', '0020-00-00', '1900-01-01'}
            if val_str in invalid_dates or val_str.startswith('000') or val_str == '00-00-0000':
                return None
            return val
        
        for c in condominios_data:
            for f in c.get('funcionarios', []):
                if f['cpf'] not in existing_funcs:
                    funcs_to_create.append(Funcionario(
                        cpf=f['cpf'],
                        nome=f['nome'],
                        matricula=f.get('matricula', ''),
                        funcao=f.get('funcao', ''),
                        data_nascimento=_normalize_date(f.get('data_nascimento')),
                        departamento=f.get('departamento', ''),
                        cep=f.get('cep', ''),
                        endereco_rua=f.get('endereco_rua', ''),
                        endereco_numero=f.get('endereco_numero', ''),
                        endereco_complemento=f.get('endereco_complemento', ''),
                        endereco_bairro=f.get('endereco_bairro', '')
                    ))
                else:
                    func_obj = existing_funcs[f['cpf']]
                    updated = False
                    if f.get('cep') and func_obj.cep != f['cep']:
                        func_obj.cep = f['cep']
                        updated = True
                    if updated:
                        funcs_to_update.append(func_obj)
        
        if funcs_to_create:
            Funcionario.objects.bulk_create(funcs_to_create, ignore_conflicts=True)
        if funcs_to_update:
            Funcionario.objects.bulk_update(funcs_to_update, ['cep'])
        
        # ========== 9. CRIAR PRODUTOS QUE NÃO EXISTEM ==========
        prod_map = {}
        for key, nome in produtos_raw:
            if key not in prod_map:
                prod_map[key] = nome
        
        prods_to_create = []
        for key, nome in prod_map.items():
            if key not in existing_prods:
                prods_to_create.append(Produto(codigo_produto=key, nome=nome))
        
        if prods_to_create:
            Produto.objects.bulk_create(prods_to_create, ignore_conflicts=True)
        
        # ========== 10. RECARREGAR ENTIDADES APÓS CRIAÇÃO ==========
        existing_condos = {c.cnpj: c for c in Condominio.objects.filter(cnpj__in=cnpj_list)}
        existing_funcs = {f.cpf: f for f in Funcionario.objects.filter(cpf__in=cpf_list)}
        existing_prods = {p.codigo_produto: p for p in Produto.objects.filter(codigo_produto__in=prod_key_list)}
        
        # ========== 11. CRIAR VÍNCULOS CONDOMÍNIO-ADMINISTRADORA ==========
        condos_to_vinc = [c for c in cnpj_list if not VinculoCondominio.objects.filter(
            administradora=administradora, condominio_id=c).exists()]
        if condos_to_vinc:
            vinculos = [VinculoCondominio(administradora=administradora, condominio_id=c) for c in condos_to_vinc]
            VinculoCondominio.objects.bulk_create(vinculos, ignore_conflicts=True)
        
        # ========== 12. CRIAR IMPORTAÇÃO COM VALOR TOTAL ==========
        importacao = Importacao.objects.create(
            file_upload_id=file_upload_id,
            usuario=processed_by_user,
            administradora=administradora,
            status='AGUARDANDO_FATURAMENTO',
            total_registros=0,
            registros_processados=0,
            valor_total=valor_total_payload,
            total_funcionarios=total_funcionarios,
            data_vencimento=validated_data.get('data_vencimento'),
            vigencia_inicio=validated_data.get('vigencia_inicio') or validated_data.get('periodo_inicio'),
            vigencia_fim=validated_data.get('vigencia_fim') or validated_data.get('periodo_fim')
        )
        
        # ========== 13. SALVAR MOVIMENTAÇÕES USANDO O PAYLOAD DIRETAMENTE ==========
        movimentacoes_to_create = []
        registros_count = 0

        # PERCORRE O PAYLOAD EXATAMENTE COMO ELE VEM DO FRONTEND
        for condo_data in condominios_data:
            for func_data in condo_data.get('funcionarios', []):
                for bene_data in func_data.get('beneficios', []):  # USA beneficios do payload
                    # PEGA OS DADOS DIRETO DO PAYLOAD
                    codigo_produto = bene_data.get('codigo', '').strip()
                    nome_produto = bene_data.get('nome', '')
                    valor_beneficio = Decimal(str(bene_data.get('valor', 0)))
                    
                    # PULA SE NÃO TIVER VALOR
                    if valor_beneficio == 0:
                        continue
                    
                    # ENCONTRA OU CRIA O PRODUTO (SIMPLES)
                    prod_obj = existing_prods.get(codigo_produto)
                    if not prod_obj and codigo_produto:
                        prod_obj, _ = Produto.objects.get_or_create(
                            codigo_produto=codigo_produto,
                            defaults={'nome': nome_produto or codigo_produto}
                        )
                        existing_prods[codigo_produto] = prod_obj
                    
                    if not prod_obj:
                        logger.warning(f"Produto não encontrado/criado para código: {codigo_produto}")
                        continue
                    
                    # ENCONTRA O CONDOMÍNIO E FUNCIONÁRIO
                    condo_obj = existing_condos.get(condo_data['cnpj'])
                    func_obj = existing_funcs.get(func_data['cpf'])
                    
                    if not condo_obj or not func_obj:
                        logger.warning(f"Condomínio ou funcionário não encontrado: {condo_data.get('cnpj')} / {func_data.get('cpf')}")
                        continue
                    
                    # CRIA A MOVIMENTAÇÃO COM OS VALORES DO PAYLOAD
                    movimentacoes_to_create.append(MovimentacaoBeneficio(
                        importacao=importacao,
                        empresa_cnpj=condo_obj,
                        funcionario_cpf=func_obj,
                        produto_codigo=prod_obj,
                        data_competencia=data_competencia,
                        valor_beneficio=valor_beneficio,  # VALOR JÁ CORRETO DO FRONTEND
                        quantidade_dias=1
                    ))
                    registros_count += 1

        # SALVA TUDO
        movimentacoes_salvas = 0
        if movimentacoes_to_create:
            try:
                MovimentacaoBeneficio.objects.bulk_create(
                    movimentacoes_to_create,
                    ignore_conflicts=True,
                    batch_size=500
                )
                movimentacoes_salvas = len(movimentacoes_to_create)
            except Exception as e:
                logger.error(f"Erro no bulk_create: {e}")
                # Fallback: salva um por um
                for mov in movimentacoes_to_create:
                    try:
                        mov.save()
                        movimentacoes_salvas += 1
                    except Exception as e2:
                        logger.error(f"Erro ao salvar individual: {e2}")
        
        # ========== 14. ATUALIZAR ESTATÍSTICAS ==========
        importacao.total_registros = registros_count
        importacao.registros_processados = movimentacoes_salvas
        importacao.save()
        
        # ========== 15. ATUALIZAR FILEUPLOAD ==========
        with transaction.atomic():
            try:
                file_upload_instance = FileUpload.objects.select_for_update().get(id=file_upload_id)
                if file_upload_instance.process_status != 'COMPLETED':
                    file_upload_instance.process_status = 'AGUARDANDO_FATURAMENTO'
                    file_upload_instance.summary_data = summary
                    file_upload_instance.save()
            except FileUpload.DoesNotExist:
                pass
        
        # ========== 16. LOG ==========
        logger.info(f"Importação {importacao.id} criada. Valor total: {valor_total_payload}. "
                    f"Movimentações: {movimentacoes_salvas}/{registros_count}")
        
        return {
            "count": movimentacoes_salvas,
            "status": "AGUARDANDO_FATURAMENTO",
            "importacao_id": importacao.id,
            "valor_total": float(valor_total_payload)
        }

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

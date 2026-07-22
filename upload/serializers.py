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
    valor_recarga_bene = serializers.DecimalField(max_digits=15, decimal_places=2)
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
    valor = serializers.DecimalField(max_digits=15, decimal_places=2)
    quantidade = serializers.IntegerField(required=False, default=1)

class FuncionarioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cpf = serializers.CharField(max_length=14)
    matricula = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    departamento = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    funcao = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    data_nascimento = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cep = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True)
    endereco_rua = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    endereco_numero = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    endereco_complemento = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    endereco_bairro = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    valor_bene = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0)
    movimentacoes = MovimentacaoSerializer(many=True, required=False, default=[])
    condominio = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)

class CondominioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cnpj = serializers.CharField(max_length=20)
    valor_condo = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0)
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
    
    competencia_mes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    competencia_ano = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    recebimento_beneficio = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    data_recebimento = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y'], required=False, allow_null=True)
    tipo_processamento = serializers.CharField(required=False, default='compra')
    modelo_importacao = serializers.CharField(required=False, default='VR-BENEFICIOS')
    origem = serializers.CharField(required=False, default='importacao_faturamento')
    status = serializers.CharField(required=False, default='PARSED')
    detail = serializers.CharField(required=False)
    dados_modificados = serializers.JSONField(required=False, allow_null=True, default=None)
    cartao_admin = serializers.BooleanField(required=False, allow_null=True, default=None)
    administradora_cnpj = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        if not data.get('file_upload_id') and not data.get('importacao_id'):
            raise serializers.ValidationError({
                "detail": "Informe file_upload_id ou importacao_id."
            })
        
        if 'periodo_inicio' in data and data['periodo_inicio'] and not data.get('vigencia_inicio'):
            data['vigencia_inicio'] = data['periodo_inicio']
        
        if 'periodo_fim' in data and data['periodo_fim'] and not data.get('vigencia_fim'):
            data['vigencia_fim'] = data['periodo_fim']
        
        if 'vencimento' in data and data['vencimento'] and not data.get('data_vencimento'):
            data['data_vencimento'] = data['vencimento']
        
        if 'inicio_vigencia' in data and data['inicio_vigencia'] and not data.get('vigencia_inicio'):
            data['vigencia_inicio'] = data['inicio_vigencia']
        
        if 'fim_vigencia' in data and data['fim_vigencia'] and not data.get('vigencia_fim'):
            data['vigencia_fim'] = data['fim_vigencia']

        if 'recebimento_beneficio' in data and data['recebimento_beneficio'] and not data.get('data_recebimento'):
            data['data_recebimento'] = data['recebimento_beneficio']

        return data

    def create(self, validated_data):
        from decimal import Decimal
        from django.db import transaction
        from datetime import datetime, date
        
        modelo_importacao = validated_data.get('modelo_importacao', 'VR-BENEFICIOS')
        condominios_data = validated_data.get('condominios', [])
        file_upload_id = validated_data.get('file_upload_id')
        importacao_id_origem = validated_data.get('importacao_id')
        processed_by_user = validated_data.get('processed_by')
        total_funcionarios = validated_data.get('summary', {}).get('total_funcionarios', 0)

        # ========== 1. VALIDAR ADMINISTRADORA ==========
        administradora = None
        if processed_by_user:
            administradora = getattr(processed_by_user, 'administradora_ativa', None)
            
            logger.info(f"Administradora do usuario {processed_by_user.email}: {administradora}")
        
        if not administradora:
            error_msg = "Usuário não possui administradora vinculada. Verifique o perfil do usuário."
            logger.error(error_msg)
            raise serializers.ValidationError({
                "detail": error_msg,
                "user_email": processed_by_user.email if processed_by_user else "unknown",
                "user_id": processed_by_user.id if processed_by_user else None
            })

        # Atualiza o flag cartao_admin da administradora conforme detectado na planilha.
        cartao_admin_payload = validated_data.get('cartao_admin')
        if cartao_admin_payload is not None and administradora.cartao_admin != cartao_admin_payload:
            administradora.cartao_admin = cartao_admin_payload
            administradora.save(update_fields=['cartao_admin'])
            logger.info(f"Administradora {administradora.cnpj} atualizada: cartao_admin={cartao_admin_payload}")

        # ========== 2. GARANTIR FILE_UPLOAD_ID ==========
        if not file_upload_id and importacao_id_origem:
            fu = FileUpload.objects.create(
                uploaded_by=processed_by_user,
                process_status='PENDING'
            )
            file_upload_id = fu.id
        
        # ========== 3. EXTRAIR VALOR TOTAL ==========
        summary = validated_data.get('summary', {})
        valor_total_payload = Decimal(str(summary.get('valor_total_beneficios', 0)))
        
        # ========== 4. EXTRAIR COMPETÊNCIA ==========
        competencia_mes = validated_data.get('competencia_mes')
        competencia_ano = validated_data.get('competencia_ano')
        data_competencia = None

        logger.info(f"Competência do payload: mês={competencia_mes}, ano={competencia_ano}")

        if competencia_mes and competencia_ano:
            try:
                data_competencia = datetime(int(competencia_ano), int(competencia_mes), 1).date()
                logger.info(f"Data de competência definida pelo payload: {data_competencia}")
            except Exception as e:
                logger.error(f"Erro ao parsear data de competência: {e}")

        if not data_competencia:
            vencimento = validated_data.get('data_vencimento') or validated_data.get('vencimento')
            if vencimento:
                data_competencia = vencimento.replace(day=1)
                logger.info(f"Data de competência definida pelo vencimento: {data_competencia}")

        if not data_competencia:
            vigencia_inicio = validated_data.get('vigencia_inicio') or validated_data.get('periodo_inicio')
            if vigencia_inicio:
                data_competencia = vigencia_inicio.replace(day=1)
                logger.info(f"Data de competência definida pela vigência início: {data_competencia}")

        if not data_competencia:
            competencia_arquivo = validated_data.get('summary', {}).get('data_competencia_arquivo')
            if competencia_arquivo:
                try:
                    data_competencia = datetime.strptime(competencia_arquivo, '%Y-%m-%d').date().replace(day=1)
                    logger.info(f"Data de competência do arquivo: {data_competencia}")
                except Exception as e:
                    logger.error(f"Erro ao parsear data_competencia_arquivo: {e}")

        if not data_competencia:
            data_competencia = date.today().replace(day=1)
            logger.warning(f"Usando data atual como competência: {data_competencia}")
        
        # ========== 5. PREPARAR LISTS PARA BULK OPERATIONS ==========
        # Normalizar CNPJ e CPF
        for condo in condominios_data:
            condo['cnpj'] = ''.join(filter(str.isdigit, str(condo.get('cnpj', ''))))
            for func in condo.get('funcionarios', []):
                func['cpf'] = ''.join(filter(str.isdigit, str(func.get('cpf', '')))).zfill(11)
        
        cnpj_list = [c['cnpj'] for c in condominios_data if c.get('cnpj')]
        cpf_list = list(set(f['cpf'] for c in condominios_data for f in c.get('funcionarios', []) if f.get('cpf')))
        
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
            cnpj_limpo = condo['cnpj']
            
            if cnpj_limpo not in existing_condos:
                condos_to_create.append(Condominio(
                    cnpj=cnpj_limpo,
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
                condo_obj = existing_condos[cnpj_limpo]
                updated = False

                # Nome sempre atualiza se vier diferente
                if condo.get('nome') and condo_obj.nome != condo['nome']:
                    condo_obj.nome = condo['nome']
                    updated = True

                # Se a planilha trouxer endereço, ela é a fonte fiel e sobrescreve
                # qualquer dado preenchido automaticamente por consulta de CNPJ.
                if condo.get('rua'):
                    if condo_obj.endereco != condo['rua']:
                        condo_obj.endereco = condo['rua']
                        updated = True
                    # Se houve atualização manual/endereço da planilha, resetamos
                    # o flag para permitir nova pesquisa futura se necessário.
                    if condo_obj.is_searched:
                        condo_obj.is_searched = False
                        updated = True

                if condo.get('numero') and condo_obj.numero != condo['numero']:
                    condo_obj.numero = condo['numero']
                    updated = True

                if condo.get('complemento') and condo_obj.complemento != condo['complemento']:
                    condo_obj.complemento = condo['complemento']
                    updated = True

                if condo.get('bairro') and condo_obj.bairro != condo['bairro']:
                    condo_obj.bairro = condo['bairro']
                    updated = True

                if condo.get('cidade') and condo_obj.cidade != condo['cidade']:
                    condo_obj.cidade = condo['cidade']
                    updated = True

                if condo.get('estado') and condo_obj.estado != condo['estado']:
                    condo_obj.estado = condo['estado']
                    updated = True

                if condo.get('cep') and condo_obj.cep != condo['cep']:
                    condo_obj.cep = condo['cep']
                    updated = True

                if updated:
                    condos_to_update.append(condo_obj)
        
        if condos_to_create:
            Condominio.objects.bulk_create(condos_to_create, ignore_conflicts=True)
            for c in condos_to_create:
                existing_condos[c.cnpj] = c
            logger.info(f"Criados {len(condos_to_create)} novos condomínios")

        if condos_to_update:
            Condominio.objects.bulk_update(
                condos_to_update,
                ['nome', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep', 'is_searched']
            )
            logger.info(f"Atualizados {len(condos_to_update)} condomínios existentes")
        
        # ========== 8. CRIAR/ATUALIZAR FUNCIONÁRIOS COM VÍNCULO (CORREÇÃO PRINCIPAL) ==========
        funcs_to_create = []
        funcs_to_update = []
        
        def _normalize_date(val):
            if val is None:
                return None
            val_str = str(val)
            invalid_dates = {'0001-01-01', '0000-00-00', '0020-00-00', '1900-01-01'}
            if val_str in invalid_dates or val_str.startswith('000') or val_str == '00-00-0000':
                return None
            return val_str if val_str else None
        
        for c in condominios_data:
            condo_obj = existing_condos.get(c['cnpj'])
            if not condo_obj:
                logger.warning(f"Condomínio não encontrado para CNPJ: {c['cnpj']}")
                continue
                
            for f in c.get('funcionarios', []):
                cpf_normalizado = f['cpf']
                
                # Validar CPF
                if len(cpf_normalizado) != 11:
                    logger.warning(f"CPF inválido para {f.get('nome')}: {cpf_normalizado}")
                    continue
                
                # Normalizar data de nascimento
                data_nascimento = f.get('data_nascimento')
                if isinstance(data_nascimento, str):
                    val = data_nascimento.strip()
                    if val:
                        formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d']
                        parsed = None
                        for fmt in formats:
                            try:
                                parsed = datetime.strptime(val, fmt).date()
                                break
                            except ValueError:
                                continue
                        data_nascimento = parsed
                    else:
                        data_nascimento = None
                elif not data_nascimento:
                    data_nascimento = None
                
                if cpf_normalizado not in existing_funcs:
                    # CRIAR novo funcionário com vínculo
                    funcs_to_create.append(Funcionario(
                        cpf=cpf_normalizado,
                        nome=(f.get('nome') or '')[:255],
                        matricula=(f.get('matricula') or '')[:50],
                        funcao=(f.get('funcao') or '')[:100],
                        data_nascimento=data_nascimento,
                        departamento=(f.get('departamento') or c['nome'])[:255],
                        condominio=condo_obj,
                        cep=(f.get('cep') or '')[:10],
                        endereco_rua=(f.get('endereco_rua') or '')[:255],
                        endereco_numero=(f.get('endereco_numero') or '')[:20],
                        endereco_complemento=(f.get('endereco_complemento') or '')[:100],
                        endereco_bairro=(f.get('endereco_bairro') or '')[:100]
                    ))
                    logger.info(f"Preparado para criar funcionário {(f.get('nome') or '')} vinculado a {condo_obj.nome}")
                else:
                    # ATUALIZAR funcionário existente
                    func_obj = existing_funcs[cpf_normalizado]
                    updated = False
                    
                    # Atualizar condomínio (vinculação)
                    if func_obj.condominio != condo_obj:
                        func_obj.condominio = condo_obj
                        updated = True
                        logger.info(f"Vinculando {func_obj.nome} ao condomínio {condo_obj.nome}")
                    
                    # Atualizar departamento se vazio
                    if not func_obj.departamento and f.get('departamento'):
                        func_obj.departamento = f['departamento'][:255]
                        updated = True
                    elif not func_obj.departamento:
                        func_obj.departamento = c['nome'][:255]
                        updated = True
                    
                    # Atualizar endereço se vazio
                    if not func_obj.cep and f.get('cep'):
                        func_obj.cep = f['cep'][:10]
                        updated = True
                    
                    # Atualizar função se vazia
                    if not func_obj.funcao and f.get('funcao'):
                        func_obj.funcao = f['funcao'][:100]
                        updated = True
                    
                    # Atualizar data de nascimento se vazia
                    if not func_obj.data_nascimento and data_nascimento:
                        func_obj.data_nascimento = data_nascimento
                        updated = True
                    
                    if updated:
                        funcs_to_update.append(func_obj)
        
        # Criar novos funcionários
        if funcs_to_create:
            try:
                Funcionario.objects.bulk_create(funcs_to_create, ignore_conflicts=True)
                for f in funcs_to_create:
                    existing_funcs[f.cpf] = f
                logger.info(f"Criados {len(funcs_to_create)} novos funcionários com vínculo")
            except Exception as e:
                logger.error(f"Erro ao criar funcionários: {e}")
                for func in funcs_to_create:
                    try:
                        func.save()
                        existing_funcs[func.cpf] = func
                        logger.info(f"Criado funcionário {func.nome} via fallback")
                    except Exception as e2:
                        logger.error(f"Erro ao criar {func.nome}: {e2}")

        if funcs_to_update:
            try:
                Funcionario.objects.bulk_update(
                    funcs_to_update, 
                    ['condominio', 'departamento', 'cep', 'funcao', 'data_nascimento']
                )
                logger.info(f"Atualizados {len(funcs_to_update)} funcionários existentes")
            except Exception as e:
                logger.error(f"Erro ao atualizar funcionários: {e}")
                for func in funcs_to_update:
                    try:
                        func.save(update_fields=['condominio', 'departamento', 'cep', 'funcao', 'data_nascimento'])
                        logger.info(f"Atualizado funcionário {func.nome} via fallback")
                    except Exception as e2:
                        logger.error(f"Erro ao atualizar {func.nome}: {e2}")
        
        # ========== 9. CRIAR PRODUTOS QUE NÃO EXISTEM ==========
        prod_map = {}
        for key, nome in produtos_raw:
            if key not in prod_map:
                prod_map[key] = nome
        
        prods_to_create = []
        for key, nome in prod_map.items():
            if key not in existing_prods:
                prods_to_create.append(Produto(codigo_produto=key, nome=nome[:255]))
        
        if prods_to_create:
            Produto.objects.bulk_create(prods_to_create, ignore_conflicts=True)
            for p in prods_to_create:
                existing_prods[p.codigo_produto] = p
            logger.info(f"Criados {len(prods_to_create)} novos produtos")
        
        # ========== 10. CRIAR VÍNCULOS CONDOMÍNIO-ADMINISTRADORA ==========
        existing_vinculos = set(VinculoCondominio.objects.filter(
            administradora=administradora, condominio_id__in=cnpj_list
        ).values_list('condominio_id', flat=True))
        condos_to_vinc = [c for c in cnpj_list if c and c not in existing_vinculos]
        if condos_to_vinc:
            vinculos = [VinculoCondominio(administradora=administradora, condominio_id=c) for c in condos_to_vinc]
            VinculoCondominio.objects.bulk_create(vinculos, ignore_conflicts=True)
            logger.info(f"Criados {len(vinculos)} vínculos condomínio-administradora")
        
        # ========== 11-13. CRIAR IMPORTAÇÃO + MOVIMENTAÇÕES + ESTATÍSTICAS (ATÔMICO) ==========
        movimentacoes_to_create = []
        registros_count = 0

        logger.info(f"Preparando movimentações para {len(condominios_data)} condomínios, "
                     f"{len(existing_condos)} condos no DB, {len(existing_funcs)} funcionários no DB")

        for condo_data in condominios_data:
            condo_obj = existing_condos.get(condo_data['cnpj'])
            if not condo_obj:
                logger.warning(f"Condomínio CNPJ {condo_data['cnpj']} não encontrado no DB após criação/recarga")
                continue
                
            for func_data in condo_data.get('funcionarios', []):
                func_obj = existing_funcs.get(func_data['cpf'])
                if not func_obj:
                    logger.warning(f"Funcionário não encontrado: {func_data.get('cpf')}")
                    continue
                
                movimentacoes_fonte = func_data.get('movimentacoes', [])
                
                for mov_data in movimentacoes_fonte:
                    codigo_produto = (mov_data.get('codigo_produto') or '').strip() or (mov_data.get('codigo') or '').strip()
                    if not codigo_produto:
                        codigo_produto = (mov_data.get('produto') or '').strip()[:50] or 'SEM_PRODUTO'
                    valor_beneficio = Decimal(str(mov_data.get('valor', 0)))
                    
                    if valor_beneficio == 0:
                        continue
                    
                    prod_obj = existing_prods.get(codigo_produto)
                    if not prod_obj and codigo_produto:
                        prod_obj, created = Produto.objects.get_or_create(
                            codigo_produto=codigo_produto,
                            defaults={'nome': mov_data.get('produto', '') or codigo_produto}
                        )
                        if created:
                            existing_prods[codigo_produto] = prod_obj
                            logger.info(f"Criado novo produto: {codigo_produto}")
                    
                    if not prod_obj:
                        logger.warning(f"Produto não encontrado para código: {codigo_produto}")
                        continue
                    
                    movimentacoes_to_create.append(MovimentacaoBeneficio(
                        importacao=None,
                        empresa_cnpj=condo_obj,
                        funcionario_cpf=func_obj,
                        produto_codigo=prod_obj,
                        data_competencia=data_competencia,
                        valor_beneficio=valor_beneficio,
                        quantidade_dias=mov_data.get('quantidade', 1)
                    ))
                    registros_count += 1

        movimentacoes_salvas = 0

        with transaction.atomic():
            arquivo_s3_url = None
            if file_upload_id:
                try:
                    arquivo_s3_url = FileUpload.objects.filter(id=file_upload_id).values_list('arquivo_s3', flat=True).first()
                except Exception:
                    pass

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
                data_recebimento=validated_data.get('data_recebimento'),
                vigencia_inicio=validated_data.get('vigencia_inicio') or validated_data.get('periodo_inicio'),
                vigencia_fim=validated_data.get('vigencia_fim') or validated_data.get('periodo_fim'),
                modelo_importacao=modelo_importacao,
                arquivo_s3=arquivo_s3_url
            )

            if movimentacoes_to_create:
                for mov in movimentacoes_to_create:
                    mov.importacao = importacao

                try:
                    result = MovimentacaoBeneficio.objects.bulk_create(
                        movimentacoes_to_create,
                        ignore_conflicts=True,
                        batch_size=500
                    )
                    movimentacoes_salvas = len(result)
                    logger.info(f"Salvas {movimentacoes_salvas} movimentações via bulk_create")
                except Exception as e:
                    logger.error(f"Erro no bulk_create: {e}", exc_info=True)
                    for mov in movimentacoes_to_create:
                        try:
                            mov.save()
                            movimentacoes_salvas += 1
                        except Exception as e2:
                            logger.error(f"Erro ao salvar individual: {e2}", exc_info=True)
            else:
                logger.warning("Nenhuma movimentação para salvar")

            if movimentacoes_salvas == 0:
                raise serializers.ValidationError(
                    "Nenhuma movimentação foi registrada. Verifique os dados do arquivo e tente novamente."
                )

            importacao.total_registros = registros_count
            importacao.registros_processados = movimentacoes_salvas
            importacao.save()

            # ========== 14. ATUALIZAR FILEUPLOAD (DENTRO DA MESMA TRANSAÇÃO) ==========
            try:
                FileUpload.objects.filter(id=file_upload_id).update(
                    process_status='AGUARDANDO_FATURAMENTO',
                    summary_data=summary
                )
                logger.info(f"FileUpload {file_upload_id} atualizado para AGUARDANDO_FATURAMENTO")
            except FileUpload.DoesNotExist:
                logger.warning(f"FileUpload {file_upload_id} não encontrado")
        
        # ========== 15. LOG FINAL ==========
        logger.info(f"Importação {importacao.id} concluída. "
                    f"Funcionários criados/atualizados: {len(funcs_to_create)}/{len(funcs_to_update)}. "
                    f"Movimentações: {movimentacoes_salvas}/{registros_count}")
        
        return {
            "count": movimentacoes_salvas,
            "status": "AGUARDANDO_FATURAMENTO",
            "importacao_id": importacao.id,
            "valor_total": float(valor_total_payload),
            "funcionarios_criados": len(funcs_to_create),
            "funcionarios_atualizados": len(funcs_to_update),
            "cartao_admin": administradora.cartao_admin if administradora else None,
        }

class FaturamentoExportSerializer(serializers.Serializer):
    CPF = serializers.CharField()
    NOME_FUNC = serializers.CharField()
    PRODUTO = serializers.CharField()
    BENEFICIO = serializers.CharField()
    VALOR_UNITARIO = serializers.DecimalField(max_digits=10, decimal_places=2)
    QUANTIDADE = serializers.IntegerField()
    VALOR_RECARGA_BENE = serializers.DecimalField(max_digits=15, decimal_places=2)
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
    
class VTCofirmationSerializer(serializers.Serializer):
    file_upload_id = serializers.IntegerField(required=True)
    summary = serializers.DictField(required=False)
    dados_validados = serializers.ListField(required=False)
    status = serializers.CharField(required=False, default='VALIDATED')
    detail = serializers.CharField(required=False)
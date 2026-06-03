import logging
import re
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import transaction
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)

class ConfirmVTView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data
        logger.info(f"ConfirmVTView - Recebido payload: {payload}")
        
        file_id = payload.get("file_upload_id")
        administradora_id = payload.get("administradora_id")
        
        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)
        
        try:
            from .models import FileUpload
            from beneficios.models import Importacao, MovimentacaoBeneficio
            from entidades.models import Condominio, Funcionario, VinculoCondominio
            from beneficios.models import Produto
            
            file_upload = FileUpload.objects.get(id=file_id)
            
            # Obtém os dados do payload
            dados_validados = payload.get("dados_validados", [])
            summary = payload.get("summary", {})
            
            if not dados_validados:
                return Response({"detail": "Nenhum dado validado para processar."}, status=400)
            
            # Agrupa por funcionário para criar/atualizar cadastros
            funcionarios_map = {}
            for item in dados_validados:
                cpf = item.get("cpf_funcionario", "")
                if cpf not in funcionarios_map:
                    funcionarios_map[cpf] = {
                        "nome": item.get("nome_funcionario", ""),
                        "cpf": cpf,
                        "condominio": item.get("nome_condominio", ""),
                        "cnpj_condominio": item.get("cnpj_condominio", ""),
                        "matricula": item.get("matricula_funcionario", ""),
                        "funcao": item.get("funcao_funcionario", ""),
                        "valor_total": 0,
                        "quantidade_dias": 0,
                        "movimentacoes": []
                    }
                
                funcionarios_map[cpf]["valor_total"] += float(item.get("valor_beneficio_total", 0))
                funcionarios_map[cpf]["quantidade_dias"] += int(item.get("quantidade_dias", 0))
                funcionarios_map[cpf]["movimentacoes"].append(item)
            
            # Busca ou cria administradora
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            administradora = None
            if administradora_id:
                from entidades.models import Administradora
                try:
                    administradora = Administradora.objects.get(id=administradora_id)
                except:
                    pass
            
            if not administradora and request.user:
                administradora = getattr(request.user, 'administradora', None)
            
            if not administradora:
                return Response({"detail": "Administradora não encontrada."}, status=400)
            
            # Processa condomínios e funcionários
            with transaction.atomic():
                # Data de competência
                competencia_mes = payload.get("competencia_mes", str(datetime.now().month).zfill(2))
                competencia_ano = payload.get("competencia_ano", str(datetime.now().year))
                data_competencia = date(int(competencia_ano), int(competencia_mes), 1)
                
                # Cria a importação
                importacao = Importacao.objects.create(
                    file_upload_id=file_id,
                    usuario=request.user,
                    administradora=administradora,
                    status='AGUARDANDO_FATURAMENTO',
                    total_registros=len(dados_validados),
                    registros_processados=0,
                    valor_total=Decimal(str(summary.get("valor_total_beneficios", 0))),
                    total_funcionarios=len(funcionarios_map),
                    data_vencimento=payload.get("vencimento"),
                    vigencia_inicio=payload.get("periodo_inicio"),
                    vigencia_fim=payload.get("periodo_fim"),
                    modelo_importacao="VT-AUTO"
                )
                
                movimentacoes_salvas = 0
                
                for cpf, func_data in funcionarios_map.items():
                    # Busca ou cria condomínio
                    cnpj_condo = re.sub(r'[^0-9]', '', func_data["cnpj_condominio"])[:14]
                    condominio, _ = Condominio.objects.get_or_create(
                        cnpj=cnpj_condo if cnpj_condo else f"000{cpf[:10]}",
                        defaults={"nome": func_data["condominio"][:255]}
                    )
                    
                    # Busca ou cria funcionário
                    funcionario, created = Funcionario.objects.get_or_create(
                        cpf=cpf,
                        defaults={
                            "nome": func_data["nome"][:255],
                            "matricula": func_data["matricula"][:50],
                            "funcao": func_data["funcao"][:100],
                            "condominio": condominio,
                            "departamento": func_data["condominio"][:255]
                        }
                    )
                    
                    if not created and funcionario.condominio != condominio:
                        funcionario.condominio = condominio
                        funcionario.save()
                    
                    # Cria vínculo condomínio-administradora
                    VinculoCondominio.objects.get_or_create(
                        administradora=administradora,
                        condominio=condominio
                    )
                    
                    # Cria movimentações
                    for mov in func_data["movimentacoes"]:
                        # Busca ou cria produto
                        codigo_produto = mov.get("codigo_produto", "VT")
                        produto, _ = Produto.objects.get_or_create(
                            codigo_produto=codigo_produto,
                            defaults={"nome": "Vale Transporte"}
                        )
                        
                        MovimentacaoBeneficio.objects.create(
                            importacao=importacao,
                            empresa_cnpj=condominio,
                            funcionario_cpf=funcionario,
                            produto_codigo=produto,
                            data_competencia=data_competencia,
                            valor_beneficio=Decimal(str(mov.get("valor_beneficio_total", 0))),
                            quantidade_dias=mov.get("quantidade_dias", 0)
                        )
                        movimentacoes_salvas += 1
                
                importacao.registros_processados = movimentacoes_salvas
                importacao.save()
                
                file_upload.process_status = "COMPLETED"
                file_upload.save()
                
            return Response({
                "detail": "Dados de Vale Transporte salvos com sucesso.",
                "status": "COMPLETED",
                "importacao_id": importacao.id,
                "total_registros": movimentacoes_salvas
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro ao salvar VT: {str(e)}", exc_info=True)
            return Response({"detail": f"Erro ao processar: {str(e)}"}, status=500)
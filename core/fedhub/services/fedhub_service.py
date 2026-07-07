# core/fedhub/service/fedhub_service.py

from django.utils import timezone
from typing import Any, Dict
import httpx
import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.template.loader import render_to_string
import requests

from core.fedhub.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        self.base_url = settings.FEDHUB_URL
        # self.base_url = 'http://localhost:8090'  # URL local para desenvolvimento

    # Emails
    # Método para enviar email de notificação de upload de faturamento/compra
    def enviar_email_upload(self, email: str, user: Any, dados_processamento: Dict = None) -> bool:
        """
        Envia email de notificação de upload de faturamento/compra.
        
        Args:
            email: Email do destinatário
            user: Usuário autenticado
            dados_processamento: Dicionário com os dados do processamento
        """
        try:
            if dados_processamento is None:
                dados_processamento = {}
            
            # Prepara o contexto para o template
            context = {
                'user': user,
                'FRONTEND_URL': settings.FRONTEND_URL,
                'arquivo_nome': dados_processamento.get('arquivo_nome', 'faturamento.xlsx'),
                'data_envio': dados_processamento.get('data_envio', timezone.now().strftime('%d/%m/%Y %H:%M')),
                'competencia': dados_processamento.get('competencia', '—'),
                'total_registros': dados_processamento.get('total_registros', 0),
                'total_funcionarios': dados_processamento.get('total_funcionarios', 0),
                'total_condominios': dados_processamento.get('total_condominios', 0),
                'valor_total': dados_processamento.get('valor_total', 0),
                'tipo_processamento': dados_processamento.get('tipo_processamento', 'Compra de Benefícios'),
                'faturamento_id': dados_processamento.get('faturamento_id'),
                'vencimento': dados_processamento.get('vencimento', ''),
                'periodo_inicio': dados_processamento.get('periodo_inicio', ''),
                'periodo_fim': dados_processamento.get('periodo_fim', ''),
            }
            
            # Formata o valor total como moeda
            if context['valor_total']:
                context['valor_total_formatado'] = f"R$ {context['valor_total']:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
            else:
                context['valor_total_formatado'] = "R$ 0,00"
            
            # Renderiza o template HTML com os dados
            html_body = render_to_string(
                'email/upload_faturamento.html',
                context
            )
            
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": f"{context['tipo_processamento']} - Fedhub",
                        "body": html_body,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email}")
                    return True
                else:
                    logger.error(f"Gateway retornou erro {response.status_code}: {response.text}")
                    return False

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar email: {e}")
            return False
    
    def enviar_email_cliente_faturamento(self, email: str, user: Any, dados_processamento: Dict = None) -> bool:
        """
        Envia email de notificação de faturamento concluído para o cliente final.
        
        Args:
            email: Email do destinatário (cliente final)
            user: Usuário autenticado (administradora)
            dados_processamento: Dicionário com os dados do faturamento
        """
        try:
            if dados_processamento is None:
                dados_processamento = {}
            
            # Prepara o contexto para o template
            context = {
                'user': user,
                'cliente_nome': dados_processamento.get('cliente_nome', 'Cliente'),
                'cliente_email': dados_processamento.get('cliente_email', email),
                'FRONTEND_URL': settings.FRONTEND_URL,
                'arquivo_nome': dados_processamento.get('arquivo_nome', 'faturamento.xlsx'),
                'data_faturamento': dados_processamento.get('data_faturamento', timezone.now().strftime('%d/%m/%Y %H:%M')),
                'competencia': dados_processamento.get('competencia', '—'),
                'total_registros': dados_processamento.get('total_registros', 0),
                'total_funcionarios': dados_processamento.get('total_funcionarios', 0),
                'total_condominios': dados_processamento.get('total_condominios', 0),
                'valor_total': dados_processamento.get('valor_total', 0),
                'tipo_processamento': 'Faturamento Concluído',
                'faturamento_id': dados_processamento.get('faturamento_id'),
                'vencimento': dados_processamento.get('vencimento', ''),
                'periodo_inicio': dados_processamento.get('periodo_inicio', ''),
                'periodo_fim': dados_processamento.get('periodo_fim', ''),
                'numero_nota_fiscal': dados_processamento.get('numero_nota_fiscal', ''),
                'link_boleto': dados_processamento.get('link_boleto', ''),
                'link_nota_fiscal': dados_processamento.get('link_nota_fiscal', ''),
            }
            
            # Formata o valor total como moeda
            if context['valor_total']:
                context['valor_total_formatado'] = f"R$ {context['valor_total']:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
            else:
                context['valor_total_formatado'] = "R$ 0,00"
            
            # Renderiza o template HTML com os dados
            html_body = render_to_string(
                'email/faturamento_concluido_cliente.html',  # Novo template para cliente
                context
            )
            
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": f"Faturamento Concluído - FedHub - {context['competencia']}",
                        "body": html_body,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Email de faturamento enviado para cliente: {email}")
                    return True
                else:
                    logger.error(f"Gateway retornou erro {response.status_code}: {response.text}")
                    return False

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar email de faturamento: {e}")
            return False
    
    
    
        # Email
        
    def enviar_email_recuperacao_senha(self, email: str, user: Any) -> bool:
        try:
            with httpx.Client() as client:

                # 🔐 Gerar NOVO token (sobrescreve o anterior)
                reset_token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timedelta(hours=24)

                # SOBRESCREVE o token anterior (se existir)
                user.reset_password_token = reset_token
                user.reset_password_token_created_at = timezone.now()
                user.reset_password_token_expires_at = expires_at
                user.save(
                    update_fields=[
                        "reset_password_token",
                        "reset_password_token_created_at",
                        "reset_password_token_expires_at",
                    ]
                )

                logger.info(
                    f"Novo token gerado (sobrescreveu anterior) para: {user.email}"
                )
                logger.info(f"Token expira em: {expires_at}")

                frontend_url = settings.FRONTEND_URL

                # Construir link de reset
                reset_url = f"{frontend_url}/resetar-senha/{reset_token}"

                logger.info(f"Link de reset gerado: {reset_url}")

                html_body = render_to_string(
                    "email/resetar_senha.html",
                    {
                        "nome_usuario": user.nome or user.email,
                        "reset_url": reset_url,
                    },
                )

                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": "Redefinição de Senha - FedHub - Benefícios",
                        "body": html_body,
                        "is_html": True,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email}")
                else:
                    logger.error(
                        f"Gateway retornou erro {response.status_code}: {response.text}"
                    )

            return True

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False
    
    def enviar_email_usuario_criado(self, email: str, user: Any, senha_temporaria: str, dados_usuario: Dict = None) -> bool:
        """
        Envia email de boas-vindas para novo usuário com suas credenciais de acesso.
        
        Args:
            email: Email do destinatário (usuário criado)
            user: Usuário criado
            senha_temporaria: Senha temporária gerada
            dados_usuario: Dicionário com dados adicionais do usuário
        """
        try:
            if dados_usuario is None:
                dados_usuario = {}
            
            # Prepara o contexto para o template
            context = {
                'user_email': email,
                'user_nome': user.nome or user.email.split('@')[0],
                'temporary_password': senha_temporaria,
                'portal_url': f"{settings.FRONTEND_URL}/login",
                'manual_url': f"{settings.BASE_URL_AWS_S3_FEDCORP_MEDIA}/manual_fedcorp.docx",
                'logo_url': f"{settings.BASE_URL_AWS_S3_FEDCORP_MEDIA}/LOGO1.png",
                'badge_text': '🚀 Seu acesso já está disponível',
                'hero_title': 'Bem-vindo ao',
                'hero_description': f'Olá {user.nome or user.email.split("@")[0]}! Seu acesso ao FedHub está liberado. Centralize importações, faturamento e gestão dos seus benefícios em uma única plataforma moderna, segura e intuitiva.',
                'security_message': 'Por segurança, altere sua senha no primeiro acesso. Essa senha é temporária e deve ser substituída por uma senha pessoal.',
                'FRONTEND_URL': settings.FRONTEND_URL,
            }
            
            # Renderiza o template HTML com os dados
            html_body = render_to_string(
                'email/usuario_criado.html',
                context
            )
            
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": f"Bem-vindo ao FedHub - Suas credenciais de acesso",
                        "body": html_body,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Email de boas-vindas enviado com sucesso para: {email}")
                    return True
                else:
                    logger.error(f"Gateway retornou erro {response.status_code}: {response.text}")
                    return False

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar email de boas-vindas: {e}")
            return False
    
    # Administradoras
    def buscar_administradoras(self):
            try:
                response = requests.get(
                    f"{self.base_url}/api/administradoras/",
                    timeout=30,
                    headers=get_headers()
                )

                if response.status_code != 200:
                    logger.error(f"Firebird erro {response.status_code}")
                    return None

                data = response.json()

                if data.get("status") != "success":
                    return None

                return data.get("data")

            except requests.RequestException as e:
                logger.error(f"Erro ao chamar Firebird: {e}")
                return None
            
    def buscar_administradora_por_nome(self, nome: str):
            try:
                logger.info(f"Endpoint de chamada: {f'{self.base_url}/api/administradoras/por-nome/{nome}'}")
                response = requests.get(
                    f"{self.base_url}/api/administradoras/por-nome/{nome}",
                    timeout=30,
                    headers=get_headers()
                )

                if response.status_code != 200:
                    logger.error(f"Firebird erro {response.status_code}")
                    return None

                data = response.json()

                if data.get("status") != "success":
                    return None

                return data.get("data")

            except requests.RequestException as e:
                logger.error(f"Erro ao chamar Firebird: {e}")
                return None

    def buscar_administradora_por_cnpj(self, cnpj: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/unica-por-cnpj/{cnpj}",
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None
        
    def buscar_pessoa_por_cnpj(self, cnpj: str):
        try:
            logger.info(f"Endpoint de chamada: {f'{self.base_url}/api/pessoas/cnpj/{cnpj}'}")
            response = requests.get(
                f"{self.base_url}/api/pessoas/cnpj/{cnpj}",
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()
            
            # logger.info(f"Dados retornados do serviço de pessoas por CNPJ: {data}")

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_dados_boleto_por_fatura(self, fatura: str):
        """
        Busca os dados do boleto/faturamento no Fedhub pelo número da fatura.
        Retorna um dicionário com os dados do boleto ou None se não encontrado.
        """
        try:
            logger.info(f"Chamando Fedhub para buscar dados do boleto da fatura {fatura}")
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/boletos-bancarios/{fatura}",
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Erro ao buscar dados do boleto no Fedhub: {response.status_code}")
                return None

            data = response.json()
            if isinstance(data, dict):
                if data.get("status") == "success" and "data" in data:
                    boletos = data.get("data")
                    if isinstance(boletos, list):
                        return boletos[0] if len(boletos) > 0 else {}
                    return boletos
                return data
            return None

        except requests.RequestException as e:
            logger.error(f"Erro de conexão com o Fedhub: {e}")
            return None

    def buscar_todos_boletos_por_fatura(self, fatura: str):
        """
        Busca todos os boletos/faturamentos no Fedhub pelo número da fatura.
        Retorna uma lista com os dados de todos os boletos ou uma lista vazia.
        """
        try:
            logger.info(f"Chamando Fedhub para buscar todos os boletos da fatura {fatura}")
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/boletos-bancarios/{fatura}",
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Erro ao buscar todos os boletos no Fedhub: {response.status_code}")
                return []

            data = response.json()
            if isinstance(data, dict) and data.get("status") == "success" and "data" in data:
                boletos = data.get("data")
                if isinstance(boletos, list):
                    return boletos
                elif isinstance(boletos, dict):
                    return [boletos]
            return []

        except requests.RequestException as e:
            logger.error(f"Erro de conexão com o Fedhub ao buscar todos os boletos: {e}")
            return []

    def enviar_email_erro_nota(self, email_destinatario: str, faturamento_id: str, cnpj_cobrado: str, id_integracao: str, motivo_erro: str = "Erro na emissão") -> bool:
        """
        Envia e-mail de alerta de erro de nota fiscal para o faturista.
        """
        try:
            # Prepara o contexto para o template
            context = {
                'faturamento_id': faturamento_id,
                'cnpj_cobrado': cnpj_cobrado,
                'id_integracao': id_integracao,
                'motivo_erro': motivo_erro,
                'data_erro': timezone.now().strftime('%d/%m/%Y %H:%M'),
            }
            
            # Renderiza o template HTML
            html_body = render_to_string(
                'email/erro_emissao_nota.html',
                context
            )
            
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email_destinatario,
                        "subject": f"ALERTA: Falha na Emissão de NFS-e (Faturamento #{faturamento_id})",
                        "body": html_body,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"E-mail de alerta de erro enviado para: {email_destinatario}")
                    return True
                else:
                    logger.error(f"Gateway de e-mail retornou erro {response.status_code}: {response.text}")
                    return False

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar serviço de e-mail para erro de nota: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar e-mail de erro de nota: {e}")
            return False

    
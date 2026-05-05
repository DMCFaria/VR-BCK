# core/fedhub/service/fedhub_service.py

from django.utils import timezone
from typing import Any, Dict
import httpx
import logging

from django.conf import settings
from django.template.loader import render_to_string
import requests

from core.fedhub.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        self.base_url = settings.FEDHUB_URL

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
                        "subject": f"{context['tipo_processamento']} - FedVR",
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

    
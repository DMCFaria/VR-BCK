# consultas/services/firebird.py

from datetime import timedelta
from datetime import timedelta
import secrets
from django.utils import timezone
from typing import Any, Dict, List, Optional
import httpx
import requests
import logging

from rest_framework import settings

from django.conf import settings
from django.template.loader import render_to_string

from core.fedhub.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        self.base_url = settings.FEDHUB_URL
        # self.base_url = "http://localhost:8090"

    # Email
    def enviar_email_upload(self, email: str, user: Any) -> bool:
        try:
            with httpx.Client() as client:
                                
                html_body = render_to_string(
                    'email/upload_faturamento.html',
                    {
                        'user': user,
                        'FRONTEND_URL': settings.FRONTEND_URL,
                        'arquivo_nome': 'faturamento.xlsx',
                        'data_envio': timezone.now().strftime('%d/%m/%Y %H:%M'),
                        'competencia': '05/2026',
                        'total_registros': 123,
                        'faturamento_id': 1,
                    }
                )
                
                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": "Upload de Faturamento - FedVR",
                        "body": html_body,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email}")
                else:
                    logger.error(f"Gateway retornou erro {response.status_code}: {response.text}")

            return True

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False
   
# core/fedhub/utils/fedhub_auth.py
#
# Bearer token do FedHub (client credentials) com cache thread-safe e
# renovação automática. Fail-open durante a migração: se a emissão do
# token falhar, os headers seguem apenas com a X-Application-Key legada
# (que o FedHub aceita em modo sombra) — nenhuma chamada quebra.
#
# Envs novas: FEDHUB_CLIENT_ID / FEDHUB_CLIENT_SECRET. Sem elas, o
# comportamento é exatamente o de hoje (só a chave legada).

import logging
import threading
import time

import requests
from decouple import config

logger = logging.getLogger(__name__)

_MARGEM_RENOVACAO = 60  # renova 60s antes de expirar


class FedHubAuth:
    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self._expira_em = 0.0

    def _renovar(self) -> None:
        base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")
        resposta = requests.post(
            f"{base_url}/api/auth/token",
            json={
                "client_id": config("FEDHUB_CLIENT_ID", default=""),
                "client_secret": config("FEDHUB_CLIENT_SECRET", default=""),
            },
            timeout=10,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        self._token = dados["access_token"]
        self._expira_em = time.time() + dados.get("expires_in", 3600) - _MARGEM_RENOVACAO

    def token(self) -> str | None:
        if not config("FEDHUB_CLIENT_ID", default=""):
            return None
        with self._lock:
            if self._token is None or time.time() >= self._expira_em:
                try:
                    self._renovar()
                except Exception as e:
                    logger.warning(f"FedHub auth: falha ao obter token ({e}); usando só a chave legada")
                    self._token = None
        return self._token


_auth = FedHubAuth()


def bearer_token() -> str | None:
    """Token válido (cacheado) ou None se indisponível/não configurado."""
    return _auth.token()

from typing import Dict

from decouple import config

from core.fedhub.utils.fedhub_auth import bearer_token


def get_headers() -> Dict:
    """Headers padrão para todas as requisições ao FedHub.

    Durante a migração enviam as duas credenciais: o bearer token novo
    (renovável, com escopos) e a X-Application-Key legada. Se o token não
    estiver disponível, a chave legada sozinha continua funcionando.
    """
    headers = {
        "X-Application-Key": config("FEDHUB_X_API_KEY", default=""),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    token = bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

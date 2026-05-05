from typing import Dict
from decouple import config

def get_headers() -> Dict:
        """
        Retorna headers padrão para todas as requisições
        """
        headers = {
            "X-Application-Key": config("FEDHUB_X_API_KEY", default=""),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
        return headers
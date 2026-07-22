import logging
import re

import requests

logger = logging.getLogger(__name__)


class CNPJConsultaService:
    """
    Serviço para consulta pública de dados de CNPJ.

    Hoje utiliza BrasilAPI como fonte principal. A estrutura permite
    adicionar fontes alternativas (ex: BigDataCorp) no futuro com fallback.
    """

    @staticmethod
    def _limpar_cnpj(cnpj):
        return re.sub(r"\D", "", str(cnpj or "")).zfill(14)[:14]

    @classmethod
    def consultar(cls, cnpj, fonte="brasilapi"):
        """
        Consulta dados de um CNPJ.

        Args:
            cnpj: CNPJ com ou sem formatação.
            fonte: Fonte da consulta. Padrão 'brasilapi'.

        Returns:
            dict: Dados normalizados do CNPJ ou None em caso de falha.
        """
        cnpj_limpo = cls._limpar_cnpj(cnpj)
        if len(cnpj_limpo) != 14:
            logger.warning(f"CNPJ inválido para consulta: {cnpj}")
            return None

        if fonte == "brasilapi":
            return cls._consultar_brasilapi(cnpj_limpo)

        logger.warning(f"Fonte de consulta desconhecida: {fonte}")
        return None

    @classmethod
    def _consultar_brasilapi(cls, cnpj_limpo):
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        try:
            logger.info(f"Consultando CNPJ {cnpj_limpo} na BrasilAPI")
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                logger.warning(f"CNPJ {cnpj_limpo} não encontrado na BrasilAPI")
                return None
            if response.status_code != 200:
                logger.error(
                    f"BrasilAPI retornou {response.status_code} para CNPJ {cnpj_limpo}: {response.text}"
                )
                return None

            dados = response.json()
            return cls._normalizar_dados(dados)
        except requests.RequestException as e:
            logger.error(f"Erro de rede ao consultar BrasilAPI para CNPJ {cnpj_limpo}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Erro inesperado ao consultar CNPJ {cnpj_limpo}: {e}")
            return None

    @classmethod
    def _normalizar_dados(cls, dados):
        """
        Normaliza a resposta da BrasilAPI para o formato usado no projeto.
        """
        if not dados or not isinstance(dados, dict):
            return None

        endereco = dados.get("descricao_tipo_de_logradouro", "")
        logradouro = dados.get("logradouro", "")
        if endereco and logradouro:
            rua = f"{endereco} {logradouro}".strip()
        else:
            rua = (endereco or logradouro or "").strip()

        numero = dados.get("numero", "")
        complemento = dados.get("complemento", "")
        bairro = dados.get("bairro", "")
        cidade = dados.get("municipio", "")
        estado = dados.get("uf", "")
        cep = re.sub(r"\D", "", str(dados.get("cep", "")))

        return {
            "cnpj": cls._limpar_cnpj(dados.get("cnpj", "")),
            "razao_social": dados.get("razao_social", ""),
            "nome_fantasia": dados.get("nome_fantasia", ""),
            "rua": rua,
            "numero": numero,
            "complemento": complemento,
            "bairro": bairro,
            "cidade": cidade,
            "estado": estado,
            "cep": cep,
            "situacao": dados.get("descricao_situacao_cadastral", ""),
        }

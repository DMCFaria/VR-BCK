import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class CNPJConsultaService:
    """
    Serviço para consulta de dados de CNPJ.

    Fonte principal: BigDataCorp (registration_data).
    Fallback: BrasilAPI.
    """

    @staticmethod
    def _limpar_cnpj(cnpj):
        return re.sub(r"\D", "", str(cnpj or "")).zfill(14)[:14]

    @classmethod
    def consultar(cls, cnpj, fonte="bigdatacorp_addresses"):
        """
        Consulta dados de um CNPJ.

        Args:
            cnpj: CNPJ com ou sem formatação.
            fonte: Fonte da consulta. Padrão 'bigdatacorp'.

        Returns:
            dict: Dados normalizados do CNPJ ou None em caso de falha.
        """
        cnpj_limpo = cls._limpar_cnpj(cnpj)
        if len(cnpj_limpo) != 14:
            logger.warning(f"CNPJ inválido para consulta: {cnpj}")
            return None

        if fonte == "bigdatacorp":
            dados = cls._consultar_bigdatacorp(cnpj_limpo)
            if dados:
                return dados
            logger.warning(f"BigDataCorp falhou para {cnpj_limpo}, tentando BrasilAPI fallback")
            return cls._consultar_brasilapi(cnpj_limpo)

        if fonte == "bigdatacorp_addresses":
            dados = cls._consultar_bigdatacorp_addresses(cnpj_limpo)
            if dados:
                return dados
            logger.warning(f"BigDataCorp addresses falhou para {cnpj_limpo}, tentando BrasilAPI fallback")
            return cls._consultar_brasilapi(cnpj_limpo)

        if fonte == "brasilapi":
            return cls._consultar_brasilapi(cnpj_limpo)

        logger.warning(f"Fonte de consulta desconhecida: {fonte}")
        return None

    @classmethod
    def _consultar_bigdatacorp(cls, cnpj_limpo):
        url = getattr(settings, "BIGDATA_URL", "https://plataforma.bigdatacorp.com.br/empresas")
        access_token = getattr(settings, "BIGDATA_ACCESS_TOKEN", "")
        token_id = getattr(settings, "BIGDATA_TOKEN_ID", "")

        if not access_token or not token_id:
            logger.error("BIGDATA_ACCESS_TOKEN ou BIGDATA_TOKEN_ID não configurados")
            return None

        headers = {
            "AccessToken": access_token,
            "TokenId": token_id,
            "accept": "application/json",
            "content-type": "application/json",
        }
        payload = {
            "Datasets": "registration_data",
            "q": f"doc{{{cnpj_limpo}}}",
            "Limit": 1,
        }

        try:
            logger.info(f"Consultando CNPJ {cnpj_limpo} na BigDataCorp (registration_data)")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code != 200:
                logger.error(
                    f"BigDataCorp retornou {response.status_code} para CNPJ {cnpj_limpo}: {response.text}"
                )
                return None

            data = response.json()
            if not data or not isinstance(data, dict):
                logger.warning(f"BigDataCorp retornou resposta inválida para {cnpj_limpo}")
                return None

            # Verifica erros no Status
            status = data.get("Status", {})
            if status:
                for dataset, erros in status.items():
                    if isinstance(erros, list):
                        for erro in erros:
                            if erro.get("Code", 0) != 0:
                                logger.warning(
                                    f"BigDataCorp erro no dataset {dataset} para {cnpj_limpo}: "
                                    f"{erro.get('Message')}"
                                )

            result = data.get("Result", [])
            if not result:
                logger.warning(f"BigDataCorp não retornou resultados para {cnpj_limpo}")
                return None

            return cls._normalizar_dados_bigdatacorp(result[0])
        except requests.RequestException as e:
            logger.error(f"Erro de rede ao consultar BigDataCorp para CNPJ {cnpj_limpo}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Erro inesperado ao consultar BigDataCorp para CNPJ {cnpj_limpo}: {e}")
            return None

    @classmethod
    def _consultar_bigdatacorp_addresses(cls, cnpj_limpo):
        """
        Consulta dados cadastrais (basic_data) e endereços (addresses_extended) de uma vez.
        O dataset addresses_extended é mais barato e traz vários endereços; basic_data traz
        o nome oficial para evitar abreviações preenchidas pelas administradoras.
        """
        url = getattr(settings, "BIGDATA_URL", "https://plataforma.bigdatacorp.com.br/empresas")
        access_token = getattr(settings, "BIGDATA_ACCESS_TOKEN", "")
        token_id = getattr(settings, "BIGDATA_TOKEN_ID", "")

        if not access_token or not token_id:
            logger.error("BIGDATA_ACCESS_TOKEN ou BIGDATA_TOKEN_ID não configurados")
            return None

        headers = {
            "AccessToken": access_token,
            "TokenId": token_id,
            "accept": "application/json",
            "content-type": "application/json",
        }
        payload = {
            "Datasets": "basic_data,addresses_extended",
            "q": f"doc{{{cnpj_limpo}}}",
            "Limit": 1,
        }

        try:
            logger.info(f"Consultando CNPJ {cnpj_limpo} na BigDataCorp (basic_data,addresses_extended)")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code != 200:
                logger.error(
                    f"BigDataCorp retornou {response.status_code} para CNPJ {cnpj_limpo}: {response.text}"
                )
                return None

            data = response.json()
            if not data or not isinstance(data, dict):
                logger.warning(f"BigDataCorp retornou resposta inválida para {cnpj_limpo}")
                return None

            status = data.get("Status", {})
            if status:
                for dataset, erros in status.items():
                    if isinstance(erros, list):
                        for erro in erros:
                            if erro.get("Code", 0) != 0:
                                logger.warning(
                                    f"BigDataCorp erro no dataset {dataset} para {cnpj_limpo}: "
                                    f"{erro.get('Message')}"
                                )

            result = data.get("Result", [])
            if not result:
                logger.warning(f"BigDataCorp não retornou resultados para {cnpj_limpo}")
                return None

            return cls._normalizar_dados_bigdatacorp_addresses(result[0], cnpj_limpo)
        except requests.RequestException as e:
            logger.error(f"Erro de rede ao consultar BigDataCorp para CNPJ {cnpj_limpo}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Erro inesperado ao consultar BigDataCorp para CNPJ {cnpj_limpo}: {e}")
            return None

    @classmethod
    def _normalizar_dados_bigdatacorp(cls, result):
        """
        Normaliza a resposta da BigDataCorp para o formato usado no projeto.
        """
        if not result or not isinstance(result, dict):
            return None

        registration = result.get("RegistrationData", {})
        basic = registration.get("BasicData", {})
        address = registration.get("Addresses", {}).get("Primary", {})

        cnpj = cls._limpar_cnpj(basic.get("TaxIdNumber", ""))
        razao_social = basic.get("OfficialName", "")
        nome_fantasia = basic.get("TradeName", "")
        situacao = basic.get("TaxIdStatus", "")

        rua = (address.get("AddressMain") or "").strip()
        numero = (address.get("Number") or "").strip()
        complemento = (address.get("Complement") or "").strip()
        bairro = (address.get("Neighborhood") or "").strip()
        cidade = (address.get("City") or "").strip()
        estado = (address.get("State") or "").strip()
        cep = re.sub(r"\D", "", str(address.get("ZipCode", "")))

        return {
            "cnpj": cnpj,
            "razao_social": razao_social,
            "nome_fantasia": nome_fantasia,
            "rua": rua,
            "numero": numero,
            "complemento": complemento,
            "bairro": bairro,
            "cidade": cidade,
            "estado": estado,
            "cep": cep,
            "situacao": situacao,
        }

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
            return cls._normalizar_dados_brasilapi(dados)
        except requests.RequestException as e:
            logger.error(f"Erro de rede ao consultar BrasilAPI para CNPJ {cnpj_limpo}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Erro inesperado ao consultar BrasilAPI para CNPJ {cnpj_limpo}: {e}")
            return None

    @classmethod
    def _normalizar_dados_bigdatacorp_addresses(cls, result, cnpj_limpo):
        """
        Normaliza a resposta combinada basic_data + addresses_extended da BigDataCorp.
        Seleciona o endereço principal (preferencialmente IsMainForEntity=True e IsActive=True).
        """
        if not result or not isinstance(result, dict):
            return None

        # Dados cadastrais (nome oficial/fantasia)
        basic = result.get("BasicData", {})
        razao_social = (basic.get("OfficialName") or "").strip()
        nome_fantasia = (basic.get("TradeName") or "").strip()
        situacao = (basic.get("TaxIdStatus") or "").strip()

        # Endereços
        extended = result.get("ExtendedAddresses", {})
        addresses = extended.get("Addresses", [])
        if not addresses:
            logger.warning(f"BigDataCorp addresses_extended não retornou endereços para {cnpj_limpo}")
            # Mesmo sem endereço, retornamos o nome para atualização
            return {
                "cnpj": cnpj_limpo,
                "razao_social": razao_social,
                "nome_fantasia": nome_fantasia,
                "rua": "",
                "numero": "",
                "complemento": "",
                "bairro": "",
                "cidade": "",
                "estado": "",
                "cep": "",
                "situacao": situacao,
            }

        # Ordena: principal ativo primeiro, depois principal, depois ativo, depois ordem original
        def _score(addr):
            score = 0
            if addr.get("IsMainForEntity"):
                score += 100
            if addr.get("IsActive"):
                score += 10
            if addr.get("AddressCurrentlyInRFSite"):
                score += 1
            return score

        addresses_sorted = sorted(addresses, key=_score, reverse=True)
        address = addresses_sorted[0]

        rua_parts = [p for p in [address.get("Typology", ""), address.get("AddressMain", "")] if p]
        rua = " ".join(rua_parts).strip()
        numero = (address.get("Number") or "").strip()
        complemento = (address.get("Complement") or "").strip()
        bairro = (address.get("Neighborhood") or "").strip()
        cidade = (address.get("City") or "").strip()
        estado = (address.get("State") or "").strip()
        cep = re.sub(r"\D", "", str(address.get("ZipCode", "")))

        return {
            "cnpj": cnpj_limpo,
            "razao_social": razao_social,
            "nome_fantasia": nome_fantasia,
            "rua": rua,
            "numero": numero,
            "complemento": complemento,
            "bairro": bairro,
            "cidade": cidade,
            "estado": estado,
            "cep": cep,
            "situacao": situacao,
        }

    @classmethod
    def _normalizar_dados_brasilapi(cls, dados):
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

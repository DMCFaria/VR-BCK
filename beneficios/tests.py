from unittest import mock

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .views import BoletoBaixaView


@mock.patch.object(BoletoBaixaView, "_get_boleto", lambda self, request, pk=None: None)
class BoletoBaixaAutenticacaoTests(SimpleTestCase):
    """Chave da baixa de boleto: dedicada do Fedcorp-Pay + NFSE_X_API_KEY durante a convivência com o FINANC.

    Sem boleto (mock), passar da autenticação = 404; barrar = 401.
    """

    def _status(self, chave):
        extra = {"HTTP_X_API_KEY": chave} if chave is not None else {}
        req = APIRequestFactory().post("/api/beneficios/boletos/baixa/", {"identificador": "x"}, format="json", **extra)
        return BoletoBaixaView.as_view()(req).status_code

    @override_settings(VRBCK_BOLETO_BAIXA_API_KEY="nova", NFSE_X_API_KEY="nfse", VRBCK_BOLETO_BAIXA_ACEITA_CHAVE_NFSE=True)
    def test_aceita_chave_dedicada_e_a_da_nfse_na_convivencia(self):
        self.assertEqual(self._status("nova"), 404)
        self.assertEqual(self._status("nfse"), 404)
        self.assertEqual(self._status("errada"), 401)
        self.assertEqual(self._status(None), 401)

    @override_settings(VRBCK_BOLETO_BAIXA_API_KEY="nova", NFSE_X_API_KEY="nfse", VRBCK_BOLETO_BAIXA_ACEITA_CHAVE_NFSE=False)
    def test_sem_convivencia_so_a_chave_dedicada(self):
        self.assertEqual(self._status("nova"), 404)
        self.assertEqual(self._status("nfse"), 401)

    @override_settings(VRBCK_BOLETO_BAIXA_API_KEY="", NFSE_X_API_KEY="nfse", VRBCK_BOLETO_BAIXA_ACEITA_CHAVE_NFSE=False)
    def test_chave_vazia_nunca_autentica(self):
        self.assertEqual(self._status(""), 401)

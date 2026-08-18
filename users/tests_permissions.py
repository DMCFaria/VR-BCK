"""
Matriz de permissões tipo × endpoint.

Cobre as regras da demanda do perfil supervisor (sup):
- gerência de usuários (dev/fat total; sup restrito a adm/dep da própria
  administradora; demais perfis negados; auto-promoção bloqueada);
- escopo forçado da consulta de boletos (allowlist dev/fat);
- escrita de TaxaConfig exclusiva de dev/fat;
- visibilidade de importações (adm/dep isolados entre si e do sup; sup vê tudo);
- login Google sem auto-criação de conta.
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from entidades.models import Administradora, Condominio, VinculoCondominio
from beneficios.models import Importacao
from beneficios.views import aplicar_visibilidade_importacoes

CustomUser = get_user_model()


class BasePermissoesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adm_a = Administradora.objects.create(cnpj='11111111000111', razao_social='ADM A')
        cls.adm_b = Administradora.objects.create(cnpj='22222222000122', razao_social='ADM B')

        def novo_usuario(email, tipo, administradora=None):
            user = CustomUser.objects.create_user(
                username=email, email=email, password='senha-teste-123', tipo=tipo
            )
            if administradora:
                user.administradoras.set([administradora])
                user.administradora_ativa = administradora
                user.save(update_fields=['administradora_ativa'])
            return user

        cls.dev = novo_usuario('dev@t.com', 'dev')
        cls.fat = novo_usuario('fat@t.com', 'fat')
        cls.adm = novo_usuario('adm@t.com', 'adm', cls.adm_a)
        cls.dep = novo_usuario('dep@t.com', 'dep', cls.adm_a)
        cls.sup = novo_usuario('sup@t.com', 'sup', cls.adm_a)
        cls.cli = novo_usuario('cli@t.com', 'cli', cls.adm_a)
        cls.adm_outro = novo_usuario('adm-b@t.com', 'adm', cls.adm_b)

    def client_de(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client


class CriacaoDeUsuariosTests(BasePermissoesTestCase):
    URL = '/api/users/register/'

    def payload(self, tipo, administradoras=None, email='novo@t.com'):
        data = {'username': email, 'email': email, 'tipo': tipo}
        if administradoras is not None:
            data['administradoras'] = administradoras
        return data

    def post_registro(self, criador, data):
        # O mock precisa devolver um booleano de verdade: um MagicMock cru em
        # `email_enviado` entra na resposta e o encoder JSON do DRF entra em
        # laço infinito de alocação tentando serializá-lo.
        with patch('users.views.FedhubService') as fedhub:
            fedhub.return_value.enviar_email_usuario_criado.return_value = True
            return self.client_de(criador).post(self.URL, data, format='json')

    def test_dev_e_fat_criam_qualquer_tipo(self):
        for i, criador in enumerate((self.dev, self.fat)):
            resp = self.post_registro(criador, self.payload('sup', [self.adm_a.id], f'novo{i}@t.com'))
            self.assertEqual(resp.status_code, 201, resp.data)

    def test_sup_cria_adm_e_dep_na_propria_administradora(self):
        for i, tipo in enumerate(('adm', 'dep')):
            resp = self.post_registro(self.sup, self.payload(tipo, [self.adm_a.id], f'time{i}@t.com'))
            self.assertEqual(resp.status_code, 201, resp.data)

    def test_sup_sem_administradoras_no_payload_usa_a_ativa(self):
        resp = self.post_registro(self.sup, self.payload('adm'))
        self.assertEqual(resp.status_code, 201, resp.data)
        criado = CustomUser.objects.get(email='novo@t.com')
        self.assertEqual(list(criado.administradoras.values_list('id', flat=True)), [self.adm_a.id])

    def test_sup_nao_cria_sup(self):
        resp = self.post_registro(self.sup, self.payload('sup', [self.adm_a.id]))
        self.assertEqual(resp.status_code, 400)

    def test_sup_nao_cria_em_outra_administradora(self):
        resp = self.post_registro(self.sup, self.payload('adm', [self.adm_b.id]))
        self.assertIn(resp.status_code, (400, 403))

    def test_adm_dep_cli_nao_criam_usuarios(self):
        for usuario in (self.adm, self.dep, self.cli):
            resp = self.post_registro(usuario, self.payload('adm', [self.adm_a.id]))
            self.assertEqual(resp.status_code, 403, f'{usuario.tipo} deveria ser negado')


class EdicaoDeUsuariosTests(BasePermissoesTestCase):
    def url(self, user):
        return reverse('user_detail', kwargs={'pk': user.pk})

    def test_auto_promocao_negada_para_perfis_de_administradora(self):
        for usuario in (self.adm, self.dep, self.cli):
            resp = self.client_de(usuario).patch(
                self.url(usuario), {'tipo': 'dev'}, format='json'
            )
            self.assertEqual(resp.status_code, 403, f'{usuario.tipo} deveria ser negado')

    def test_sup_nao_promove_a_si_mesmo(self):
        resp = self.client_de(self.sup).patch(self.url(self.sup), {'tipo': 'dev'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.sup.refresh_from_db()
        self.assertEqual(self.sup.tipo, 'sup')

    def test_auto_promocao_via_me_negada(self):
        resp = self.client_de(self.adm).patch('/api/users/me/', {'tipo': 'dev'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.adm.refresh_from_db()
        self.assertEqual(self.adm.tipo, 'adm')

    def test_sup_edita_adm_da_propria_administradora(self):
        resp = self.client_de(self.sup).patch(
            self.url(self.adm), {'nome': 'Nome Editado'}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_sup_nao_edita_usuario_de_outra_administradora(self):
        resp = self.client_de(self.sup).patch(
            self.url(self.adm_outro), {'nome': 'X'}, format='json'
        )
        self.assertEqual(resp.status_code, 403)

    def test_sup_nao_edita_fat_nem_promove_para_fora_de_adm_dep(self):
        resp = self.client_de(self.sup).patch(self.url(self.fat), {'nome': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403)

        resp = self.client_de(self.sup).patch(self.url(self.adm), {'tipo': 'sup'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_dev_edita_qualquer_um(self):
        resp = self.client_de(self.dev).patch(self.url(self.adm), {'tipo': 'dep'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class ConsultaBoletosEscopoTests(BasePermissoesTestCase):
    URL = '/api/beneficios/consulta-boletos/'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Importacao.objects.create(
            administradora=cls.adm_a, usuario=cls.adm,
            status='AGUARDANDO_FATURAMENTO', modelo_importacao='VR-BENEFICIOS',
        )
        Importacao.objects.create(
            administradora=cls.adm_b, usuario=cls.adm_outro,
            status='AGUARDANDO_FATURAMENTO', modelo_importacao='VR-BENEFICIOS',
        )

    def test_perfis_de_administradora_recebem_escopo_forcado(self):
        for usuario in (self.adm, self.dep, self.sup, self.cli):
            resp = self.client_de(usuario).get(self.URL, {'administradora_id': self.adm_b.id})
            self.assertEqual(resp.status_code, 200, f'{usuario.tipo}: {resp.data}')
            adm_ids = {item['administradora_id'] for item in resp.data['data']}
            self.assertNotIn(
                self.adm_b.id, adm_ids,
                f'{usuario.tipo} não pode ver boletos de outra administradora'
            )

    def test_fat_pode_filtrar_por_administradora(self):
        resp = self.client_de(self.fat).get(self.URL, {'administradora_id': self.adm_b.id})
        self.assertEqual(resp.status_code, 200)
        adm_ids = {item['administradora_id'] for item in resp.data['data']}
        self.assertEqual(adm_ids, {self.adm_b.id})


class TaxaConfigEscritaTests(BasePermissoesTestCase):
    URL = '/api/entidades/taxas-config/'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.condominio = Condominio.objects.create(cnpj='33333333000133', nome='COND TESTE')
        cls.vinculo = VinculoCondominio.objects.create(
            administradora=cls.adm_a, condominio=cls.condominio
        )

    def payload(self):
        # produto e tipo sempre presentes (null) — é o formato que os
        # clientes do front enviam; o serializer exige as chaves no payload.
        return {
            'vinculo': self.vinculo.id,
            'produto': None,
            'tipo': None,
            'taxa_tipo': 'PERC',
            'taxa_valor': 3.5,
            'ativo': True,
        }

    def test_escrita_negada_para_perfis_de_administradora(self):
        for usuario in (self.adm, self.dep, self.sup, self.cli):
            resp = self.client_de(usuario).post(self.URL, self.payload(), format='json')
            self.assertEqual(resp.status_code, 403, f'{usuario.tipo} não pode gravar taxa')

    def test_escrita_permitida_para_fedcorp(self):
        resp = self.client_de(self.fat).post(self.URL, self.payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_leitura_liberada_para_adm(self):
        resp = self.client_de(self.adm).get(self.URL)
        self.assertEqual(resp.status_code, 200)


class VisibilidadeImportacoesTests(BasePermissoesTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for autor in (cls.adm, cls.dep, cls.sup, cls.dev):
            Importacao.objects.create(
                administradora=cls.adm_a, usuario=autor,
                status='COMPLETED', modelo_importacao='VR-BENEFICIOS',
            )

    def autores_visiveis(self, usuario):
        qs = Importacao.objects.filter(administradora=self.adm_a)
        qs = aplicar_visibilidade_importacoes(qs, usuario)
        return {imp.usuario.tipo for imp in qs}

    def test_adm_nao_ve_dep_dev_sup(self):
        self.assertEqual(self.autores_visiveis(self.adm), {'adm'})

    def test_dep_nao_ve_adm_dev_sup(self):
        self.assertEqual(self.autores_visiveis(self.dep), {'dep'})

    def test_sup_ve_uniao_completa(self):
        self.assertEqual(self.autores_visiveis(self.sup), {'adm', 'dep', 'sup', 'dev'})


class PedidoCartaoAcessoTests(BasePermissoesTestCase):
    """
    Pedidos de cartão da administradora são exclusivos do supervisor
    (dev/fat passam pela visão operacional). O adm não deve acessar —
    a página ficou anos com o menu oculto justamente por isso, e o
    backend não checava tipo nenhum.
    """

    URL = '/api/beneficios/pedidos-cartao/'

    def test_adm_dep_cli_nao_acessam(self):
        for usuario in (self.adm, self.dep, self.cli):
            resp = self.client_de(usuario).get(self.URL)
            self.assertEqual(resp.status_code, 403, f'{usuario.tipo} deveria ser negado')

    def test_sup_acessa(self):
        resp = self.client_de(self.sup).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)


class GoogleLoginTests(BasePermissoesTestCase):
    URL = '/api/users/google-login/'

    def _login(self, email):
        with patch('users.views.id_token.verify_oauth2_token') as verify:
            verify.return_value = {'email': email, 'name': 'Fulano'}
            return APIClient().post(self.URL, {'credential': 'fake'}, format='json')

    def test_conta_nao_cadastrada_e_recusada(self):
        resp = self._login('desconhecido@gmail.com')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(CustomUser.objects.filter(email='desconhecido@gmail.com').exists())

    def test_conta_cadastrada_autentica(self):
        resp = self._login(self.adm.email)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)

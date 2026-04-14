from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import Administradora, Condominio, Gerente, VinculoCondominio

User = get_user_model()


class GerenteModelTest(TestCase):
    def setUp(self):
        self.gerente = Gerente.objects.create(
            nome="João Silva",
            email="joao@teste.com",
            telefone="11999999999",
            ativo=True
        )

    def test_gerente_criado(self):
        self.assertEqual(self.gerente.nome, "João Silva")
        self.assertEqual(self.gerente.email, "joao@teste.com")
        self.assertTrue(self.gerente.ativo)

    def test_gerente_str(self):
        self.assertEqual(str(self.gerente), "João Silva")

    def test_gerente_inativo(self):
        self.gerente.ativo = False
        self.gerente.save()
        self.assertFalse(Gerente.objects.get(id=self.gerente.id).ativo)


class VinculoCondominioModelTest(TestCase):
    def setUp(self):
        self.admin = Administradora.objects.create(
            cnpj="12345678000100",
            nome="Admin Teste",
            ativo=True
        )
        self.condominio = Condominio.objects.create(
            cnpj="98765432000199",
            nome="Condominio Teste"
        )
        self.gerente = Gerente.objects.create(
            nome="Maria Gerente",
            email="maria@teste.com"
        )
        self.vinculo = VinculoCondominio.objects.create(
            administradora=self.admin,
            condominio=self.condominio
        )
        self.vinculo.gerentes.add(self.gerente)

    def test_vinculo_criado(self):
        self.assertEqual(self.vinculo.administradora, self.admin)
        self.assertEqual(self.vinculo.condominio, self.condominio)

    def test_vinculo_str(self):
        self.assertEqual(str(self.vinculo), "Admin Teste - Condominio Teste")

    def test_vinculo_gerentes(self):
        self.assertIn(self.gerente, self.vinculo.gerentes.all())

    def test_vinculo_unique_together(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            VinculoCondominio.objects.create(
                administradora=self.admin,
                condominio=self.condominio
            )


class GerenteAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@teste.com",
            password="senhateste123"
        )
        self.client.force_authenticate(user=self.admin_user)
        
        self.gerente1 = Gerente.objects.create(
            nome="Gerente Um",
            email="gerente1@teste.com"
        )
        self.gerente2 = Gerente.objects.create(
            nome="Gerente Dois",
            email="gerente2@teste.com"
        )
        self.gerente_data = {
            "nome": "Carlos Gerente",
            "email": "carlos@teste.com",
            "telefone": "11988888888",
            "ativo": True
        }

    def test_listar_gerentes(self):
        url = reverse("gerente-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 2)

    def test_criar_gerente(self):
        url = reverse("gerente-list")
        response = self.client.post(url, self.gerente_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["nome"], "Carlos Gerente")
        self.assertEqual(response.data["email"], "carlos@teste.com")

    def test_visualizar_gerente(self):
        url = reverse("gerente-detail", kwargs={"pk": self.gerente1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nome"], "Gerente Um")

    def test_atualizar_gerente(self):
        url = reverse("gerente-detail", kwargs={"pk": self.gerente1.pk})
        response = self.client.patch(url, {"nome": "Nome Atualizado"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nome"], "Nome Atualizado")

    def test_deletar_gerente(self):
        url = reverse("gerente-detail", kwargs={"pk": self.gerente1.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Gerente.objects.filter(pk=self.gerente1.pk).exists())

    def test_filtro_gerente_ativo(self):
        self.gerente1.ativo = False
        self.gerente1.save()
        
        url = reverse("gerente-list")
        response = self.client.get(url, {"ativo": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        for item in results:
            self.assertTrue(item["ativo"])

    def test_gerente_nao_autenticado(self):
        self.client.force_authenticate(user=None)
        url = reverse("gerente-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class VinculoCondominioAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@teste.com",
            password="senhateste123"
        )
        self.client.force_authenticate(user=self.admin_user)
        
        self.admin = Administradora.objects.create(
            cnpj="12345678000100",
            nome="Admin Teste",
            ativo=True
        )
        self.condominio = Condominio.objects.create(
            cnpj="98765432000199",
            nome="Condominio Teste"
        )
        self.gerente1 = Gerente.objects.create(
            nome="Gerente 1",
            email="gerente1@teste.com"
        )
        self.gerente2 = Gerente.objects.create(
            nome="Gerente 2",
            email="gerente2@teste.com"
        )

    def test_listar_vinculos(self):
        VinculoCondominio.objects.create(
            administradora=self.admin,
            condominio=self.condominio
        )
        url = reverse("vinculocondominio-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_criar_vinculo(self):
        url = reverse("vinculocondominio-list")
        data = {
            "administradora": self.admin.id,
            "condominio": self.condominio.cnpj
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["administradora_nome"], "Admin Teste")
        self.assertEqual(response.data["condominio_nome"], "Condominio Teste")

    def test_criar_vinculo_com_gerentes(self):
        url = reverse("vinculocondominio-list")
        data = {
            "administradora": self.admin.id,
            "condominio": self.condominio.cnpj,
            "gerentes": [self.gerente1.id, self.gerente2.id]
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["gerentes"]), 2)

    def test_adicionar_gerente_vinculo_existente(self):
        vinculo = VinculoCondominio.objects.create(
            administradora=self.admin,
            condominio=self.condominio
        )
        url = reverse("vinculocondominio-detail", kwargs={"pk": vinculo.pk})
        data = {"gerentes": [self.gerente1.id]}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.gerente1.id, response.data["gerentes"])

    def test_remover_gerente_vinculo(self):
        vinculo = VinculoCondominio.objects.create(
            administradora=self.admin,
            condominio=self.condominio
        )
        vinculo.gerentes.add(self.gerente1, self.gerente2)
        
        url = reverse("vinculocondominio-detail", kwargs={"pk": vinculo.pk})
        data = {"gerentes": [self.gerente1.id]}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.gerente2.id, response.data["gerentes"])

    def test_vinculo_unique_constraint(self):
        VinculoCondominio.objects.create(
            administradora=self.admin,
            condominio=self.condominio
        )
        url = reverse("vinculocondominio-list")
        data = {
            "administradora": self.admin.id,
            "condominio": self.condominio.cnpj
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filtro_por_administradora(self):
        admin2 = Administradora.objects.create(
            cnpj="11111111000100",
            nome="Admin 2"
        )
        VinculoCondominio.objects.create(administradora=self.admin, condominio=self.condominio)
        VinculoCondominio.objects.create(administradora=admin2, condominio=self.condominio)
        
        url = reverse("vinculocondominio-list")
        response = self.client.get(url, {"administradora": self.admin.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["administradora_nome"], "Admin Teste")

    def test_filtro_por_condominio(self):
        condominio2 = Condominio.objects.create(
            cnpj="22222222000100",
            nome="Condominio 2"
        )
        VinculoCondominio.objects.create(administradora=self.admin, condominio=self.condominio)
        VinculoCondominio.objects.create(administradora=self.admin, condominio=condominio2)
        
        url = reverse("vinculocondominio-list")
        response = self.client.get(url, {"condominio": self.condominio.cnpj})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filtro_por_gerente(self):
        condominio2 = Condominio.objects.create(
            cnpj="22222222000100",
            nome="Condominio 2"
        )
        vinculo1 = VinculoCondominio.objects.create(administradora=self.admin, condominio=self.condominio)
        vinculo2 = VinculoCondominio.objects.create(administradora=self.admin, condominio=condominio2)
        
        vinculo1.gerentes.add(self.gerente1)
        vinculo2.gerentes.add(self.gerente2)
        
        url = reverse("vinculocondominio-list")
        response = self.client.get(url, {"gerente": self.gerente1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["condominio_nome"], "Condominio Teste")

    def test_vinculo_detalhes_com_gerentes(self):
        vinculo = VinculoCondominio.objects.create(
            administradora=self.admin,
            condominio=self.condominio
        )
        vinculo.gerentes.add(self.gerente1, self.gerente2)
        
        url = reverse("vinculocondominio-detail", kwargs={"pk": vinculo.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["gerentes_detalhes"]), 2)

    def test_vinculo_nao_autenticado(self):
        self.client.force_authenticate(user=None)
        url = reverse("vinculocondominio-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

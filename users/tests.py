import json
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model, authenticate
from django.db.utils import IntegrityError
from django.core.exceptions import PermissionDenied

CustomUser = get_user_model()

class CustomUserModelTests(TestCase):
    """
    Testes para garantir que o modelo CustomUser e CustomUserManager
    estao funcionando corretamente.
    """
    def setUp(self):
        self.user_data = {
            'username': 'testeuser',
            'email': 'normal@teste.com',
            'password': 'senhasegura123',
            'empresa': 'Empresa Teste',
            'tipo': 'fat'
        }
        
    def test_create_user(self):
        """
        Testa a criacao basica de um usuario com login por email.
        """
        user = CustomUser.objects.create_user(**self.user_data)
        
        self.assertEqual(user.email, 'normal@teste.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.tipo, 'fat') 
        self.assertEqual(user.empresa, 'Empresa Teste')
        self.assertNotEqual(user.password, 'senhasegura123')

    def test_create_superuser(self):
        """
        Testa a criacao de um superusuario com sucesso, incluindo campos customizados.
        """
        data = self.user_data.copy()
        data['email'] = 'admin@teste.com'
        data['username'] = 'adminuser'
        data['tipo'] = 'dev'
        
        master_user = CustomUser.objects.create_superuser(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            tipo=data['tipo']
        )
        
        self.assertTrue(master_user.is_superuser)
        self.assertTrue(master_user.is_staff)
        self.assertEqual(master_user.tipo, 'dev')

    def test_login_with_email(self):
        """
        Testa a autenticacao de login usando o email (USERNAME_FIELD).
        """
        CustomUser.objects.create_user(**self.user_data)
        
        user = authenticate(
            username='normal@teste.com', 
            password='senhasegura123'
        )
        
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'normal@teste.com')

    def test_email_must_be_unique(self):
        """
        Testa se a criacao de usuarios com emails duplicados falha.
        """
        CustomUser.objects.create_user(**self.user_data)
        
        data_dup = self.user_data.copy()
        data_dup['username'] = 'outro_user'
        
        with self.assertRaises(IntegrityError):
            CustomUser.objects.create_user(**data_dup)

class UserCRUDTests(TestCase):
    """
    Testes para os endpoints de Backend (Views).
    """
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('user-register')

        self.normal_user = CustomUser.objects.create_superuser(
            username='admin', email='admin@a.com', password='p', tipo='adm'
        )
        self.master_user = CustomUser.objects.create_user(
            username='normie', email='normie@a.com', password='p', tipo='fin'
        )
        self.dev_user = CustomUser.objects.create_user(
            username='devuser', email='dev@a.com', password='p', tipo='dev'
        )
        self.user_for_delete = CustomUser.objects.create_user(
            username='del', email='del@a.com', password='p', tipo='adm'
        )
        

        self.valid_data = {
            'username': 'newuser',
            'email': 'new@user.com',
            'password': 'securepassword',
            'password2': 'securepassword', 
            'tipo': 'adm',
            'empresa': 'Startup X'
        }


    def test_user_list_admin_denied(self):
        """ Admin não deve ter acesso a lista e receber JSON """
        # Em vez de self.client.login, use force_authenticate
        self.client.force_authenticate(user=self.normal_user)
        url = reverse('user_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        

    def test_user_detail_fin_access(self):
        """ Usuario 'fin'deve ter acesso aos detalhes de outros usuarios """
        self.client.force_authenticate(user=self.master_user)
        # Usamos o nome da rota unificada: user_detail
        url = reverse('user_detail', kwargs={'pk': self.normal_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) 
        
    
    def test_user_update_success(self):
        """ Master(fin) deve conseguir atualizar um usuario """
        self.client.force_authenticate(user=self.dev_user)
        # Rota unificada: user_detail
        url = reverse('user_detail', kwargs={'pk': self.normal_user.pk})
        
        update_data = {
            'username': 'normie_updated',
            'email': 'normie@a.com',
            'tipo': 'dev',
            'empresa': 'Nova Empresa'
        }
        response = self.client.put(url, update_data, format='json') # Use PUT
        self.assertEqual(response.status_code, 200)

    def test_user_delete_success(self):
        """ Admin deve conseguir deletar um usuario """
        self.client.force_authenticate(user=self.master_user)
        user_id = self.user_for_delete.pk
        # Rota unificada: user_detail
        url = reverse('user_detail', kwargs={'pk': user_id})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
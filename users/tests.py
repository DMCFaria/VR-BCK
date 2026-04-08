import json
from django.test import TestCase, Client
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
        
        admin_user = CustomUser.objects.create_superuser(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            tipo=data['tipo']
        )
        
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertEqual(admin_user.tipo, 'dev')

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
        self.client = Client()
        self.register_url = reverse('user-register')

        self.admin_user = CustomUser.objects.create_superuser(
            username='admin', email='admin@a.com', password='p', tipo='adm'
        )
        self.normal_user = CustomUser.objects.create_user(
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


    def test_register_get_endpoint(self):
        """ Teste se o GET no /register retorna 200 (nao-HTML) """
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)

    def test_successful_registration_post(self):
        """ Teste se o POST cria o usuario e retorna 201 JSON """
        response = self.client.post(self.register_url, self.valid_data)
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue(CustomUser.objects.filter(email='new@user.com').exists())
        
        response_data = response.json()
        self.assertEqual(response_data['email'], 'new@user.com')
        self.assertEqual(response_data['tipo'], 'adm')

    def test_invalid_registration_post(self):
        """ Teste se o POST com dados invalidos retorna 400 JSON """
        invalid_data = self.valid_data.copy()
        invalid_data['password2'] = 'differentpassword'
        
        response = self.client.post(self.register_url, invalid_data)
        
        self.assertEqual(response.status_code, 400) 
        self.assertIn('password2', response.json()['errors'])
        self.assertFalse(CustomUser.objects.filter(email='new@user.com').exists())
        

    def test_user_list_admin_access(self):
        """ Admin deve ter acesso a lista e receber JSON """
        self.client.login(email='admin@a.com', password='p')
        url = reverse('user_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/json')
        self.assertTrue(len(response.json()) >= 3) 
    def test_user_detail_fin_denied(self):
        """ Usuario 'fin' nao deve ter acesso aos detalhes de outros usuarios (Mixin) """
        self.client.login(email='normie@a.com', password='p')
        url = reverse('user_detail', kwargs={'pk': self.admin_user.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403) 
        
    
    def test_user_update_success(self):
        """ Admin deve conseguir atualizar um usuario e receber 200 JSON """
        self.client.login(email='admin@a.com', password='p')
        url = reverse('user_update', kwargs={'pk': self.normal_user.pk})
        
        update_data = {
            'username': 'normie_updated',
            'email': 'normie@a.com',
            'tipo': 'adm',
            'empresa': 'Nova Empresa'
        }
        

        response = self.client.post(url, update_data)
        
        self.assertEqual(response.status_code, 200)
        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.tipo, 'adm')
        self.assertEqual(response.json()['username'], 'normie_updated')


    def test_user_delete_success(self):
        """ Admin deve conseguir deletar um usuario e receber 204 No Content """
        self.client.login(email='admin@a.com', password='p')
        user_id = self.user_for_delete.pk
        url = reverse('user_delete', kwargs={'pk': user_id})

        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, 204) 
        self.assertFalse(CustomUser.objects.filter(pk=user_id).exists())
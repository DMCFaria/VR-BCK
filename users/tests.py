from django.test import TestCase
from django.contrib.auth import get_user_model, authenticate
from django.db.utils import IntegrityError

CustomUser = get_user_model()


class CustomUserModelTests(TestCase):
    """
    Testes do modelo CustomUser / CustomUserManager.
    (Reescritos: a versão anterior usava um campo `empresa` que não existe.)
    """

    def setUp(self):
        self.user_data = {
            'username': 'testeuser',
            'email': 'normal@teste.com',
            'password': 'senhasegura123',
            'tipo': 'fat',
        }

    def test_create_user(self):
        user = CustomUser.objects.create_user(**self.user_data)

        self.assertEqual(user.email, 'normal@teste.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.tipo, 'fat')
        self.assertNotEqual(user.password, 'senhasegura123')

    def test_create_superuser(self):
        master_user = CustomUser.objects.create_superuser(
            username='adminuser',
            email='admin@teste.com',
            password='senhasegura123',
            tipo='dev',
        )

        self.assertTrue(master_user.is_superuser)
        self.assertTrue(master_user.is_staff)
        self.assertEqual(master_user.tipo, 'dev')

    def test_login_with_email(self):
        CustomUser.objects.create_user(**self.user_data)

        user = authenticate(username='normal@teste.com', password='senhasegura123')

        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'normal@teste.com')

    def test_email_must_be_unique(self):
        CustomUser.objects.create_user(**self.user_data)

        data_dup = self.user_data.copy()
        data_dup['username'] = 'outro_user'

        with self.assertRaises(IntegrityError):
            CustomUser.objects.create_user(**data_dup)

    def test_tipo_sup_existe_nos_choices(self):
        tipos = dict(CustomUser.TYPE_CHOICES)
        self.assertIn('sup', tipos)

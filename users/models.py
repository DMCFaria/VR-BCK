from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Gerenciador de usuários customizado. Garante que todos os campos customizados
    são tratados corretamente durante a criação.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O email deve ser fornecido')
        
        email = self.normalize_email(email)
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
      
        if not extra_fields.get('username'):
             raise ValueError('Superuser must have a username.')
        
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    
    TYPE_CHOICES = [
        ("dev", "Desenvolvedor"),
        ("fin", "Financeiro"),
        ("fat", "Faturista"),
        ("adm", "Administrador"),
        ("cli", "Client"),
    ]
    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    email = models.EmailField(unique=True) 


    empresa = models.CharField(max_length=100, blank=True)
    tipo = models.CharField(max_length=3, choices=TYPE_CHOICES, default="adm")
    

    objects = CustomUserManager() 
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'tipo'] 
    
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set', 
        blank=True,
        help_text='The groups this user belongs to.',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        related_query_name='custom_user',
    )
    
    def __str__(self):
        return self.email
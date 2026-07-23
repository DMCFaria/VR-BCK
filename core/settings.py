import logging
import os
from pathlib import Path
from datetime import timedelta
from decouple import config

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')

BASE_URL_CLOUDFLARE_R2 = config('BASE_URL_CLOUDFLARE_R2', default='https://pub-8810a11ea9cf4103bdd7883df14db4de.r2.dev')

BASE_URL_AWS_S3_FEDCORP_MEDIA=config('BASE_URL_AWS_S3_FEDCORP_MEDIA', default='https://fedcorp-media.s3.us-east-2.amazonaws.com')

# Credenciais Fedhub
FEDHUB_URL = config('FEDHUB_URL', default='http://localhost:8090')
FEDHUB_X_API_KEY = config('FEDHUB_X_API_KEY', default='')

FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

EMAIL_FATURAMENTO= config('EMAIL_FATURAMENTO', default='faturamento@fedcorp.com')

DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "vr-beneficios-backend-fedcorp-ju482.ondigitalocean.app", 
    "vr-fedcorp-portal-beneficios-2kxoa.ondigitalocean.app",
    "beneficios.fedhub.com.br"
]

INSTALLED_APPS = [ 
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Apps de Terceiros
    'rest_framework',
    'rest_framework_simplejwt', 
    'corsheaders',

    # Seu App
    'users',
    'upload',
    'beneficios',
    'entidades',
    'consultas',
]

APPEND_SLASH = False


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',  
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),           
        'PASSWORD':config('DB_PASSWORD'),  
        'HOST': config('DB_HOST'),                    
        'PORT': config('DB_PORT'),     
        'CONN_MAX_AGE': 300,                   
    }
    
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
AUTH_USER_MODEL = 'users.CustomUser'


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'suporte@fedcorp.com')
LOGO_URL = os.getenv('LOGO_URL', 'https://i.postimg.cc/SsPmTvDM/logo-fedcorp.png')

# Configurações de Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@seusite.com')
EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'Sistema')



LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} :: {message}',
            'style': '{',
        },
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },

    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },

    'loggers': {
        'nfse': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

logger.info(f"ROOT_URLCONF está definido como: {ROOT_URLCONF}")


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  
    'ROTATE_REFRESH_TOKENS': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': 'sua-chave-secreta-forte',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://vr-beneficios-backend-fedcorp-ju482.ondigitalocean.app",
    "https://vr-fedcorp-portal-beneficios-2kxoa.ondigitalocean.app",
    "https://beneficios.fedhub.com.br"
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://vr-beneficios-backend-fedcorp-ju482.ondigitalocean.app",
    "https://vr-fedcorp-portal-beneficios-2kxoa.ondigitalocean.app",
    "https://beneficios.fedhub.com.br"
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]


ACCESS_KEY_S3 = config('ACCESS_KEY_S3')
SECRET_KEY_S3 = config('SECRET_KEY_S3')
BUCKET_S3 = config('BUCKET_S3')


CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Sao_Paulo'

# NFSe Configurações
NFSE_API_URL = config('NFSE_API_URL', default='https://fedcorp-nfs-e-django-ebh2e.ondigitalocean.app/api/nfse/emissao/vr/')
NFSE_PRESTADOR_CPF_CNPJ = config('NFSE_PRESTADOR_CPF_CNPJ', default='35315360000167')
NFSE_PRESTADOR_RAZAO_SOCIAL = config('NFSE_PRESTADOR_RAZAO_SOCIAL', default='FEDCORP ADMINISTRADORA DE CARTOES LTDA')
NFSE_SERVICO_CODIGO = config('NFSE_SERVICO_CODIGO', default='100202')
NFSE_TOMADOR_CODIGO_PADRAO = config('NFSE_TOMADOR_CODIGO_PADRAO', default='3550308')
NFSE_X_API_KEY = config('NFSE_X_API_KEY', default='fedcorp_static_token_secure_xyz123')

# BigDataCorp
BIGDATA_ACCESS_TOKEN = config('BIGDATA_ACCESS_TOKEN', default='')
BIGDATA_TOKEN_ID = config('BIGDATA_TOKEN_ID', default='')
BIGDATA_URL = config('BIGDATA_URL', default='https://plataforma.bigdatacorp.com.br/empresas')

"""
Django settings for FacturAR project.
"""

from pathlib import Path
import os
import environ

# =========================================================
# PATHS & ENVIRON
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Inicializar environ
env = environ.Env(
    DEBUG=(bool, False) # Valor por defecto seguro
)

# Leer el archivo .env si existe (en producción puede estar configurado a nivel SO)
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    environ.Env.read_env(env_file)


# =========================================================
# SECURITY
# =========================================================

# Lee la clave del .env, si no está en producción, el sistema no levantará
SECRET_KEY = env('SECRET_KEY')

# Si no está en el .env, asume False por el valor por defecto definido arriba
DEBUG = env('DEBUG')

# Convierte automáticamente 'localhost,.corexit.tech' a una lista de Python
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

ARCA_CUIT_FACTURAR = env('ARCA_CUIT_FACTURAR', default='')
ARCA_CERT_PATH = env('ARCA_CERT_PATH', default='')
ARCA_KEY_PATH = env('ARCA_KEY_PATH', default='')


# =========================================================
# SHARED APPS
# =========================================================

SHARED_APPS = [
    # Django
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # No auth acá. Cada tenant tendrá sus propios usuarios.

    # Django Tenants
    'django_tenants',

    # FacturAR
    'tenant',

    # API global
    'api',
]


# =========================================================
# TENANT APPS
# =========================================================

TENANT_APPS = [
    # Autenticación por empresa
    'django.contrib.auth',
    'django.contrib.sessions',

    # Admin
    'django.contrib.admin',

    # Facturación
    'billing',

    # ARCA
    'arca_gateway',
    
    # Gestión de Empleados
    'users',
]


# =========================================================
# INSTALLED APPS
# =========================================================

INSTALLED_APPS = SHARED_APPS + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Tenant según dominio
    'django_tenants.middleware.main.TenantMainMiddleware',
    # CORS
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =========================================================
# URLS
# =========================================================

ROOT_URLCONF = 'FacturAR.urls'


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# =========================================================
# WSGI / ASGI
# =========================================================

WSGI_APPLICATION = 'FacturAR.wsgi.application'
ASGI_APPLICATION = 'FacturAR.asgi.application'


# =========================================================
# DATABASE
# =========================================================

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='5432'),
    }
}


# =========================================================
# DATABASE ROUTER
# =========================================================

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)


# =========================================================
# DJANGO-TENANTS
# =========================================================

TENANT_MODEL = 'tenant.Tenant'
TENANT_DOMAIN_MODEL = 'tenant.Domain'
PUBLIC_SCHEMA_NAME = 'public'


# =========================================================
# AUTH
# =========================================================

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True


# =========================================================
# STATIC
# =========================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']


# =========================================================
# MEDIA
# =========================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =========================================================
# CORS & CSRF
# =========================================================

CORS_ALLOW_ALL_ORIGINS = True

# Lee los dominios confiables desde el .env
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['http://localhost:8000', 'http://127.0.0.1:8000'])


# =========================================================
# DJANGO REST FRAMEWORK
# =========================================================

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
}


# =========================================================
# ARCA / FACTURAR
# =========================================================

FACTURAR_CUIT = env('FACTURAR_CUIT', default='')


# =========================================================
# ARCA CERTIFICATES
# =========================================================

ARCA_CERTIFICATES_DIR = BASE_DIR / 'secrets' / 'arca'


# =========================================================
# COOKIES & PRODUCTION SECURITY
# =========================================================

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

if DEBUG:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
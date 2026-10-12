# En middleware.py de FacturAR o NexoRetail

from django.db import connection
from django.http import Http404

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Obtener el host completo (Ej: farmasino.corexit.tech o localhost:8000)
        hostname = request.get_host().split(':')[0] 
        
        # 2. Extraer la primera parte (Ej: farmasino)
        subdominio = hostname.split('.')[0]

        # 3. Si es el dominio base, la web principal, o estamos desarrollando en local
        if subdominio in ['corexit', 'www', 'localhost', '127']:
            schema_name = 'public'
        else:
            # El subdominio es exactamente el nombre del esquema
            schema_name = subdominio 

        # 4. Setear el esquema en PostgreSQL
        with connection.cursor() as cursor:
            # Validación básica de seguridad alfanumérica
            if schema_name.isalnum():
                cursor.execute(f"SET search_path TO {schema_name}, public;")
            else:
                raise Http404("Inquilino no válido")

        response = self.get_response(request)
        
        # Restaurar por seguridad al terminar el ciclo
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO public;")

        return response
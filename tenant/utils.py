# utils.py
from django.db import connection
from contextlib import contextmanager

@contextmanager
def tenant_context(schema_name):
    """
    Context manager para ejecutar código de Django dentro de un esquema específico.
    Uso:
        with tenant_context('rtlmasino'):
            User.objects.create(...)
    """
    try:
        with connection.cursor() as cursor:
            # Aseguramos el nombre para evitar inyecciones
            if schema_name.isalnum():
                cursor.execute(f"SET search_path TO {schema_name}, public;")
            else:
                raise ValueError("Nombre de esquema inválido")
        
        yield # Aquí se ejecuta el código que esté dentro del bloque 'with'
        
    finally:
        # IMPORTANTE: Siempre restaurar al esquema public al terminar, 
        # incluso si ocurre un error dentro del 'with'.
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO public;")
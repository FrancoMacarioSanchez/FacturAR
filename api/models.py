# api/models.py
from django.db import models
from tenant.models import Tenant
import uuid
import secrets

def generate_api_key():
    return secrets.token_urlsafe(32)

class TenantAPIKey(models.Model):
    """
    Llaves de acceso para que los sistemas de los comercios 
    (o tu propio frontend móvil) interactúen con la API.
    """
    tenant = models.ForeignKey(Tenant, related_name='api_keys', on_delete=models.CASCADE)
    name = models.CharField(max_length=50, help_text="Ej: App Móvil, Servidor Sucursal 1")
    key = models.CharField(max_length=64, default=generate_api_key, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Key: {self.name} ({self.tenant.company_name})"
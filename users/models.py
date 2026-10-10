# users/models.py
from django.db import models
from django.contrib.auth.models import User

class Empleado(models.Model):
    ROLES = [
        ("ADMIN", "Administrador / Dueño"),
        ("CAJERO", "Cajero / Vendedor"),
    ]
    
    usuario = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="perfil_empleado"
    )
    rol = models.CharField(
        max_length=20, 
        choices=ROLES, 
        default="CAJERO"
    )
    
    # Relacionamos de forma "lazy" con la app billing
    punto_venta_asignado = models.ForeignKey(
        'billing.PuntoVenta', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Si se asigna, el cajero solo facturará con este punto de venta."
    )
    
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"

    def __str__(self):
        return f"{self.usuario.username} - {self.get_rol_display()}"
        
    def es_admin(self):
        return self.rol == "ADMIN"
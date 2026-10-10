# users/admin.py
from django.contrib import admin
from .models import Empleado

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'punto_venta_asignado', 'activo')
    list_filter = ('rol', 'activo')
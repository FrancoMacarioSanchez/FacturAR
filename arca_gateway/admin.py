from django.contrib import admin
from .models import (
    ArcaConfiguracion,
    ArcaDelegacion,
    ArcaToken,
)


@admin.register(ArcaConfiguracion)
class ArcaConfiguracionAdmin(admin.ModelAdmin):
    list_display = (
        "metodo",
        "ambiente",
        "activo",
        "creado",
        "actualizado",
    )

    list_filter = (
        "metodo",
        "ambiente",
        "activo",
    )

    readonly_fields = (
        "creado",
        "actualizado",
    )

    ordering = (
        "-actualizado",
    )

admin.site.register(ArcaDelegacion)

@admin.register(ArcaToken)
class ArcaTokenAdmin(admin.ModelAdmin):
    list_display = (
        "servicio",
        "ambiente",
        "expiracion",
        "creado",
        "actualizado",
        "vigente",
    )

    list_filter = (
        "servicio",
        "ambiente",
    )

    search_fields = (
        "servicio",
        "ambiente",
    )

    readonly_fields = (
        "token",
        "sign",
        "expiracion",
        "creado",
        "actualizado",
    )

    ordering = (
        "-expiracion",
    )

    @admin.display(boolean=True, description="Vigente")
    def vigente(self, obj):
        from django.utils import timezone
        return obj.expiracion > timezone.now()
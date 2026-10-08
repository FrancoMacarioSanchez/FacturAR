from django.contrib import admin
from .models import Tenant, Domain, MonotributoCategoria


@admin.register(MonotributoCategoria)
class MonotributoCategoriaAdmin(admin.ModelAdmin):
    list_display = (
        "categoria",
        "ingresos_brutos_anuales",
        "superficie_maxima_m2",
        "energia_maxima_kw",
        "alquileres_maximos_anuales",
        "precio_unitario_maximo",
        "vigente_desde",
        "activo",
    )

    list_filter = (
        "activo",
        "vigente_desde",
    )

    search_fields = (
        "categoria",
    )

    ordering = (
        "categoria",
        "-vigente_desde",
    )

    readonly_fields = (
        "creado",
        "actualizado",
    )


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "razon_social",
        "cuit",
        "nombre",
        "condicion_fiscal",
        "categoria_monotributo",
        "email",
        "activo",
        "schema_name",
        "creado",
    )

    list_filter = (
        "activo",
        "condicion_fiscal",
        "categoria_monotributo",
    )

    search_fields = (
        "razon_social",
        "nombre",
        "cuit",
        "email",
        "schema_name",
    )

    readonly_fields = (
        "creado",
        "actualizado",
    )

    ordering = (
        "razon_social",
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = (
        "domain",
        "tenant",
        "is_primary",
    )

    list_filter = (
        "is_primary",
    )

    search_fields = (
        "domain",
        "tenant__razon_social",
        "tenant__cuit",
    )

    autocomplete_fields = (
        "tenant",
    )

    ordering = (
        "domain",
    )
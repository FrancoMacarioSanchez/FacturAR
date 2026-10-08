from django.contrib import admin
from .models import (
    PuntoVenta,
    Cliente,
    Comprobante,
    ComprobanteItem,
)


@admin.register(PuntoVenta)
class PuntoVentaAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "nombre",
        "activo",
        "habilitado_arca",
        "creado",
    )

    list_filter = (
        "activo",
        "habilitado_arca",
    )

    search_fields = (
        "nombre",
    )

    ordering = (
        "numero",
    )

    readonly_fields = (
        "creado",
    )


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "tipo_documento",
        "numero_documento",
        "condicion_fiscal",
        "email",
        "telefono",
        "creado",
    )

    list_filter = (
        "tipo_documento",
        "condicion_fiscal",
    )

    search_fields = (
        "nombre",
        "numero_documento",
        "email",
        "telefono",
    )

    readonly_fields = (
        "creado",
        "actualizado",
    )

    ordering = (
        "nombre",
    )


class ComprobanteItemInline(admin.TabularInline):
    model = ComprobanteItem
    extra = 0

    fields = (
        "descripcion",
        "cantidad",
        "precio_unitario",
        "alicuota_iva",
        "importe",
    )


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = (
        "numero_completo",
        "tipo",
        "fecha",
        "cliente",
        "punto_venta",
        "estado",
        "importe_total",
        "cae",
        "cae_vencimiento",
    )

    list_filter = (
        "tipo",
        "estado",
        "fecha",
        "punto_venta",
    )

    search_fields = (
        "numero",
        "cae",
        "cuit_emisor",
        "cliente__nombre",
        "cliente__numero_documento",
    )

    readonly_fields = (
        "creado",
        "actualizado",
        "respuesta_arca",
    )

    autocomplete_fields = (
        "cliente",
        "punto_venta",
    )

    date_hierarchy = "fecha"

    ordering = (
        "-fecha",
        "-numero",
    )

    inlines = (
        ComprobanteItemInline,
    )

    fieldsets = (
        (
            "Comprobante",
            {
                "fields": (
                    "tipo",
                    "punto_venta",
                    "numero",
                    "fecha",
                    "cliente",
                    "cuit_emisor",
                    "estado",
                )
            },
        ),
        (
            "Importes",
            {
                "fields": (
                    "importe_neto",
                    "importe_iva",
                    "importe_total",
                )
            },
        ),
        (
            "ARCA",
            {
                "fields": (
                    "cae",
                    "cae_vencimiento",
                    "numero_comprobante_asociado",
                    "respuesta_arca",
                )
            },
        ),
        (
            "Información adicional",
            {
                "fields": (
                    "observaciones",
                    "creado",
                    "actualizado",
                )
            },
        ),
    )

    @admin.display(description="Comprobante", ordering="numero")
    def numero_completo(self, obj):
        return str(obj)


@admin.register(ComprobanteItem)
class ComprobanteItemAdmin(admin.ModelAdmin):
    list_display = (
        "descripcion",
        "comprobante",
        "cantidad",
        "precio_unitario",
        "alicuota_iva",
        "importe",
    )

    search_fields = (
        "descripcion",
        "comprobante__numero",
        "comprobante__cae",
    )

    list_filter = (
        "alicuota_iva",
    )

    autocomplete_fields = (
        "comprobante",
    )
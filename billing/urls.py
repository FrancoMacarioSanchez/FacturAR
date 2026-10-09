from django.urls import path

from . import views


app_name = "billing"


urlpatterns = [
    path(
        "",
        views.dashboard,
        name="dashboard",
    ),

    path(
        "facturar/",
        views.facturar,
        name="facturar",
    ),

    path(
        "comprobantes/",
        views.comprobantes,
        name="comprobantes",
    ),

    path(
        "comprobantes/<int:pk>/",
        views.comprobante_detalle,
        name="comprobante_detalle",
    ),

    path(
        "clientes/",
        views.clientes,
        name="clientes",
    ),

    path(
        "clientes/<int:pk>/",
        views.cliente_detalle,
        name="cliente_detalle",
    ),

    path(
        "puntos-venta/",
        views.puntos_venta,
        name="puntos_venta",
    ),

    path(
        "comprobantes/<int:pk>/emitir-en-arca/",
        views.emitir_en_arca,
        name="emitir_en_arca",
    ),

    path(
        "comprobantes/<int:pk>/verificar-en-arca/",
        views.verificar_comprobante_arca,
        name="verificar_comprobante_arca",
    ),
    path('comprobante/<int:pk>/imprimir/', views.comprobante_imprimir, name='comprobante_imprimir'),
]
from django.urls import path

from . import views


app_name = "arca_gateway"


urlpatterns = [
    path(
        "",
        views.configuracion,
        name="configuracion",
    ),

    path(
        "delegacion/",
        views.delegacion,
        name="delegacion",
    ),

    path(
        "delegacion/verificar/",
        views.verificar_delegacion,
        name="verificar_delegacion",
    ),
]
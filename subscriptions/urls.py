
from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path(
        "planes/",
        views.planes,
        name="planes",
    ),
    path(
        "mi-suscripcion/",
        views.mi_suscripcion,
        name="mi_suscripcion",
    ),
    path(
        "uso/",
        views.uso_actual,
        name="uso_actual",
    ),
    path(
        "seleccionar/<slug:slug>/",
        views.seleccionar_plan,
        name="seleccionar_plan",
    ),
]

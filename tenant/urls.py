from django.urls import path
from . import views


app_name = "tenant"


urlpatterns = [

    path(
        "configuracion/",
        views.configuracion,
        name="configuracion",
    ),

    path(
        "monotributo/",
        views.monotributo,
        name="monotributo",
    ),
]
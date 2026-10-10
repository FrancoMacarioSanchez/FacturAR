from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('equipo/', views.empleados_list, name='empleados_list'),
    path('equipo/nuevo/', views.empleado_create, name='empleado_create'),
    path('equipo/<int:pk>/toggle/', views.empleado_toggle_activo, name='empleado_toggle'),
]
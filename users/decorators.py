# users/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def requiere_rol(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            try:
                empleado = request.user.perfil_empleado
            except:
                messages.error(request, "No tenés un perfil asignado en esta empresa.")
                return redirect("billing:facturar")

            if empleado.rol in roles_permitidos:
                request.empleado = empleado
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "Acceso denegado. Se requiere nivel de Administrador.")
                return redirect("billing:facturar")
                
        return _wrapped_view
    return decorator
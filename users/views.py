from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction, IntegrityError

from .models import Empleado
from .decorators import requiere_rol
from billing.models import PuntoVenta

@login_required
@requiere_rol(["ADMIN"])
def empleados_list(request):
    empleados = Empleado.objects.select_related('usuario', 'punto_venta_asignado').order_by('usuario__username')
    return render(request, 'users/empleados_list.html', {'empleados': empleados})

@login_required
@requiere_rol(["ADMIN"])
def empleado_create(request):
    puntos_venta = PuntoVenta.objects.filter(activo=True)
    
    if request.method == "POST":
        username = request.POST.get("username").strip()
        email = request.POST.get("email").strip()
        password = request.POST.get("password")
        rol = request.POST.get("rol")
        punto_venta_id = request.POST.get("punto_venta_asignado")
        
        try:
            with transaction.atomic():
                # 1. Crear el usuario base de Django
                nuevo_usuario = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                
                # 2. Obtener el punto de venta si se seleccionó uno
                punto_venta = None
                if punto_venta_id:
                    punto_venta = PuntoVenta.objects.get(id=punto_venta_id, activo=True)
                
                # 3. Crear el perfil de empleado en este tenant
                Empleado.objects.create(
                    usuario=nuevo_usuario,
                    rol=rol,
                    punto_venta_asignado=punto_venta
                )
                
            messages.success(request, f"Empleado {username} creado con éxito.")
            return redirect("users:empleados_list")
            
        except IntegrityError:
            messages.error(request, "El nombre de usuario ya existe en el sistema. Elegí otro.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error: {e}")
            
    return render(request, 'users/empleado_form.html', {'puntos_venta': puntos_venta})

@login_required
@requiere_rol(["ADMIN"])
def empleado_toggle_activo(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    
    if empleado.usuario == request.user:
        messages.error(request, "No podés desactivar tu propio usuario.")
        return redirect("users:empleados_list")
        
    empleado.activo = not empleado.activo
    empleado.save()
    
    estado = "activado" if empleado.activo else "desactivado"
    messages.success(request, f"El empleado {empleado.usuario.username} fue {estado}.")
    return redirect("users:empleados_list")
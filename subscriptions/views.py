
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django_tenants.utils import get_public_schema_name
from django.db import connection
from django.utils import timezone

from .models import Plan, Suscripcion, UsoDiario


def obtener_tenant_actual():
    """
    Obtiene la empresa correspondiente al esquema actual.
    Las vistas no deben operar sobre el tenant público.
    """
    tenant = getattr(connection, "tenant", None)

    if (
        tenant is None
        or connection.schema_name == get_public_schema_name()
        or getattr(tenant, "pk", None) is None
    ):
        raise Http404("Esta sección requiere una empresa de FacturAR.")

    return tenant


def obtener_suscripcion(tenant):
    """
    Crea una suscripción Starter si todavía no existe.
    El plan Starter debe estar creado en el administrador.
    """
    starter = Plan.objects.filter(
        slug="starter",
        activo=True,
    ).first()

    if starter is None:
        raise Http404(
            "El plan Starter no está configurado. "
            "Crealo desde el administrador de Django."
        )

    suscripcion, creada = Suscripcion.objects.get_or_create(
        tenant=tenant,
        defaults={
            "plan": starter,
            "estado": Suscripcion.Estado.ACTIVA,
            "frecuencia_pago": Suscripcion.FrecuenciaPago.MENSUAL,
        },
    )

    return suscripcion


@login_required
def planes(request):
    tenant = obtener_tenant_actual()
    suscripcion = obtener_suscripcion(tenant)

    planes_disponibles = Plan.objects.filter(activo=True).order_by(
        "orden",
        "precio_mensual",
    )

    return render(
        request,
        "subscriptions/planes.html",
        {
            "tenant": tenant,
            "suscripcion": suscripcion,
            "planes": planes_disponibles,
        },
    )


@login_required
def mi_suscripcion(request):
    tenant = obtener_tenant_actual()
    suscripcion = obtener_suscripcion(tenant)

    return render(
        request,
        "subscriptions/mi_suscripcion.html",
        {
            "tenant": tenant,
            "suscripcion": suscripcion,
            "plan": suscripcion.plan,
            "vigente": suscripcion.vigente,
        },
    )


@login_required
def uso_actual(request):
    tenant = obtener_tenant_actual()
    suscripcion = obtener_suscripcion(tenant)
    plan = suscripcion.plan

    registro, _ = UsoDiario.objects.get_or_create(
        tenant=tenant,
        fecha=timezone.localdate(),
    )

    limite = (
        plan.aidy_consultas_diarias
        if plan.aidy_habilitado
        else 0
    )

    ilimitado = plan.aidy_habilitado and limite is None

    if not plan.aidy_habilitado:
        restante = 0
    elif ilimitado:
        restante = None
    else:
        restante = max(0, limite - registro.consultas_aidy)

    return render(
        request,
        "subscriptions/uso.html",
        {
            "tenant": tenant,
            "suscripcion": suscripcion,
            "plan": plan,
            "uso_hoy": registro.consultas_aidy,
            "limite_diario": limite,
            "consultas_restantes": restante,
            "aidy_incluido": plan.aidy_habilitado,
            "aidy_disponible": plan.permite_funcionalidad("aidy"),
            "ilimitado": ilimitado,
        },
    )

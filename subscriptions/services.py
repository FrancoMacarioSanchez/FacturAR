
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from billing.models import Cliente, PuntoVenta
from subscriptions.models import Plan, Suscripcion


def obtener_suscripcion_tenant(tenant):
    suscripcion = (
        Suscripcion.objects
        .select_related("plan")
        .filter(tenant=tenant)
        .first()
    )

    if suscripcion:
        return suscripcion

    # Solo asigna Starter si todavía no existe una suscripción.
    starter = Plan.objects.get(slug="starter", activo=True)

    suscripcion, _ = Suscripcion.objects.get_or_create(
        tenant=tenant,
        defaults={
            "plan": starter,
            "estado": Suscripcion.Estado.ACTIVA,
            "frecuencia_pago": Suscripcion.FrecuenciaPago.MENSUAL,
        },
    )
    return suscripcion


def comprobar_limite(tenant, recurso):
    suscripcion = obtener_suscripcion_tenant(tenant)

    if not suscripcion.vigente:
        raise PermissionDenied(
            "Tu suscripción no está activa. Revisá tus planes."
        )

    plan = suscripcion.plan

    configuracion = {
        "clientes": (Cliente, plan.max_clientes),
        "puntos_venta": (PuntoVenta, plan.max_puntos_venta),
        "usuarios": (
            get_user_model(),
            plan.max_usuarios,
        ),
    }

    if recurso not in configuracion:
        raise ValueError(f"Recurso desconocido: {recurso}")

    modelo, limite = configuracion[recurso]

    # None significa ilimitado.
    if limite is None:
        return

    cantidad_actual = modelo.objects.count()

    if cantidad_actual >= limite:
        raise PermissionDenied(
            f"Alcanzaste el límite de {limite} "
            f"{recurso.replace('_', ' ')} de tu plan."
        )

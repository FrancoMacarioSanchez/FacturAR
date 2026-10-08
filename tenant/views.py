from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    return render(
        request,
        "tenant/dashboard.html",
        {
            "tenant": request.tenant,
        },
    )


@login_required
def configuracion(request):
    return render(
        request,
        "tenant/configuracion.html",
        {
            "tenant": request.tenant,
        },
    )
    
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from billing.models import Comprobante
from .models import Tenant, MonotributoCategoria


@login_required
def dashboard(request):

    tenant = request.tenant

    hoy = timezone.localdate()

    inicio_mes = hoy.replace(day=1)

    inicio_anio = hoy.replace(
        month=1,
        day=1,
    )

    inicio_12_meses = hoy - timedelta(days=365)

    comprobantes_aprobados = Comprobante.objects.filter(
        estado="APROBADO"
    )

    facturado_hoy = (
        comprobantes_aprobados
        .filter(fecha=hoy)
        .aggregate(total=Sum("importe_total"))
        .get("total")
        or Decimal("0")
    )

    facturado_mes = (
        comprobantes_aprobados
        .filter(
            fecha__gte=inicio_mes,
            fecha__lte=hoy,
        )
        .aggregate(total=Sum("importe_total"))
        .get("total")
        or Decimal("0")
    )

    facturacion_anual = (
        comprobantes_aprobados
        .filter(
            fecha__gte=inicio_anio,
            fecha__lte=hoy,
        )
        .aggregate(total=Sum("importe_total"))
        .get("total")
        or Decimal("0")
    )

    facturacion_12_meses = (
        comprobantes_aprobados
        .filter(
            fecha__gte=inicio_12_meses,
            fecha__lte=hoy,
        )
        .aggregate(total=Sum("importe_total"))
        .get("total")
        or Decimal("0")
    )

    comprobantes_mes = comprobantes_aprobados.filter(
        fecha__gte=inicio_mes,
        fecha__lte=hoy,
    ).count()

    pendientes = Comprobante.objects.filter(
        estado__in=["BORRADOR", "PENDIENTE"]
    )

    pendientes_total = (
        pendientes
        .aggregate(total=Sum("importe_total"))
        .get("total")
        or Decimal("0")
    )

    pendientes_count = pendientes.count()

    rechazados_count = Comprobante.objects.filter(
        estado="RECHAZADO"
    ).count()

    ultimos_comprobantes = Comprobante.objects.select_related(
        "cliente",
        "punto_venta",
    ).order_by(
        "-fecha",
        "-numero",
    )[:8]

    evolucion_mensual = []

    for mes in range(1, hoy.month + 1):

        inicio_mes_grafico = hoy.replace(
            month=mes,
            day=1,
        )

        if mes == 12:
            fin_mes_grafico = hoy.replace(
                year=hoy.year + 1,
                month=1,
                day=1,
            ) - timedelta(days=1)
        else:
            fin_mes_grafico = hoy.replace(
                month=mes + 1,
                day=1,
            ) - timedelta(days=1)

        total = (
            comprobantes_aprobados
            .filter(
                fecha__gte=inicio_mes_grafico,
                fecha__lte=fin_mes_grafico,
            )
            .aggregate(total=Sum("importe_total"))
            .get("total")
            or Decimal("0")
        )

        evolucion_mensual.append(
            {
                "mes": inicio_mes_grafico.strftime("%b"),
                "total": total,
            }
        )

    promedio_mensual = Decimal("0")

    if evolucion_mensual:
        promedio_mensual = (
            sum(
                item["total"]
                for item in evolucion_mensual
            )
            / len(evolucion_mensual)
        )

    mejor_mes = None

    if evolucion_mensual:
        mejor_mes = max(
            evolucion_mensual,
            key=lambda item: item["total"],
        )

    categoria_monotributo = None
    monotributo_maximo = Decimal("0")
    monotributo_disponible = Decimal("0")
    monotributo_porcentaje = Decimal("0")

    if (
        tenant.condicion_fiscal == "MONOTRIBUTO"
        and tenant.categoria_monotributo
    ):

        categoria_monotributo = (
            MonotributoCategoria.objects
            .filter(
                categoria=tenant.categoria_monotributo,
                activo=True,
            )
            .order_by("-vigente_desde")
            .first()
        )

        if categoria_monotributo:

            monotributo_maximo = (
                categoria_monotributo.ingresos_brutos_anuales
            )

            monotributo_disponible = (
                monotributo_maximo
                - facturacion_12_meses
            )

            if monotributo_disponible < 0:
                monotributo_disponible = Decimal("0")

            if monotributo_maximo > 0:
                monotributo_porcentaje = (
                    facturacion_12_meses
                    / monotributo_maximo
                ) * Decimal("100")

            if monotributo_porcentaje > 100:
                monotributo_porcentaje = Decimal("100")

    context = {
        "tenant": tenant,

        "facturado_hoy": facturado_hoy,
        "facturado_mes": facturado_mes,
        "facturacion_anual": facturacion_anual,
        "facturacion_12_meses": facturacion_12_meses,
        "comprobantes_mes": comprobantes_mes,

        "pendientes_total": pendientes_total,
        "pendientes_count": pendientes_count,
        "rechazados_count": rechazados_count,

        "evolucion_mensual": evolucion_mensual,
        "promedio_mensual": promedio_mensual,
        "mejor_mes": mejor_mes,

        "ultimos_comprobantes": ultimos_comprobantes,

        "categoria_monotributo": categoria_monotributo,
        "monotributo_maximo": monotributo_maximo,
        "monotributo_disponible": monotributo_disponible,
        "monotributo_porcentaje": monotributo_porcentaje,

        "anio": hoy.year,
    }

    return render(
        request,
        "tenant/dashboard.html",
        context,
    )


@login_required
def configuracion(request):
    return render(
        request,
        "tenant/configuracion.html",
    )


@login_required
def monotributo(request):

    categorias = (
        MonotributoCategoria.objects
        .filter(activo=True)
        .order_by("categoria", "-vigente_desde")
    )

    # Nos quedamos solamente con la última vigencia de cada categoría.
    categorias_actuales = {}

    for categoria in categorias:
        if categoria.categoria not in categorias_actuales:
            categorias_actuales[categoria.categoria] = categoria

    categorias = list(
        categorias_actuales.values()
    )

    categorias.sort(
        key=lambda categoria: categoria.categoria
    )

    categoria_tenant = None

    if (
        request.tenant.condicion_fiscal == "MONOTRIBUTO"
        and request.tenant.categoria_monotributo
    ):
        categoria_tenant = next(
            (
                categoria
                for categoria in categorias
                if categoria.categoria
                == request.tenant.categoria_monotributo
            ),
            None,
        )

    return render(
        request,
        "tenant/monotributo.html",
        {
            "categorias": categorias,
            "categoria_tenant": categoria_tenant,
        },
    )
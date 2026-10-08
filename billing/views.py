from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    Cliente,
    Comprobante,
    ComprobanteItem,
    PuntoVenta,
)


def _decimal(value, default="0"):
    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):
        return Decimal(default)


def _calcular_totales(
    descripciones,
    cantidades,
    precios,
    alicuotas,
):
    items = []

    importe_neto = Decimal("0")
    importe_iva = Decimal("0")
    importe_total = Decimal("0")

    cantidad_items = min(
        len(descripciones),
        len(cantidades),
        len(precios),
        len(alicuotas),
    )

    for i in range(cantidad_items):
        descripcion = (
            descripciones[i] or ""
        ).strip()

        if not descripcion:
            continue

        cantidad = _decimal(
            cantidades[i]
        )

        precio = _decimal(
            precios[i]
        )

        alicuota = _decimal(
            alicuotas[i],
            "21",
        )

        if cantidad <= 0:
            continue

        if precio < 0:
            continue

        importe = (
            cantidad * precio
        ).quantize(
            Decimal("0.01")
        )

        if alicuota > 0:
            divisor = (
                Decimal("1")
                + alicuota / Decimal("100")
            )

            neto = (
                importe / divisor
            ).quantize(
                Decimal("0.01")
            )

            iva = (
                importe - neto
            ).quantize(
                Decimal("0.01")
            )
        else:
            neto = importe
            iva = Decimal("0.00")

        importe_neto += neto
        importe_iva += iva
        importe_total += importe

        items.append(
            {
                "descripcion": descripcion,
                "cantidad": cantidad,
                "precio_unitario": precio,
                "importe": importe,
                "alicuota_iva": alicuota,
                "neto": neto,
                "iva": iva,
            }
        )

    return {
        "items": items,
        "importe_neto": importe_neto.quantize(
            Decimal("0.01")
        ),
        "importe_iva": importe_iva.quantize(
            Decimal("0.01")
        ),
        "importe_total": importe_total.quantize(
            Decimal("0.01")
        ),
    }


def _siguiente_numero(
    punto_venta,
    tipo,
):
    ultimo = (
        Comprobante.objects
        .filter(
            punto_venta=punto_venta,
            tipo=tipo,
        )
        .order_by("-numero")
        .first()
    )

    if not ultimo:
        return 1

    return ultimo.numero + 1


@login_required
def dashboard(request):
    hoy = timezone.localdate()

    inicio_mes = hoy.replace(
        day=1
    )

    inicio_anio = hoy.replace(
        month=1,
        day=1,
    )

    # =========================================================
    # COMPROBANTES APROBADOS
    # =========================================================

    aprobados = Comprobante.objects.filter(
        estado="APROBADO"
    )

    facturado_hoy = (
        aprobados
        .filter(
            fecha=hoy,
        )
        .aggregate(
            total=Sum("importe_total")
        )["total"]
        or Decimal("0")
    )

    facturado_mes = (
        aprobados
        .filter(
            fecha__gte=inicio_mes,
            fecha__lte=hoy,
        )
        .aggregate(
            total=Sum("importe_total")
        )["total"]
        or Decimal("0")
    )

    facturado_anio = (
        aprobados
        .filter(
            fecha__gte=inicio_anio,
            fecha__lte=hoy,
        )
        .aggregate(
            total=Sum("importe_total")
        )["total"]
        or Decimal("0")
    )

    comprobantes_hoy = (
        aprobados
        .filter(
            fecha=hoy,
        )
        .count()
    )

    comprobantes_mes = (
        aprobados
        .filter(
            fecha__gte=inicio_mes,
            fecha__lte=hoy,
        )
        .count()
    )

    comprobantes_anio = (
        aprobados
        .filter(
            fecha__gte=inicio_anio,
            fecha__lte=hoy,
        )
        .count()
    )

    # =========================================================
    # PENDIENTES
    # =========================================================

    pendientes = Comprobante.objects.filter(
        estado__in=[
            "BORRADOR",
            "PENDIENTE",
        ]
    )

    pendientes_total = (
        pendientes.aggregate(
            total=Sum("importe_total")
        )["total"]
        or Decimal("0")
    )

    pendientes_cantidad = pendientes.count()

    # =========================================================
    # RECHAZADOS
    # =========================================================

    rechazados = Comprobante.objects.filter(
        estado="RECHAZADO"
    )

    rechazados_cantidad = rechazados.count()

    # =========================================================
    # ÚLTIMOS COMPROBANTES
    # =========================================================

    ultimos_comprobantes = (
        Comprobante.objects
        .select_related(
            "cliente",
            "punto_venta",
        )
        .order_by(
            "-fecha",
            "-creado",
            "-numero",
        )[:8]
    )

    # =========================================================
    # EVOLUCIÓN MENSUAL DEL AÑO
    # =========================================================

    meses = [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ]

    evolucion_mensual = []

    for numero_mes in range(1, hoy.month + 1):
        total_mes = (
            aprobados
            .filter(
                fecha__year=hoy.year,
                fecha__month=numero_mes,
            )
            .aggregate(
                total=Sum("importe_total")
            )["total"]
            or Decimal("0")
        )

        cantidad_mes = (
            aprobados
            .filter(
                fecha__year=hoy.year,
                fecha__month=numero_mes,
            )
            .count()
        )

        evolucion_mensual.append(
            {
                "numero": numero_mes,
                "nombre": meses[numero_mes - 1],
                "total": total_mes,
                "cantidad": cantidad_mes,
            }
        )

    # =========================================================
    # PROMEDIO MENSUAL
    # =========================================================

    meses_con_facturacion = [
        mes
        for mes in evolucion_mensual
        if mes["total"] > 0
    ]

    if meses_con_facturacion:
        promedio_mensual = (
            sum(
                mes["total"]
                for mes in meses_con_facturacion
            )
            / len(meses_con_facturacion)
        )
    else:
        promedio_mensual = Decimal("0")

    # =========================================================
    # MEJOR MES
    # =========================================================

    mejor_mes = None

    if evolucion_mensual:
        mejor_mes = max(
            evolucion_mensual,
            key=lambda mes: mes["total"],
        )

    # =========================================================
    # CONTEXTO
    # =========================================================

    context = {
        "hoy": hoy,
        "anio": hoy.year,

        # Facturación
        "facturado_hoy": facturado_hoy,
        "facturado_mes": facturado_mes,
        "facturado_anio": facturado_anio,

        # Cantidades
        "comprobantes_hoy": comprobantes_hoy,
        "comprobantes_mes": comprobantes_mes,
        "comprobantes_anio": comprobantes_anio,

        # Pendientes
        "pendientes_total": pendientes_total,
        "pendientes_cantidad": pendientes_cantidad,

        # Rechazados
        "rechazados_cantidad": rechazados_cantidad,

        # Evolución
        "evolucion_mensual": evolucion_mensual,
        "promedio_mensual": promedio_mensual,
        "mejor_mes": mejor_mes,

        # Últimos
        "ultimos_comprobantes": ultimos_comprobantes,

        # Compatibilidad con el template anterior
        "facturacion_anual": facturado_anio,

        "monotributo_facturado": Decimal("0"),
        "monotributo_maximo": Decimal("0"),
        "monotributo_porcentaje": Decimal("0"),

        "responsable_facturado": Decimal("0"),
        "responsable_maximo": Decimal("0"),
        "responsable_porcentaje": Decimal("0"),

        "consumidor_facturado": Decimal("0"),
        "consumidor_maximo": Decimal("0"),
        "consumidor_porcentaje": Decimal("0"),
    }

    return render(
        request,
        "billing/dashboard.html",
        context,
    )


@login_required
def comprobantes(request):
    comprobantes_qs = (
        Comprobante.objects
        .select_related(
            "cliente",
            "punto_venta",
        )
        .order_by(
            "-fecha",
            "-numero",
        )
    )

    buscar = request.GET.get(
        "buscar",
        "",
    ).strip()

    estado = request.GET.get(
        "estado",
        "",
    ).strip()

    tipo = request.GET.get(
        "tipo",
        "",
    ).strip()

    if buscar:
        comprobantes_qs = (
            comprobantes_qs.filter(
                cliente__nombre__icontains=buscar
            )
        )

    if estado:
        comprobantes_qs = (
            comprobantes_qs.filter(
                estado=estado
            )
        )

    if tipo:
        comprobantes_qs = (
            comprobantes_qs.filter(
                tipo=tipo
            )
        )

    return render(
        request,
        "billing/comprobantes.html",
        {
            "comprobantes": comprobantes_qs,
            "buscar": buscar,
            "estado": estado,
            "tipo": tipo,
            "tipos": Comprobante.TIPOS,
            "estados": Comprobante.ESTADOS,
        },
    )


@login_required
def comprobante_detalle(
    request,
    pk,
):
    comprobante = get_object_or_404(
        Comprobante.objects
        .select_related(
            "cliente",
            "punto_venta",
        )
        .prefetch_related("items"),
        pk=pk,
    )

    return render(
        request,
        "billing/comprobante_detalle.html",
        {
            "comprobante": comprobante,
        },
    )


@login_required
def facturar(request):
    clientes = Cliente.objects.order_by(
        "nombre"
    )

    puntos_venta = (
        PuntoVenta.objects
        .filter(activo=True)
        .order_by("numero")
    )

    if request.method == "POST":
        tipo = request.POST.get(
            "tipo",
            "FC",
        )

        punto_venta_id = request.POST.get(
            "punto_venta"
        )

        cliente_id = request.POST.get(
            "cliente"
        )

        fecha = request.POST.get(
            "fecha"
        )

        descripciones = request.POST.getlist(
            "descripcion[]"
        )

        cantidades = request.POST.getlist(
            "cantidad[]"
        )

        precios = request.POST.getlist(
            "precio[]"
        )

        alicuotas = request.POST.getlist(
            "alicuota_iva[]"
        )

        punto_venta = get_object_or_404(
            PuntoVenta,
            pk=punto_venta_id,
            activo=True,
        )

        cliente = get_object_or_404(
            Cliente,
            pk=cliente_id,
        )

        if not fecha:
            fecha = timezone.localdate()

        totales = _calcular_totales(
            descripciones,
            cantidades,
            precios,
            alicuotas,
        )

        if not totales["items"]:
            messages.error(
                request,
                "Agregá al menos un producto.",
            )

            return redirect(
                "billing:facturar"
            )

        numero = _siguiente_numero(
            punto_venta,
            tipo,
        )

        comprobante = Comprobante.objects.create(
            tipo=tipo,
            punto_venta=punto_venta,
            numero=numero,
            fecha=fecha,
            cliente=cliente,
            cuit_emisor=request.tenant.cuit,
            estado="BORRADOR",
            importe_neto=totales[
                "importe_neto"
            ],
            importe_iva=totales[
                "importe_iva"
            ],
            importe_total=totales[
                "importe_total"
            ],
        )

        for item in totales["items"]:
            ComprobanteItem.objects.create(
                comprobante=comprobante,
                descripcion=item[
                    "descripcion"
                ],
                cantidad=item[
                    "cantidad"
                ],
                precio_unitario=item[
                    "precio_unitario"
                ],
                importe=item[
                    "importe"
                ],
                alicuota_iva=item[
                    "alicuota_iva"
                ],
            )

        messages.success(
            request,
            (
                "El comprobante fue guardado "
                "como borrador."
            ),
        )

        return redirect(
            "billing:comprobante_detalle",
            pk=comprobante.pk,
        )

    return render(
        request,
        "billing/facturar.html",
        {
            "clientes": clientes,
            "puntos_venta": puntos_venta,
            "hoy": timezone.localdate(),
        },
    )


@login_required
def clientes(request):
    clientes_qs = Cliente.objects.all()

    buscar = request.GET.get(
        "buscar",
        "",
    ).strip()

    if buscar:
        clientes_qs = (
            clientes_qs.filter(
                nombre__icontains=buscar
            )
        )

    return render(
        request,
        "billing/clientes.html",
        {
            "clientes": clientes_qs,
            "buscar": buscar,
        },
    )


@login_required
def cliente_detalle(
    request,
    pk,
):
    cliente = get_object_or_404(
        Cliente,
        pk=pk,
    )

    if request.method == "POST":
        cliente.nombre = request.POST.get(
            "nombre",
            "",
        ).strip()

        cliente.tipo_documento = request.POST.get(
            "tipo_documento",
            "DNI",
        )

        cliente.numero_documento = request.POST.get(
            "numero_documento",
            "",
        ).strip()

        cliente.condicion_fiscal = request.POST.get(
            "condicion_fiscal",
            "",
        ).strip()

        cliente.email = request.POST.get(
            "email",
            "",
        ).strip()

        cliente.telefono = request.POST.get(
            "telefono",
            "",
        ).strip()

        cliente.direccion = request.POST.get(
            "direccion",
            "",
        ).strip()

        cliente.localidad = request.POST.get(
            "localidad",
            "",
        ).strip()

        cliente.provincia = request.POST.get(
            "provincia",
            "",
        ).strip()

        cliente.save()

        messages.success(
            request,
            "Cliente actualizado correctamente.",
        )

        return redirect(
            "billing:cliente_detalle",
            pk=cliente.pk,
        )

    return render(
        request,
        "billing/cliente_detalle.html",
        {
            "cliente": cliente,
            "tipos_documento": Cliente.TIPOS_DOCUMENTO,
        },
    )


@login_required
def puntos_venta(request):
    puntos = (
        PuntoVenta.objects
        .all()
        .order_by("numero")
    )

    if request.method == "POST":
        numero = request.POST.get(
            "numero"
        )

        nombre = request.POST.get(
            "nombre",
            "",
        ).strip()

        if not numero or not nombre:
            messages.error(
                request,
                "Completá número y nombre.",
            )
        else:
            try:
                PuntoVenta.objects.create(
                    numero=int(numero),
                    nombre=nombre,
                )

                messages.success(
                    request,
                    "Punto de venta creado.",
                )

            except Exception:
                messages.error(
                    request,
                    (
                        "No se pudo crear el "
                        "punto de venta."
                    ),
                )

        return redirect(
            "billing:puntos_venta"
        )

    return render(
        request,
        "billing/puntos_venta.html",
        {
            "puntos": puntos,
        },
    )
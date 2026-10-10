from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from users.decorators import requiere_rol

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
    tipo_comprobante,
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

    # Si es comprobante C, se anula el IVA internamente
    es_comprobante_c = tipo_comprobante in ["FC", "NCC", "NDC"]

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

        if es_comprobante_c:
            alicuota = Decimal("0")

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
    # Asume que se llama dentro de un bloque transaction.atomic() 
    # con el punto de venta bloqueado mediante select_for_update()
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


# Asegurate de agregar esto en la parte superior de billing/views.py
from arca_gateway.models import ArcaConfiguracion

from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    Cliente,
    Comprobante,
    ComprobanteItem,
    PuntoVenta,
)

@login_required
@requiere_rol(["ADMIN"])
def dashboard(request):
    from arca_gateway.models import ArcaConfiguracion
    from django.db.models import Case, When, F
    
    hoy = timezone.localdate()

    inicio_mes = hoy.replace(day=1)
    inicio_anio = hoy.replace(month=1, day=1)
    hace_12_meses = hoy - timedelta(days=365)

    # =========================================================
    # LÓGICA DE SUMA CONTABLE (Resta Notas de Crédito)
    # =========================================================
    # NCA, NCB, NCC restan. FA, FB, FC, NDA, NDB, NDC suman.
    suma_neta = Sum(
        Case(
            When(tipo__in=["NCA", "NCB", "NCC"], then=-F("importe_total")),
            default=F("importe_total")
        )
    )

    # =========================================================
    # COMPROBANTES APROBADOS
    # =========================================================

    aprobados = Comprobante.objects.filter(estado="APROBADO")

    facturado_hoy = (
        aprobados.filter(fecha=hoy)
        .aggregate(total=suma_neta)["total"] or Decimal("0")
    )

    facturado_mes = (
        aprobados.filter(fecha__gte=inicio_mes, fecha__lte=hoy)
        .aggregate(total=suma_neta)["total"] or Decimal("0")
    )

    facturado_anio = (
        aprobados.filter(fecha__gte=inicio_anio, fecha__lte=hoy)
        .aggregate(total=suma_neta)["total"] or Decimal("0")
    )

    facturacion_12_meses = (
        aprobados.filter(fecha__gte=hace_12_meses, fecha__lte=hoy)
        .aggregate(total=suma_neta)["total"] or Decimal("0")
    )

    comprobantes_hoy = aprobados.filter(fecha=hoy).count()
    comprobantes_mes = aprobados.filter(fecha__gte=inicio_mes, fecha__lte=hoy).count()
    comprobantes_anio = aprobados.filter(fecha__gte=inicio_anio, fecha__lte=hoy).count()

    # =========================================================
    # PENDIENTES Y RECHAZADOS
    # =========================================================

    pendientes = Comprobante.objects.filter(estado__in=["BORRADOR", "PENDIENTE"])
    pendientes_total = pendientes.aggregate(total=suma_neta)["total"] or Decimal("0")
    pendientes_cantidad = pendientes.count()
    
    rechazados_cantidad = Comprobante.objects.filter(estado="RECHAZADO").count()

    # =========================================================
    # ÚLTIMOS COMPROBANTES
    # =========================================================

    ultimos_comprobantes = (
        Comprobante.objects
        .select_related("cliente", "punto_venta")
        .order_by("-fecha", "-creado", "-numero")[:8]
    )

    # =========================================================
    # EVOLUCIÓN MENSUAL DEL AÑO
    # =========================================================

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    evolucion_mensual = []

    for numero_mes in range(1, hoy.month + 1):
        total_mes = (
            aprobados
            .filter(fecha__year=hoy.year, fecha__month=numero_mes)
            .aggregate(total=suma_neta)["total"] or Decimal("0")
        )
        cantidad_mes = (
            aprobados
            .filter(fecha__year=hoy.year, fecha__month=numero_mes)
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
    # PROMEDIO Y MEJOR MES
    # =========================================================

    meses_con_facturacion = [mes for mes in evolucion_mensual if mes["total"] > 0]
    
    promedio_mensual = Decimal("0")
    if meses_con_facturacion:
        promedio_mensual = sum(mes["total"] for mes in meses_con_facturacion) / len(meses_con_facturacion)

    mejor_mes = None
    if evolucion_mensual:
        mejor_mes = max(evolucion_mensual, key=lambda mes: mes["total"])

    # =========================================================
    # LÓGICA DE MONOTRIBUTO / LÍMITES
    # =========================================================

    monotributo_maximo = Decimal("0")
    monotributo_porcentaje = Decimal("0")
    monotributo_porcentaje_barra = Decimal("0")
    monotributo_disponible = Decimal("0")
    
    categoria = request.tenant.categoria_monotributo
    
    if categoria and categoria.ingresos_brutos_anuales > 0:
        monotributo_maximo = categoria.ingresos_brutos_anuales
        monotributo_porcentaje = (facturacion_12_meses / monotributo_maximo * 100).quantize(Decimal("0.01"))
        
        if facturacion_12_meses < 0:
            facturacion_12_meses = Decimal("0")
            monotributo_porcentaje = Decimal("0")

        monotributo_porcentaje_barra = min(monotributo_porcentaje, Decimal("100"))
        
        monotributo_disponible = monotributo_maximo - facturacion_12_meses
        if monotributo_disponible < 0:
            monotributo_disponible = Decimal("0")

    # =========================================================
    # ESTADO ARCA PARA EL DASHBOARD
    # =========================================================
    
    config_arca = ArcaConfiguracion.objects.filter(activo=True).order_by("-actualizado").first()
    
    arca_estado_codigo = "INCOMPLETO"
    arca_mensaje_ui = "Configuración pendiente"
    arca_ambiente = "HOMOLOGACION"
    arca_bloquea_emision = True

    if config_arca:
        arca_ambiente = config_arca.ambiente
        if config_arca.metodo == "DELEGACION":
            delegacion = getattr(config_arca, "delegacion", None)
            if delegacion:
                if delegacion.estado == "ACTIVA":
                    arca_estado_codigo = "OK"
                    arca_mensaje_ui = "Delegación Activa"
                    arca_bloquea_emision = False
                elif delegacion.estado == "ERROR":
                    arca_estado_codigo = "ERROR"
                    arca_mensaje_ui = "Error en delegación"
                else:
                    arca_estado_codigo = "PENDIENTE"
                    arca_mensaje_ui = "Delegación Pendiente"
            else:
                arca_estado_codigo = "INCOMPLETO"
                arca_mensaje_ui = "Falta configurar delegación"
        else:
            arca_estado_codigo = "OK"
            arca_mensaje_ui = "Certificado Propio"
            arca_bloquea_emision = False

    # =========================================================
    # CONTEXTO
    # =========================================================

    context = {
        "hoy": hoy,
        "anio": hoy.year,

        "facturado_hoy": facturado_hoy,
        "facturado_mes": facturado_mes,
        "facturado_anio": facturado_anio,
        "facturacion_12_meses": facturacion_12_meses,

        "comprobantes_hoy": comprobantes_hoy,
        "comprobantes_mes": comprobantes_mes,
        "comprobantes_anio": comprobantes_anio,

        "pendientes_total": pendientes_total,
        "pendientes_cantidad": pendientes_cantidad,
        "rechazados_cantidad": rechazados_cantidad,

        "evolucion_mensual": evolucion_mensual,
        "promedio_mensual": promedio_mensual,
        "mejor_mes": mejor_mes,

        "ultimos_comprobantes": ultimos_comprobantes,

        "monotributo_facturado": facturacion_12_meses,
        "monotributo_maximo": monotributo_maximo,
        "monotributo_porcentaje": monotributo_porcentaje,
        "monotributo_porcentaje_barra": monotributo_porcentaje_barra,
        "monotributo_disponible": monotributo_disponible,

        "responsable_facturado": Decimal("0"),
        "responsable_maximo": Decimal("0"),
        "responsable_porcentaje": Decimal("0"),
        "consumidor_facturado": Decimal("0"),
        "consumidor_maximo": Decimal("0"),
        "consumidor_porcentaje": Decimal("0"),

        "arca_estado_codigo": arca_estado_codigo,
        "arca_mensaje_ui": arca_mensaje_ui,
        "arca_ambiente": arca_ambiente,
        "arca_bloquea_emision": arca_bloquea_emision,
    }

    return render(request, "billing/dashboard.html", context)


@login_required
@requiere_rol(["ADMIN", "CAJERO"])
def comprobantes(request):
    comprobantes_qs = (
        Comprobante.objects
        .select_related("cliente", "punto_venta")
        .order_by("-fecha", "-numero")
    )

    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "").strip()
    tipo = request.GET.get("tipo", "").strip()

    if buscar:
        comprobantes_qs = comprobantes_qs.filter(cliente__nombre__icontains=buscar)

    if estado:
        comprobantes_qs = comprobantes_qs.filter(estado=estado)

    if tipo:
        comprobantes_qs = comprobantes_qs.filter(tipo=tipo)

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
@requiere_rol(["ADMIN", "CAJERO"])
def comprobante_detalle(request, pk):
    comprobante = get_object_or_404(
        Comprobante.objects
        .select_related("cliente", "punto_venta")
        .prefetch_related("items"),
        pk=pk,
    )

    return render(
        request,
        "billing/comprobante_detalle.html",
        {"comprobante": comprobante},
    )


@login_required
@requiere_rol(["ADMIN", "CAJERO"])
def facturar(request):
    import json
    
    clientes = Cliente.objects.order_by("nombre")
    puntos_venta = PuntoVenta.objects.filter(activo=True).order_by("numero")

    # Extraer todos los comprobantes aprobados para el autocompletado en el frontend
    aprobados = Comprobante.objects.filter(estado="APROBADO").select_related("punto_venta").prefetch_related("items")
    
    comprobantes_json = []
    for c in aprobados:
        items_list = []
        for i in c.items.all():
            items_list.append({
                "descripcion": i.descripcion,
                "cantidad": str(i.cantidad),
                "precio": str(i.precio_unitario),
                "alicuota_iva": str(i.alicuota_iva)
            })
        
        comprobantes_json.append({
            "id": c.id,
            "cliente_id": c.cliente_id,
            "punto_venta_id": c.punto_venta_id,
            "tipo": c.tipo,
            "numero_str": f"{c.punto_venta.numero:04d}-{c.numero:08d}",
            "total": str(c.importe_total),
            "items": items_list
        })

    if request.method == "POST":
        tipo_solicitado = request.POST.get("tipo", "F")
        punto_venta_id = request.POST.get("punto_venta")
        cliente_id = request.POST.get("cliente")
        fecha = request.POST.get("fecha")
        
        descripciones = request.POST.getlist("descripcion[]")
        cantidades = request.POST.getlist("cantidad[]")
        precios = request.POST.getlist("precio[]")
        alicuotas = request.POST.getlist("alicuota_iva[]")

        cliente = get_object_or_404(Cliente, pk=cliente_id)

        prefijo_tipo = "F"
        if tipo_solicitado in ["NC", "ND"]:
            prefijo_tipo = tipo_solicitado

        letra_correcta = cliente.obtener_tipo_comprobante_default(request.tenant.condicion_fiscal)
        tipo_final = f"{prefijo_tipo}{letra_correcta}"

        if not fecha:
            fecha = timezone.localdate()

        totales = _calcular_totales(
            descripciones,
            cantidades,
            precios,
            alicuotas,
            tipo_comprobante=tipo_final,
        )

        if not totales["items"]:
            messages.error(request, "Agregá al menos un producto.")
            return redirect("billing:facturar")

        numero_asociado = None
        
        # Validaciones estrictas para Notas de Crédito / Débito
        if prefijo_tipo in ["NC", "ND"]:
            asociado_id = request.POST.get("comprobante_asociado_id")
            if not asociado_id:
                messages.error(request, "Debés seleccionar el comprobante original asociado.")
                return redirect("billing:facturar")
                
            comp_asoc = get_object_or_404(Comprobante, pk=asociado_id, cliente=cliente, estado="APROBADO")
            
            if comp_asoc.punto_venta_id != int(punto_venta_id):
                messages.error(request, "La Nota debe emitirse en el mismo Punto de Venta que la factura original.")
                return redirect("billing:facturar")
                
            if totales["importe_total"] > comp_asoc.importe_total:
                messages.error(request, "El monto de la Nota no puede superar el total del comprobante original.")
                return redirect("billing:facturar")

            numero_asociado = comp_asoc.numero

        try:
            with transaction.atomic():
                punto_venta = get_object_or_404(
                    PuntoVenta.objects.select_for_update(),
                    pk=punto_venta_id,
                    activo=True,
                )

                numero = _siguiente_numero(punto_venta, tipo_final)

                comprobante = Comprobante.objects.create(
                    tipo=tipo_final,
                    punto_venta=punto_venta,
                    numero=numero,
                    fecha=fecha,
                    cliente=cliente,
                    cuit_emisor=request.tenant.cuit,
                    estado="BORRADOR",
                    importe_neto=totales["importe_neto"],
                    importe_iva=totales["importe_iva"],
                    importe_total=totales["importe_total"],
                    numero_comprobante_asociado=numero_asociado,
                )

                for item in totales["items"]:
                    ComprobanteItem.objects.create(
                        comprobante=comprobante,
                        descripcion=item["descripcion"],
                        cantidad=item["cantidad"],
                        precio_unitario=item["precio_unitario"],
                        importe=item["importe"],
                        alicuota_iva=item["alicuota_iva"],
                    )

            messages.success(request, f"El borrador de la {comprobante.get_tipo_display()} fue guardado.")
            return redirect("billing:comprobante_detalle", pk=comprobante.pk)

        except Exception as e:
            messages.error(request, f"Error al generar el borrador: {e}")
            return redirect("billing:facturar")

    return render(
        request,
        "billing/facturar.html",
        {
            "clientes": clientes,
            "puntos_venta": puntos_venta,
            "hoy": timezone.localdate(),
            "comprobantes_aprobados_json": json.dumps(comprobantes_json),
        },
    )


@login_required
@requiere_rol(["ADMIN", "CAJERO"])
def clientes(request):
    clientes_qs = Cliente.objects.all()
    buscar = request.GET.get("buscar", "").strip()

    if buscar:
        clientes_qs = clientes_qs.filter(nombre__icontains=buscar)

    return render(
        request,
        "billing/clientes.html",
        {
            "clientes": clientes_qs,
            "buscar": buscar,
        },
    )


@login_required
@requiere_rol(["ADMIN", "CAJERO"])
def cliente_detalle(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        cliente.nombre = request.POST.get("nombre", "").strip()
        cliente.tipo_documento = request.POST.get("tipo_documento", "DNI")
        cliente.numero_documento = request.POST.get("numero_documento", "").strip()
        cliente.condicion_fiscal = request.POST.get("condicion_fiscal", "").strip()
        cliente.email = request.POST.get("email", "").strip()
        cliente.telefono = request.POST.get("telefono", "").strip()
        cliente.direccion = request.POST.get("direccion", "").strip()
        cliente.localidad = request.POST.get("localidad", "").strip()
        cliente.provincia = request.POST.get("provincia", "").strip()

        try:
            # Invoca clean() manualmente para forzar las validaciones de CUIT/DNI
            cliente.clean()
            cliente.save()
            messages.success(request, "Cliente actualizado correctamente.")
        except ValidationError as e:
            for field, err in e.message_dict.items():
                messages.error(request, f"{field}: {err[0]}")
        
        return redirect("billing:cliente_detalle", pk=cliente.pk)

    return render(
        request,
        "billing/cliente_detalle.html",
        {
            "cliente": cliente,
            "tipos_documento": Cliente.TIPOS_DOCUMENTO,
            "condiciones_fiscales": Cliente.CONDICIONES_FISCALES,
        },
    )


@login_required
@requiere_rol(["ADMIN"])
def puntos_venta(request):
    puntos = PuntoVenta.objects.all().order_by("numero")

    if request.method == "POST":
        numero = request.POST.get("numero")
        nombre = request.POST.get("nombre", "").strip()

        if not numero or not nombre:
            messages.error(request, "Completá número y nombre.")
        else:
            try:
                PuntoVenta.objects.create(
                    numero=int(numero),
                    nombre=nombre,
                )
                messages.success(request, "Punto de venta creado.")
            except Exception:
                messages.error(request, "No se pudo crear el punto de venta.")

        return redirect("billing:puntos_venta")

    return render(
        request,
        "billing/puntos_venta.html",
        {"puntos": puntos},
    )
    

@login_required
def emitir_en_arca(request, pk):
    if request.method != "POST":
        return redirect("billing:comprobante_detalle", pk=pk)

    comprobante = get_object_or_404(
        Comprobante.objects
        .select_related("cliente", "punto_venta")
        .prefetch_related("items"),
        pk=pk,
    )
    
    if not comprobante.punto_venta.activo:
        messages.error(request, "El punto de venta está inactivo.")
        return redirect("billing:comprobante_detalle", pk=comprobante.pk)

    if not comprobante.punto_venta.habilitado_arca:
        messages.error(
            request,
            "Este punto de venta todavía no está habilitado para operar con ARCA. "
            "Configurá el punto de venta en ARCA y verificá su habilitación "
            "antes de emitir.",
        )
        return redirect("billing:comprobante_detalle", pk=comprobante.pk)

    try:
        from arca_gateway.views import emitir_factura_wsfe
        emitir_factura_wsfe(comprobante)
        messages.success(request, f"Factura autorizada por ARCA. CAE: {comprobante.cae}")
    except Exception as exc:
        messages.error(request, f"No se pudo emitir el comprobante: {exc}")

    return redirect("billing:comprobante_detalle", pk=comprobante.pk)
    

@login_required
def verificar_comprobante_arca(request, pk):
    if request.method != "POST":
        return redirect("billing:comprobante_detalle", pk=pk)

    comprobante = get_object_or_404(
        Comprobante.objects.select_related("cliente", "punto_venta"),
        pk=pk,
    )

    if comprobante.estado != "PENDIENTE":
        messages.warning(request, "Solo se pueden verificar comprobantes pendientes.")
        return redirect("billing:comprobante_detalle", pk=comprobante.pk)

    try:
        from arca_gateway.views import (
            ArcaConfiguracion,
            obtener_token_wsfe,
            consultar_comprobante_wsfe,
            TIPOS_COMPROBANTE_ARCA,
        )

        configuracion = (
            ArcaConfiguracion.objects
            .filter(activo=True)
            .order_by("-actualizado")
            .first()
        )

        if not configuracion:
            raise RuntimeError("No existe una configuración ARCA activa.")

        cuit_emisor = str(comprobante.cuit_emisor or "").strip()
        if not cuit_emisor:
            raise RuntimeError("El comprobante no tiene CUIT emisor registrado.")

        tipo_arca = TIPOS_COMPROBANTE_ARCA.get(comprobante.tipo)
        if not tipo_arca:
            raise RuntimeError("No se reconoce el tipo de comprobante ARCA.")

        respuesta_guardada = comprobante.respuesta_arca or {}
        numero = respuesta_guardada.get("numero_consultado", comprobante.numero)

        token = obtener_token_wsfe()

        resultado = consultar_comprobante_wsfe(
            token=token,
            cuit=cuit_emisor,
            punto_venta=comprobante.punto_venta.numero,
            tipo_comprobante=tipo_arca,
            numero_comprobante=int(numero),
            ambiente=configuracion.ambiente,
        )

        cae = resultado.get("CodAutorizacion", "").strip()
        resultado_arca = resultado.get("Resultado", "").strip()
        vencimiento = resultado.get("FchVto", "").strip()

        if cae and resultado_arca == "A":
            from datetime import datetime

            comprobante.numero = int(numero)
            comprobante.estado = "APROBADO"
            comprobante.cae = cae

            if vencimiento:
                comprobante.cae_vencimiento = datetime.strptime(
                    vencimiento, "%Y%m%d"
                ).date()

            comprobante.respuesta_arca = {
                **respuesta_guardada,
                "verificacion_arca": resultado,
                "estado": "APROBADO_CONFIRMADO",
            }
            comprobante.observaciones = "Autorización confirmada mediante consulta a ARCA."

            comprobante.save(
                update_fields=[
                    "numero",
                    "estado",
                    "cae",
                    "cae_vencimiento",
                    "respuesta_arca",
                    "observaciones",
                    "actualizado",
                ]
            )

            messages.success(request, f"ARCA confirmó la autorización. CAE: {cae}")
        else:
            comprobante.respuesta_arca = {
                **respuesta_guardada,
                "verificacion_arca": resultado,
                "estado": "PENDIENTE_VERIFICACION",
            }
            comprobante.observaciones = (
                "La consulta no confirmó una autorización con CAE. "
                "El comprobante sigue pendiente para evitar duplicados. "
                "Revisá la respuesta de ARCA antes de reintentar."
            )
            comprobante.save(
                update_fields=["respuesta_arca", "observaciones", "actualizado"]
            )
            messages.warning(
                request,
                "ARCA no confirmó un CAE. El comprobante continúa "
                "pendiente y no se habilitó un nuevo intento.",
            )

    except Exception as exc:
        messages.error(
            request,
            f"No se pudo verificar el comprobante en ARCA: {exc}",
        )

    return redirect("billing:comprobante_detalle", pk=comprobante.pk)


# Asegurate de tener estos imports arriba de todo en billing/views.py
import json
import base64
import re
import qrcode
import io
from django.http import HttpResponse

@login_required
def comprobante_imprimir(request, pk):
    comprobante = get_object_or_404(
        Comprobante.objects.select_related("cliente", "punto_venta").prefetch_related("items"),
        pk=pk
    )

    if comprobante.estado != "APROBADO":
        messages.error(request, "Solo se pueden imprimir comprobantes aprobados.")
        return redirect("billing:comprobante_detalle", pk=pk)

    # 1. Mapeos oficiales de AFIP
    TIPOS_COMPROBANTE_ARCA = {
        "FA": 1, "NCA": 3, "NDA": 2,
        "FB": 6, "NCB": 8, "NDB": 7,
        "FC": 11, "NCC": 13, "NDC": 12,
    }
    
    TIPOS_DOCUMENTO_ARCA = {
        "DNI": 96, "CUIT": 80, "CUIL": 86,
        "CONSUMIDOR_FINAL": 99, "PASAPORTE": 94,
    }

    # 2. Limpiar documento del receptor
    doc_receptor_str = re.sub(r"\D", "", str(comprobante.cliente.numero_documento or ""))
    doc_receptor = int(doc_receptor_str) if doc_receptor_str else 0

    # 3. Armar el JSON requerido por AFIP
    qr_data = {
        "ver": 1,
        "fecha": comprobante.fecha.strftime("%Y-%m-%d"),
        "cuit": int(comprobante.cuit_emisor),
        "ptoVta": comprobante.punto_venta.numero,
        "tipoCmp": TIPOS_COMPROBANTE_ARCA.get(comprobante.tipo, 0),
        "nroCmp": comprobante.numero,
        "importe": float(comprobante.importe_total),
        "moneda": "PES",
        "ctz": 1.0,
        "tipoDocRec": TIPOS_DOCUMENTO_ARCA.get(comprobante.cliente.tipo_documento, 99),
        "nroDocRec": doc_receptor,
        "tipoCodAut": "E",
        "codAut": int(comprobante.cae) if comprobante.cae else 0
    }

    json_str = json.dumps(qr_data)
    base64_str = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    url_afip = f"https://www.afip.gob.ar/fe/qr/?p={base64_str}"

    # 4. Generar la imagen del QR en Base64
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(url_afip)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return render(
        request, 
        "billing/comprobante_print.html", 
        {
            "comprobante": comprobante,
            "qr_image": f"data:image/png;base64,{qr_base64}",
            "codigo_comprobante_arca": f"{TIPOS_COMPROBANTE_ARCA.get(comprobante.tipo, 0):03d}"
        }
    )
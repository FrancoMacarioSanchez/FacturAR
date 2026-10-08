from django.http import JsonResponse
from django.views.decorators.http import (
    require_GET,
)

from billing.models import Comprobante


@require_GET
def health(request):

    return JsonResponse({
        "status": "ok",
        "service": "FacturAR",
    })


@require_GET
def comprobantes(request):

    comprobantes = (
        Comprobante.objects
        .select_related(
            "cliente",
            "punto_venta"
        )
        .all()
    )

    results = []

    for comprobante in comprobantes:

        results.append({
            "id": comprobante.id,
            "tipo": comprobante.tipo,
            "punto_venta": (
                comprobante
                .punto_venta
                .numero
            ),
            "numero": comprobante.numero,
            "fecha": str(
                comprobante.fecha
            ),
            "cliente": (
                comprobante
                .cliente
                .nombre
            ),
            "estado": comprobante.estado,
            "cae": comprobante.cae,
            "total": str(
                comprobante.importe_total
            ),
        })

    return JsonResponse({
        "count": len(results),
        "results": results,
    })
import base64
import os
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET
from decimal import Decimal
import requests
from django.db import connection
from datetime import datetime, timedelta, timezone as dt_timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    ArcaConfiguracion,
    ArcaDelegacion,
    ArcaToken,
)

# =========================================================
# CONFIGURACIÓN (CON VARIABLES DE ENTORNO)
# =========================================================
ARCA_CUIT_FACTURAR = os.getenv("ARCA_CUIT_FACTURAR", "20446699696")
ARCA_CERT_PATH = os.getenv("ARCA_CERT_PATH")
ARCA_KEY_PATH = os.getenv("ARCA_KEY_PATH")

WSAA_URLS = {
    "HOMOLOGACION": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
    "PRODUCCION": "https://wsaa.afip.gov.ar/ws/services/LoginCms",
}
WSFE_URLS = {
    "HOMOLOGACION": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx",
    "PRODUCCION": "https://servicios1.afip.gov.ar/wsfev1/service.asmx",
}
TIPOS_COMPROBANTE_ARCA = {
    "FA": 1,
    "NCA": 3,
    "NDA": 2,
    "FB": 6,
    "NCB": 8,
    "NDB": 7,
    "FC": 11,
    "NCC": 13,
    "NDC": 12,
}
TIPOS_DOCUMENTO_ARCA = {
    "DNI": 96,
    "CUIT": 80,
    "CUIL": 86,
    "CONSUMIDOR_FINAL": 99,
    "PASAPORTE": 94,
}

# =========================================================
# CERTIFICADO
# =========================================================

def _obtener_certificado():
    cert_path = ARCA_CERT_PATH
    if not cert_path:
        raise RuntimeError(
            "No está definida la variable de entorno ARCA_CERT_PATH."
        )

    path = Path(cert_path)
    if not path.exists():
        raise RuntimeError(
            f"No existe el certificado ARCA en la ruta indicada: {path}"
        )

    return path.read_bytes()


# =========================================================
# CLAVE PRIVADA
# =========================================================

def _obtener_clave():
    key_path = ARCA_KEY_PATH
    if not key_path:
        raise RuntimeError(
            "No está definida la variable de entorno ARCA_KEY_PATH."
        )

    path = Path(key_path)
    if not path.exists():
        raise RuntimeError(
            f"No existe la clave privada ARCA en la ruta indicada: {path}"
        )

    return path.read_bytes()


# =========================================================
# CREAR LOGIN TICKET REQUEST
# =========================================================
def crear_login_ticket(servicio="wsfe"):
    ahora = datetime.now(dt_timezone.utc)

    generacion = ahora - timedelta(minutes=10)
    expiracion = ahora + timedelta(minutes=10)

    unique_id = int(uuid.uuid4().int % 2147483647)

    root = ET.Element(
        "loginTicketRequest",
        {
            "version": "1.0",
        },
    )

    header = ET.SubElement(root, "header")

    ET.SubElement(
        header,
        "uniqueId",
    ).text = str(unique_id)

    ET.SubElement(
        header,
        "generationTime",
    ).text = generacion.isoformat()

    ET.SubElement(
        header,
        "expirationTime",
    ).text = expiracion.isoformat()

    ET.SubElement(
        root,
        "service",
    ).text = servicio

    return ET.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
    )


# =========================================================
# FIRMAR CMS
# =========================================================

def firmar_login_ticket(xml):
    cert_data = _obtener_certificado()
    key_data = _obtener_clave()

    certificado = x509.load_pem_x509_certificate(
        cert_data
    )

    clave = serialization.load_pem_private_key(
        key_data,
        password=None,
    )

    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(xml)
        .add_signer(
            certificado,
            clave,
            hashes.SHA256(),
        )
    )

    cms = builder.sign(
        serialization.Encoding.DER,
        [
            pkcs7.PKCS7Options.Binary,
        ],
    )

    return base64.b64encode(
        cms
    ).decode("ascii")


# =========================================================
# SOLICITAR TOKEN A WSAA
# =========================================================
def solicitar_token_wsaa(
    cms_base64,
    servicio="wsfe",
    ambiente="PRODUCCION",
):
    url = WSAA_URLS[ambiente]

    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov">
    <soapenv:Header/>
    <soapenv:Body>
        <wsaa:loginCms>
            <wsaa:in0>{cms_base64}</wsaa:in0>
        </wsaa:loginCms>
    </soapenv:Body>
</soapenv:Envelope>
"""

    headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "SOAPAction": '"loginCms"',
        "User-Agent": "FacturAR",
    }

    try:
        response = requests.post(
            url,
            data=soap_body.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(
            f"No se pudo conectar con WSAA: {e}"
        ) from e

    if response.status_code != 200:
        raise RuntimeError(
            f"WSAA respondió HTTP {response.status_code}.\n\n"
            f"Respuesta:\n{response.text[:10000]}"
        )

    return response.text


# =========================================================
# PARSEAR RESPUESTA WSAA
# =========================================================

def parsear_token_wsaa(respuesta_xml):
    try:
        soap_root = ET.fromstring(respuesta_xml)
    except ET.ParseError as e:
        raise RuntimeError(
            "WSAA devolvió una respuesta SOAP inválida.\n\n"
            f"{respuesta_xml[:10000]}"
        ) from e

    def local_name(tag):
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    login_cms_return = None

    for elemento in soap_root.iter():
        if local_name(elemento.tag) == "loginCmsReturn":
            login_cms_return = elemento
            break

    if login_cms_return is None:
        fault_string = None

        for elemento in soap_root.iter():
            if local_name(elemento.tag) == "faultstring":
                fault_string = (elemento.text or "").strip()
                break

        if fault_string:
            raise RuntimeError(
                f"WSAA rechazó la solicitud:\n{fault_string}"
            )

        raise RuntimeError(
            "WSAA no devolvió loginCmsReturn.\n\n"
            "Respuesta recibida:\n"
            f"{respuesta_xml[:10000]}"
        )

    login_ticket_xml = login_cms_return.text

    if not login_ticket_xml:
        raise RuntimeError(
            "WSAA devolvió loginCmsReturn vacío."
        )

    login_ticket_xml = login_ticket_xml.strip()

    try:
        ticket_root = ET.fromstring(login_ticket_xml)
    except ET.ParseError as e:
        raise RuntimeError(
            "WSAA devolvió un loginTicketResponse inválido.\n\n"
            f"{login_ticket_xml[:10000]}"
        ) from e

    token_element = None
    sign_element = None
    expiration_element = None

    for elemento in ticket_root.iter():
        nombre = local_name(elemento.tag)

        if nombre == "token":
            token_element = elemento
        elif nombre == "sign":
            sign_element = elemento
        elif nombre == "expirationTime":
            expiration_element = elemento

    if token_element is None:
        raise RuntimeError(
            "WSAA no devolvió Token.\n\n"
            f"LoginTicketResponse:\n{login_ticket_xml[:10000]}"
        )

    token = (token_element.text or "").strip()

    if not token:
        raise RuntimeError(
            "WSAA devolvió el elemento Token vacío."
        )

    if sign_element is None:
        raise RuntimeError(
            "WSAA devolvió Token pero no devolvió Sign.\n\n"
            f"LoginTicketResponse:\n{login_ticket_xml[:10000]}"
        )

    sign = (sign_element.text or "").strip()

    if not sign:
        raise RuntimeError(
            "WSAA devolvió el elemento Sign vacío."
        )

    if expiration_element is None:
        raise RuntimeError(
            "WSAA devolvió Token y Sign pero no devolvió expirationTime."
        )

    expiration_text = (
        expiration_element.text or ""
    ).strip()

    if not expiration_text:
        raise RuntimeError(
            "WSAA devolvió expirationTime vacío."
        )

    try:
        expiracion = datetime.fromisoformat(
            expiration_text.replace("Z", "+00:00")
        )
    except ValueError as e:
        raise RuntimeError(
            "WSAA devolvió una fecha de expiración inválida:\n"
            f"{expiration_text}"
        ) from e

    if timezone.is_naive(expiracion):
        expiracion = timezone.make_aware(
            expiracion,
            dt_timezone.utc,
        )

    return token, sign, expiracion


# =========================================================
# OBTENER TOKEN VIGENTE
# =========================================================

def obtener_token_wsfe():
    configuracion = (
        ArcaConfiguracion.objects
        .filter(activo=True)
        .order_by("-actualizado")
        .first()
    )

    if not configuracion:
        raise RuntimeError(
            "No existe una configuración ARCA activa para este tenant."
        )

    ambiente = configuracion.ambiente
    ahora = timezone.now()

    token_existente = (
        ArcaToken.objects
        .filter(
            servicio="wsfe",
            ambiente=ambiente,
            expiracion__gt=ahora + timedelta(minutes=2),
        )
        .order_by("-expiracion")
        .first()
    )

    if token_existente:
        return token_existente

    login_ticket = crear_login_ticket(
        servicio="wsfe"
    )

    cms_base64 = firmar_login_ticket(
        login_ticket
    )

    respuesta_xml = solicitar_token_wsaa(
        cms_base64,
        servicio="wsfe",
        ambiente=ambiente,
    )

    token, sign, expiracion = parsear_token_wsaa(
        respuesta_xml
    )

    ArcaToken.objects.filter(
        servicio="wsfe",
        ambiente=ambiente,
    ).delete()

    return ArcaToken.objects.create(
        servicio="wsfe",
        ambiente=ambiente,
        token=token,
        sign=sign,
        expiracion=expiracion,
    )


# =========================================================
# CONFIGURACIÓN ARCA
# =========================================================

@login_required
def configuracion(request):
    configuracion = (
        ArcaConfiguracion.objects
        .first()
    )

    delegacion = None
    if configuracion:
        delegacion = getattr(
            configuracion,
            "delegacion",
            None,
        )

    return render(
        request,
        "arca_gateway/configuracion.html",
        {
            "configuracion": configuracion,
            "delegacion": delegacion,
        },
    )


# =========================================================
# DELEGACIÓN
# =========================================================

@login_required
def delegacion(request):
    configuracion, created = (
        ArcaConfiguracion.objects
        .get_or_create(
            defaults={
                "metodo": "DELEGACION",
                "ambiente": "PRODUCCION",
            }
        )
    )

    tenant = connection.tenant

    delegacion = getattr(
        configuracion,
        "delegacion",
        None,
    )

    if delegacion is None:
        cuit_facturar = os.getenv("ARCA_CUIT_FACTURAR", "20446699696")

        delegacion = (
            ArcaDelegacion.objects.create(
                configuracion=configuracion,
                cuit_cliente=tenant.cuit,
                cuit_facturar=cuit_facturar,
                servicio="wsfe",
                estado="PENDIENTE",
            )
        )

    return render(
        request,
        "arca_gateway/delegacion.html",
        {
            "configuracion": configuracion,
            "delegacion": delegacion,
        },
    )


# =========================================================
# PROBAR WSAA
# =========================================================

@login_required
def verificar_delegacion(request):
    configuracion = (
        ArcaConfiguracion.objects
        .filter(activo=True)
        .order_by("-actualizado")
        .first()
    )

    delegacion = None

    if configuracion:
        try:
            delegacion = configuracion.delegacion
        except ArcaDelegacion.DoesNotExist:
            delegacion = None

    if request.method == "POST":
        try:
            if not configuracion:
                raise RuntimeError(
                    "No existe una configuración ARCA activa."
                )

            token = obtener_token_wsfe()

            if delegacion:
                delegacion.ultima_verificacion = timezone.now()
                delegacion.mensaje = (
                    "Autenticación WSAA correcta. "
                    "La autorización de WSFE debe verificarse "
                    "por separado."
                )

                if delegacion.estado != "ACTIVA":
                    delegacion.estado = "PENDIENTE"

                delegacion.save(
                    update_fields=[
                        "estado",
                        "ultima_verificacion",
                        "mensaje",
                        "actualizado",
                    ]
                )

            messages.success(
                request,
                "WSAA respondió correctamente. "
                "Esto no confirma por sí solo la autorización de WSFE."
            )

            return render(
                request,
                "arca_gateway/delegacion_resultado.html",
                {
                    "configuracion": configuracion,
                    "delegacion": delegacion,
                    "token": token,
                },
            )

        except Exception as exc:
            if delegacion:
                delegacion.estado = "ERROR"
                delegacion.ultima_verificacion = timezone.now()
                delegacion.mensaje = str(exc)
                delegacion.save(
                    update_fields=[
                        "estado",
                        "ultima_verificacion",
                        "mensaje",
                        "actualizado",
                    ]
                )

            messages.error(
                request,
                f"No se pudo autenticar con ARCA: {exc}"
            )

    return render(
        request,
        "arca_gateway/delegacion_resultado.html",
        {
            "configuracion": configuracion,
            "delegacion": delegacion,
        },
    )

# ======================== WSFE =========================

def solicitar_wsfe(
    soap_body,
    ambiente="PRODUCCION",
    soap_action=None,
):
    url = WSFE_URLS[ambiente]

    headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "User-Agent": "FacturAR",
    }

    if soap_action:
        headers["SOAPAction"] = f'"{soap_action}"'

    try:
        response = requests.post(
            url,
            data=soap_body.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(
            f"No se pudo conectar con WSFEv1: {e}"
        ) from e

    if response.status_code != 200:
        raise RuntimeError(
            f"WSFEv1 respondió HTTP {response.status_code}.\n\n"
            f"Respuesta:\n{response.text[:10000]}"
        )

    return response.text


def obtener_ultimo_comprobante(
    token,
    cuit,
    punto_venta,
    tipo_comprobante,
    ambiente="PRODUCCION",
):
    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ar="http://ar.gov.afip.dif.FEV1/">
    <soapenv:Header/>
    <soapenv:Body>
        <ar:FECompUltimoAutorizado>
            <ar:Auth>
                <ar:Token>{token.token}</ar:Token>
                <ar:Sign>{token.sign}</ar:Sign>
                <ar:Cuit>{cuit}</ar:Cuit>
            </ar:Auth>
            <ar:PtoVta>{punto_venta}</ar:PtoVta>
            <ar:CbteTipo>{tipo_comprobante}</ar:CbteTipo>
        </ar:FECompUltimoAutorizado>
    </soapenv:Body>
</soapenv:Envelope>
"""

    return solicitar_wsfe(
        soap_body,
        ambiente=ambiente,
        soap_action="http://ar.gov.afip.dif.FEV1/FECompUltimoAutorizado",
    )


def parsear_ultimo_comprobante(respuesta_xml):
    try:
        root = ET.fromstring(respuesta_xml)
    except ET.ParseError as e:
        raise RuntimeError(
            "WSFEv1 devolvió XML inválido.\n\n"
            f"{respuesta_xml[:10000]}"
        ) from e

    def local_name(tag):
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    numero = None

    for elemento in root.iter():
        if local_name(elemento.tag) == "CbteNro":
            texto = (elemento.text or "").strip()
            if texto:
                numero = int(texto)
                break

    if numero is None:
        fault = None

        for elemento in root.iter():
            if local_name(elemento.tag) == "faultstring":
                fault = (elemento.text or "").strip()
                break

        if fault:
            raise RuntimeError(
                f"WSFEv1 rechazó la consulta:\n{fault}"
            )

        raise RuntimeError(
            "WSFEv1 no devolvió CbteNro.\n\n"
            f"Respuesta:\n{respuesta_xml[:10000]}"
        )

    return numero


def consultar_condiciones_iva_receptor():
    """
    Consulta los códigos oficiales de condición de IVA
    que admite WSFEv1 para el receptor.
    No emite comprobantes.
    """
    token = obtener_token_wsfe()

    configuracion = (
        ArcaConfiguracion.objects
        .filter(activo=True)
        .order_by("-actualizado")
        .first()
    )

    if not configuracion:
        raise RuntimeError(
            "No existe una configuración ARCA activa."
        )

    ambiente = configuracion.ambiente

    cuit_emisor = os.getenv("ARCA_CUIT_FACTURAR", "20446699696")

    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ar="http://ar.gov.afip.dif.FEV1/">
    <soapenv:Header/>
    <soapenv:Body>
        <ar:FEParamGetCondicionIvaReceptor>
            <ar:Auth>
                <ar:Token>{token.token}</ar:Token>
                <ar:Sign>{token.sign}</ar:Sign>
                <ar:Cuit>{cuit_emisor}</ar:Cuit>
            </ar:Auth>
        </ar:FEParamGetCondicionIvaReceptor>
    </soapenv:Body>
</soapenv:Envelope>
"""

    respuesta = solicitar_wsfe(
        soap_body,
        ambiente=ambiente,
        soap_action=(
            "http://ar.gov.afip.dif.FEV1/"
            "FEParamGetCondicionIvaReceptor"
        ),
    )

    try:
        root = ET.fromstring(respuesta)
    except ET.ParseError as exc:
        raise RuntimeError(
            "ARCA devolvió XML inválido."
        ) from exc

    def nombre_local(tag):
        return tag.split("}", 1)[-1]

    errores = []
    condiciones = []

    for elemento in root.iter():
        nombre = nombre_local(elemento.tag)

        if nombre == "Err":
            codigo = ""
            mensaje = ""

            for hijo in elemento.iter():
                hijo_nombre = nombre_local(hijo.tag)

                if hijo_nombre == "Code":
                    codigo = hijo.text or ""
                elif hijo_nombre == "Msg":
                    mensaje = hijo.text or ""

            errores.append(
                f"{codigo}: {mensaje}"
            )

        elif nombre == "CondicionIvaReceptor":
            registro = {}

            for hijo in elemento.iter():
                hijo_nombre = nombre_local(hijo.tag)

                if hijo_nombre in ("Id", "Desc", "Cmp_Clase"):
                    registro[hijo_nombre] = hijo.text

            if registro:
                condiciones.append(registro)

    if errores:
        raise RuntimeError(
            "ARCA rechazó la consulta: "
            + " | ".join(errores)
        )

    if not condiciones:
        raise RuntimeError(
            "La respuesta no contiene condiciones de IVA. "
            "Respuesta recibida:\n"
            + respuesta[:5000]
        )

    return condiciones

def emitir_factura_wsfe(comprobante):
    from decimal import Decimal, ROUND_HALF_UP
    from datetime import datetime as fecha_datetime
    from django.db import transaction
    from billing.models import Comprobante

    if comprobante.estado == "APROBADO" and comprobante.cae:
        raise RuntimeError("Este comprobante ya tiene CAE y está aprobado.")

    if comprobante.estado == "PENDIENTE":
        raise RuntimeError(
            "El comprobante está pendiente de verificación en ARCA. "
            "Consultá su estado antes de volver a emitirlo."
        )

    if comprobante.estado not in ("BORRADOR", "RECHAZADO"):
        raise RuntimeError(
            f"No se puede emitir un comprobante en estado "
            f"{comprobante.get_estado_display()}."
        )

    configuracion = (
        ArcaConfiguracion.objects
        .filter(activo=True)
        .order_by("-actualizado")
        .first()
    )

    if not configuracion:
        raise RuntimeError("No hay una configuración ARCA activa.")

    ambiente = configuracion.ambiente

    if not comprobante.punto_venta.activo:
        raise RuntimeError("El punto de venta está inactivo.")

    if not comprobante.punto_venta.habilitado_arca:
        raise RuntimeError(
            "El punto de venta no está habilitado para operar con ARCA."
        )

    items = list(comprobante.items.all())

    if not items:
        raise RuntimeError("El comprobante no tiene ítems.")

    # ---------------------------------------------------------
    # VALIDACIÓN ESPECÍFICA PARA NOTAS DE CRÉDITO/DÉBITO
    # ---------------------------------------------------------
    TIPO_FACTURA_ASOCIADA = {
        "NCA": 1, "NDA": 1,
        "NCB": 6, "NDB": 6,
        "NCC": 11, "NDC": 11,
    }

    if comprobante.tipo in TIPO_FACTURA_ASOCIADA:
        if not comprobante.numero_comprobante_asociado:
            raise RuntimeError(
                "Para emitir una Nota de Crédito o Débito, es obligatorio "
                "indicar el número de la factura asociada."
            )

    if configuracion.metodo == "DELEGACION":
        try:
            delegacion_configurada = configuracion.delegacion
        except ArcaDelegacion.DoesNotExist:
            delegacion_configurada = None

        if not delegacion_configurada:
            raise RuntimeError(
                "No existe una delegación configurada para este tenant."
            )

        if delegacion_configurada.estado != "ACTIVA":
            raise RuntimeError(
                "La delegación no está activa. Verificá la autorización "
                "de WSFE antes de emitir."
            )

        cuit_emisor = str(delegacion_configurada.cuit_cliente or "").strip()
        cuit_titular = str(delegacion_configurada.cuit_facturar or "").strip()

        if cuit_titular != str(ARCA_CUIT_FACTURAR):
            raise RuntimeError(
                "La CUIT titular del certificado no coincide con "
                "la CUIT configurada para FacturAR."
            )

        if not cuit_emisor:
            raise RuntimeError("La delegación no tiene configurado el CUIT del cliente.")
    else:
        cuit_emisor = str(comprobante.cuit_emisor or "").strip()
        if not cuit_emisor:
            raise RuntimeError("El comprobante no tiene CUIT emisor.")

    token = obtener_token_wsfe()

    tipo_arca = TIPOS_COMPROBANTE_ARCA[comprobante.tipo]
    punto_venta = comprobante.punto_venta.numero

    respuesta_ultimo = obtener_ultimo_comprobante(
        token=token,
        cuit=cuit_emisor,
        punto_venta=punto_venta,
        tipo_comprobante=tipo_arca,
        ambiente=ambiente,
    )

    ultimo_autorizado = parsear_ultimo_comprobante(respuesta_ultimo)
    numero_arca = ultimo_autorizado + 1

    conflicto = (
        Comprobante.objects
        .filter(
            punto_venta=comprobante.punto_venta,
            tipo=comprobante.tipo,
            numero=numero_arca,
        )
        .exclude(pk=comprobante.pk)
        .exists()
    )

    if conflicto:
        raise RuntimeError(
            f"ARCA espera el número {numero_arca}, pero ya existe "
            "otro comprobante local con ese número. No se envió la factura."
        )

    def centavos(valor):
        return Decimal(str(valor)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    total = centavos(comprobante.importe_total)

    if total <= 0:
        raise RuntimeError("El importe total debe ser mayor que cero.")

    iva_por_alicuota = {}

    if comprobante.tipo in ("FA", "FB", "NCA", "NCB", "NDA", "NDB"):
        alicuotas_validas = {
            Decimal("0.00"), Decimal("2.50"), Decimal("5.00"),
            Decimal("10.50"), Decimal("21.00"), Decimal("27.00"),
        }

        for item in items:
            alicuota = centavos(item.alicuota_iva)
            importe_bruto = centavos(item.importe)

            if alicuota not in alicuotas_validas:
                raise RuntimeError(f"La alícuota de IVA {alicuota}% no es válida.")

            divisor = Decimal("1") + alicuota / Decimal("100")
            neto_item = centavos(importe_bruto / divisor)
            iva_item = centavos(importe_bruto - neto_item)

            if alicuota not in iva_por_alicuota:
                iva_por_alicuota[alicuota] = {"neto": Decimal("0.00"), "iva": Decimal("0.00")}

            iva_por_alicuota[alicuota]["neto"] += neto_item
            iva_por_alicuota[alicuota]["iva"] += iva_item

        neto = centavos(sum((dato["neto"] for dato in iva_por_alicuota.values()), Decimal("0.00")))
        iva_total = centavos(sum((dato["iva"] for dato in iva_por_alicuota.values()), Decimal("0.00")))

        if centavos(neto + iva_total) != total:
            raise RuntimeError(
                "Los importes del detalle no coinciden con el total. "
                "Revisá el cálculo de IVA antes de emitir."
            )
    else:
        neto = total
        iva_total = Decimal("0.00")
        iva_por_alicuota = {}

    cliente = comprobante.cliente
    tipo_documento = TIPOS_DOCUMENTO_ARCA.get(cliente.tipo_documento)

    if tipo_documento is None:
        raise RuntimeError(f"Tipo de documento no reconocido: {cliente.tipo_documento}")

    documento_receptor = "".join(caracter for caracter in str(cliente.numero_documento or "") if caracter.isdigit())

    if cliente.tipo_documento == "CONSUMIDOR_FINAL":
        tipo_documento = 99
        documento_receptor = ""
    elif not documento_receptor:
        raise RuntimeError("El cliente debe tener un número de documento.")

    condicion = (cliente.condicion_fiscal or "").strip().lower().replace("_", " ")

    condiciones_iva = {
        "responsable inscripto": 1, "iva responsable inscripto": 1,
        "monotributista": 6, "monotributo": 6, "exento": 4, "iva exento": 4,
        "consumidor final": 5, "no responsable": 7, "sujeto no categorizado": 8,
        "proveedor del exterior": 9, "cliente del exterior": 10,
        "iva no alcanzado": 15, "monotributo social": 13,
    }

    condicion_iva_id = condiciones_iva.get(condicion)
    if condicion_iva_id is None:
        raise RuntimeError("No se reconoce la condición fiscal del receptor.")

    def tag(parent, nombre, valor):
        elemento = ET.SubElement(parent, f"ar:{nombre}")
        elemento.text = str(valor)
        return elemento

    envelope = ET.Element(
        "soapenv:Envelope",
        {
            "xmlns:soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
            "xmlns:ar": "http://ar.gov.afip.dif.FEV1/",
        },
    )

    body = ET.SubElement(envelope, "soapenv:Body")
    solicitud = ET.SubElement(body, "ar:FECAESolicitar")

    auth = ET.SubElement(solicitud, "ar:Auth")
    tag(auth, "Token", token.token)
    tag(auth, "Sign", token.sign)
    tag(auth, "Cuit", cuit_emisor)

    request = ET.SubElement(solicitud, "ar:FeCAEReq")
    cabecera = ET.SubElement(request, "ar:FeCabReq")

    tag(cabecera, "CantReg", 1)
    tag(cabecera, "PtoVta", punto_venta)
    tag(cabecera, "CbteTipo", tipo_arca)

    detalles = ET.SubElement(request, "ar:FeDetReq")
    detalle = ET.SubElement(detalles, "ar:FECAEDetRequest")

    tag(detalle, "Concepto", 1)
    tag(detalle, "DocTipo", tipo_documento)
    tag(detalle, "DocNro", documento_receptor or 0)
    tag(detalle, "CbteDesde", numero_arca)
    tag(detalle, "CbteHasta", numero_arca)
    tag(detalle, "CbteFch", comprobante.fecha.strftime("%Y%m%d"))
    tag(detalle, "ImpTotal", f"{total:.2f}")
    tag(detalle, "ImpTotConc", "0.00")
    tag(detalle, "ImpNeto", f"{neto:.2f}")
    tag(detalle, "ImpOpEx", "0.00")
    tag(detalle, "ImpIVA", f"{iva_total:.2f}")
    tag(detalle, "ImpTrib", "0.00")
    tag(detalle, "MonId", "PES")
    tag(detalle, "MonCotiz", "1.000000")
    tag(detalle, "CondicionIVAReceptorId", condicion_iva_id)

    # ---------------------------------------------------------
    # COMPROBANTES ASOCIADOS (PARA NC/ND)
    # ---------------------------------------------------------
    if comprobante.tipo in TIPO_FACTURA_ASOCIADA:
        cbtes_asoc = ET.SubElement(detalle, "ar:CbtesAsoc")
        cbte_asoc = ET.SubElement(cbtes_asoc, "ar:CbteAsoc")
        
        tag(cbte_asoc, "Tipo", TIPO_FACTURA_ASOCIADA[comprobante.tipo])
        tag(cbte_asoc, "PtoVta", punto_venta)
        tag(cbte_asoc, "Nro", comprobante.numero_comprobante_asociado)

    if comprobante.tipo in ("FA", "FB", "NCA", "NCB", "NDA", "NDB") and iva_por_alicuota:
        iva_container = ET.SubElement(detalle, "ar:Iva")
        codigos_iva = {
            Decimal("0.00"): 3, Decimal("2.50"): 9, Decimal("5.00"): 8,
            Decimal("10.50"): 4, Decimal("21.00"): 5, Decimal("27.00"): 6,
        }

        for alicuota in sorted(iva_por_alicuota):
            datos = iva_por_alicuota[alicuota]
            alicuota_xml = ET.SubElement(iva_container, "ar:AlicIva")
            tag(alicuota_xml, "Id", codigos_iva[alicuota])
            tag(alicuota_xml, "BaseImp", f"{datos['neto']:.2f}")
            tag(alicuota_xml, "Importe", f"{datos['iva']:.2f}")

    soap_body = ET.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
    ).decode("utf-8")

    try:
        respuesta_xml = solicitar_wsfe(
            soap_body,
            ambiente=ambiente,
            soap_action="http://ar.gov.afip.dif.FEV1/FECAESolicitar",
        )
    except Exception as exc:
        comprobante.numero = numero_arca
        comprobante.cuit_emisor = cuit_emisor
        comprobante.estado = "PENDIENTE"
        comprobante.respuesta_arca = {
            "estado": "PENDIENTE_VERIFICACION",
            "numero_consultado": numero_arca,
            "punto_venta": punto_venta,
            "tipo_arca": tipo_arca,
            "error_comunicacion": str(exc),
        }
        comprobante.observaciones = (
            "No se pudo confirmar la respuesta de ARCA. "
            "Consultá el estado del comprobante antes de reintentar. "
            f"Detalle: {exc}"
        )
        comprobante.save(update_fields=["numero", "cuit_emisor", "estado", "respuesta_arca", "observaciones", "actualizado"])
        raise RuntimeError(
            "No se pudo confirmar el resultado de la emisión. "
            "El comprobante quedó pendiente de verificación para evitar una posible duplicación."
        ) from exc

    try:
        respuesta_root = ET.fromstring(respuesta_xml)
    except ET.ParseError as exc:
        comprobante.numero = numero_arca
        comprobante.cuit_emisor = cuit_emisor
        comprobante.estado = "PENDIENTE"
        comprobante.respuesta_arca = {
            "estado": "PENDIENTE_VERIFICACION",
            "numero_consultado": numero_arca,
            "punto_venta": punto_venta,
            "tipo_arca": tipo_arca,
            "respuesta_xml": respuesta_xml[:15000],
            "error_parseo": str(exc),
        }
        comprobante.observaciones = "ARCA respondió, pero no se pudo interpretar la respuesta."
        comprobante.save(update_fields=["numero", "cuit_emisor", "estado", "respuesta_arca", "observaciones", "actualizado"])
        raise RuntimeError(
            "ARCA devolvió una respuesta que no se pudo interpretar. "
            "El comprobante quedó pendiente de verificación."
        ) from exc

    def nombre_local(nombre):
        return nombre.split("}", 1)[-1].split(":", 1)[-1]

    valores = {}
    errores = []
    observaciones = []

    for elemento in respuesta_root.iter():
        nombre = nombre_local(elemento.tag)

        if nombre in ("Resultado", "CAE", "CAEFchVto", "CbteDesde", "CbteHasta"):
            valores[nombre] = (elemento.text or "").strip()
        elif nombre in ("Err", "Obs"):
            codigo = ""
            mensaje = ""
            for hijo in elemento.iter():
                nombre_hijo = nombre_local(hijo.tag)
                if nombre_hijo == "Code":
                    codigo = (hijo.text or "").strip()
                elif nombre_hijo == "Msg":
                    mensaje = (hijo.text or "").strip()

            if mensaje:
                texto = f"{codigo}: {mensaje}" if codigo else mensaje
                if nombre == "Err":
                    errores.append(texto)
                else:
                    observaciones.append(texto)

    resultado = valores.get("Resultado", "")
    cae = valores.get("CAE", "")
    vencimiento = valores.get("CAEFchVto", "")

    if resultado == "A" and cae:
        with transaction.atomic():
            comprobante.numero = numero_arca
            comprobante.cuit_emisor = cuit_emisor
            comprobante.estado = "APROBADO"
            comprobante.cae = cae
            comprobante.observaciones = "\n".join(observaciones)
            comprobante.respuesta_arca = {
                "resultado": resultado,
                "cae": cae,
                "cae_vencimiento": vencimiento,
                "errores": errores,
                "observaciones": observaciones,
                "xml": respuesta_xml,
            }
            if vencimiento:
                comprobante.cae_vencimiento = fecha_datetime.strptime(vencimiento, "%Y%m%d").date()

            comprobante.save(update_fields=["numero", "cuit_emisor", "estado", "cae", "cae_vencimiento", "respuesta_arca", "observaciones", "actualizado"])
        return comprobante

    if resultado == "R":
        comprobante.numero = numero_arca
        comprobante.cuit_emisor = cuit_emisor
        comprobante.estado = "RECHAZADO"
        comprobante.respuesta_arca = {
            "resultado": resultado,
            "errores": errores,
            "observaciones": observaciones,
            "xml": respuesta_xml,
        }
        comprobante.observaciones = "\n".join(errores + observaciones)
        comprobante.save(update_fields=["numero", "cuit_emisor", "estado", "respuesta_arca", "observaciones", "actualizado"])

        detalle_error = " | ".join(errores + observaciones)
        raise RuntimeError("ARCA rechazó el comprobante. " + (detalle_error or "Revisá la respuesta de ARCA."))

    comprobante.numero = numero_arca
    comprobante.cuit_emisor = cuit_emisor
    comprobante.estado = "PENDIENTE"
    comprobante.respuesta_arca = {
        "estado": "PENDIENTE_VERIFICACION",
        "resultado": resultado,
        "errores": errores,
        "observaciones": observaciones,
        "xml": respuesta_xml,
    }
    comprobante.observaciones = "ARCA no devolvió una autorización ni un rechazo concluyente."
    comprobante.save(update_fields=["numero", "cuit_emisor", "estado", "respuesta_arca", "observaciones", "actualizado"])

    raise RuntimeError("No se pudo confirmar si ARCA autorizó el comprobante. Quedó pendiente de verificación.")


def consultar_comprobante_wsfe(
    token,
    cuit,
    punto_venta,
    tipo_comprobante,
    numero_comprobante,
    ambiente="PRODUCCION",
):
    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ar="http://ar.gov.afip.dif.FEV1/">
    <soapenv:Header/>
    <soapenv:Body>
        <ar:FECompConsultar>
            <ar:Auth>
                <ar:Token>{token.token}</ar:Token>
                <ar:Sign>{token.sign}</ar:Sign>
                <ar:Cuit>{cuit}</ar:Cuit>
            </ar:Auth>
            <ar:FeCompConsReq>
                <ar:CbteTipo>{tipo_comprobante}</ar:CbteTipo>
                <ar:CbteNro>{numero_comprobante}</ar:CbteNro>
                <ar:PtoVta>{punto_venta}</ar:PtoVta>
            </ar:FeCompConsReq>
        </ar:FECompConsultar>
    </soapenv:Body>
</soapenv:Envelope>
"""

    respuesta = solicitar_wsfe(
        soap_body,
        ambiente=ambiente,
        soap_action=(
            "http://ar.gov.afip.dif.FEV1/FECompConsultar"
        ),
    )

    try:
        root = ET.fromstring(respuesta)
    except ET.ParseError as exc:
        raise RuntimeError(
            "WSFE devolvió una respuesta XML inválida al consultar "
            "el comprobante."
        ) from exc

    def nombre_local(tag):
        return tag.split("}", 1)[-1].split(":", 1)[-1]

    resultado = {}

    for elemento in root.iter():
        nombre = nombre_local(elemento.tag)

        if nombre in (
            "Resultado",
            "CodAutorizacion",
            "EmisionTipo",
            "FchVto",
            "CbteFch",
            "ImpTotal",
            "PtoVta",
            "CbteTipo",
            "CbteDesde",
            "CbteHasta",
        ):
            resultado[nombre] = (elemento.text or "").strip()

    if not resultado:
        raise RuntimeError(
            "WSFE no devolvió los datos del comprobante consultado."
        )

    return resultado
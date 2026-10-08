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
# CONFIGURACIÓN
# =========================================================
ARCA_CUIT_FACTURAR=20446699696
ARCA_CERT_PATH= 'C:/FacturAR/secrets/facturar.crt'
ARCA_KEY_PATH= 'C:/FacturAR/secrets/facturar.key'
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
            "No está definida la variable "
            "ARCA_CERT_PATH."
        )

    path = Path(cert_path)

    if not path.exists():

        raise RuntimeError(
            f"No existe el certificado ARCA: {path}"
        )

    return path.read_bytes()


# =========================================================
# CLAVE PRIVADA
# =========================================================

def _obtener_clave():

    key_path = ARCA_KEY_PATH

    if not key_path:

        raise RuntimeError(
            "No está definida la variable "
            "ARCA_KEY_PATH."
        )

    path = Path(key_path)

    if not path.exists():

        raise RuntimeError(
            f"No existe la clave privada ARCA: {path}"
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
    ambiente="HOMOLOGACION",
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

    # =========================================================
    # 1. Buscar loginCmsReturn dentro del SOAP
    # =========================================================

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

    # =========================================================
    # 2. El contenido de loginCmsReturn es XML escapado
    # =========================================================

    login_ticket_xml = login_cms_return.text

    if not login_ticket_xml:
        raise RuntimeError(
            "WSAA devolvió loginCmsReturn vacío."
        )

    login_ticket_xml = login_ticket_xml.strip()

    # =========================================================
    # 3. Parsear loginTicketResponse
    # =========================================================

    try:
        ticket_root = ET.fromstring(login_ticket_xml)
    except ET.ParseError as e:
        raise RuntimeError(
            "WSAA devolvió un loginTicketResponse inválido.\n\n"
            f"{login_ticket_xml[:10000]}"
        ) from e

    # =========================================================
    # 4. Buscar token, sign y expirationTime
    # =========================================================

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

    # =========================================================
    # 5. Validar token
    # =========================================================

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

    # =========================================================
    # 6. Validar sign
    # =========================================================

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

    # =========================================================
    # 7. Validar expiración
    # =========================================================

    if expiration_element is None:
        raise RuntimeError(
            "WSAA devolvió Token y Sign pero no devolvió "
            "expirationTime."
        )

    expiration_text = (
        expiration_element.text or ""
    ).strip()

    if not expiration_text:
        raise RuntimeError(
            "WSAA devolvió expirationTime vacío."
        )

    # =========================================================
    # 8. Convertir fecha
    # =========================================================

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

    # =========================================================
    # 9. Retornar credenciales
    # =========================================================

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
                "ambiente": "HOMOLOGACION",
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

        cuit_facturar = os.getenv(
            "ARCA_CUIT_FACTURAR",
            "",
        )

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
        .first()
    )

    delegacion = None

    if configuracion:

        delegacion = getattr(
            configuracion,
            "delegacion",
            None,
        )

    if request.method == "POST":

        try:

            token = obtener_token_wsfe()

            if delegacion:

                delegacion.estado = "ACTIVA"

                delegacion.ultima_verificacion = (
                    timezone.now()
                )

                delegacion.mensaje = (
                    "WSAA respondió correctamente. "
                    "Token obtenido para WSFE."
                )

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
                "Conexión con ARCA WSAA realizada correctamente."
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

                delegacion.ultima_verificacion = (
                    timezone.now()
                )

                delegacion.mensaje = str(
                    exc
                )

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
                f"ARCA rechazó la autenticación: {exc}"
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
    ambiente="HOMOLOGACION",
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
    ambiente="HOMOLOGACION",
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

    cuit_emisor = 20446699696 # os.getenv("ARCA_CUIT_FACTURAR", "")

    if not cuit_emisor:
        raise RuntimeError(
            "Falta configurar ARCA_CUIT_FACTURAR."
        )

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
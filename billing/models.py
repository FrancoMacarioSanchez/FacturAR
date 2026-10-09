import re
from django.db import models
from django.core.exceptions import ValidationError


def validar_cuit_cuil(documento):
    """
    Algoritmo de Módulo 11 para validar CUIT/CUIL según AFIP.
    """
    cuit = str(documento).replace("-", "").strip()
    
    if len(cuit) != 11 or not cuit.isdigit():
        return False

    base = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(cuit[i]) * base[i] for i in range(10))
    resto = suma % 11
    
    if resto == 0:
        digito_esperado = 0
    elif resto == 1:
        if cuit[:2] == "20":
            digito_esperado = 9
        elif cuit[:2] == "27":
            digito_esperado = 4
        elif cuit[:2] == "24":
            digito_esperado = 1
        else:
            digito_esperado = 9
    else:
        digito_esperado = 11 - resto

    return int(cuit[10]) == digito_esperado


class PuntoVenta(models.Model):

    numero = models.PositiveIntegerField()

    nombre = models.CharField(
        max_length=100
    )

    activo = models.BooleanField(
        default=True
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )
    habilitado_arca = models.BooleanField(default=False)

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["numero"],
                name="unique_punto_venta"
            )
        ]

    def __str__(self):
        return (
            f"{self.numero:04d} - "
            f"{self.nombre}"
        )


class Cliente(models.Model):

    TIPOS_DOCUMENTO = [
        ("DNI", "DNI"),
        ("CUIT", "CUIT"),
        ("CUIL", "CUIL"),
        ("PASAPORTE", "Pasaporte"),
        ("CONSUMIDOR_FINAL", "Consumidor Final"),
    ]

    CONDICIONES_FISCALES = [
        ("Responsable Inscripto", "Responsable Inscripto"),
        ("Monotributo", "Monotributo"),
        ("Exento", "IVA Exento"),
        ("Consumidor Final", "Consumidor Final"),
        ("No Responsable", "No Responsable"),
        ("Sujeto No Categorizado", "Sujeto No Categorizado"),
    ]

    nombre = models.CharField(
        max_length=200
    )

    tipo_documento = models.CharField(
        max_length=30,
        choices=TIPOS_DOCUMENTO,
        default="DNI"
    )

    numero_documento = models.CharField(
        max_length=20,
        blank=True
    )

    condicion_fiscal = models.CharField(
        max_length=50,
        choices=CONDICIONES_FISCALES,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    telefono = models.CharField(
        max_length=50,
        blank=True
    )

    direccion = models.CharField(
        max_length=255,
        blank=True
    )

    localidad = models.CharField(
        max_length=100,
        blank=True
    )

    provincia = models.CharField(
        max_length=100,
        blank=True
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()

        if self.tipo_documento == "DNI":
            numero = self.numero_documento.replace(".", "").strip()
            if not numero.isdigit() or not (7 <= len(numero) <= 8):
                raise ValidationError({"numero_documento": "El DNI debe tener entre 7 y 8 números y no contener letras."})
            self.numero_documento = numero

        elif self.tipo_documento in ["CUIT", "CUIL"]:
            numero = self.numero_documento.replace("-", "").strip()
            if not validar_cuit_cuil(numero):
                raise ValidationError({"numero_documento": "El CUIT/CUIL ingresado es inválido (falló validación de AFIP)."})
            self.numero_documento = numero

        elif self.tipo_documento == "CONSUMIDOR_FINAL":
            numero = self.numero_documento.replace(".", "").strip()
            if numero and not numero.isdigit():
                raise ValidationError({"numero_documento": "El documento para Consumidor Final debe ser numérico o dejarse en blanco."})
            self.numero_documento = numero

    def obtener_tipo_comprobante_default(self, condicion_fiscal_emisor):
        """
        Devuelve el sufijo del comprobante ('A', 'B' o 'C') que corresponde emitir
        a este cliente, basándose en la condición fiscal del tenant emisor.
        """
        emisor = (condicion_fiscal_emisor or "").upper()
        receptor = (self.condicion_fiscal or "").upper()

        # Si el emisor es Monotributista o Exento, siempre emite C
        if "MONOTRIBUTO" in emisor or "EXENTO" in emisor:
            return "C"

        # Si el emisor es Responsable Inscripto
        if "RESPONSABLE INSCRIPTO" in emisor:
            # RI emite A si el receptor es RI o Monotributista (resolución 2021)
            if "RESPONSABLE INSCRIPTO" in receptor or "MONOTRIBUTO" in receptor:
                return "A"
            # Caso contrario (Consumidor Final, Exento, etc), emite B
            return "B"

        return "C" # Fallback seguro


class Comprobante(models.Model):

    TIPOS = [
        ("FA", "Factura A"),
        ("FB", "Factura B"),
        ("FC", "Factura C"),

        ("NCA", "Nota de Crédito A"),
        ("NCB", "Nota de Crédito B"),
        ("NCC", "Nota de Crédito C"),

        ("NDA", "Nota de Débito A"),
        ("NDB", "Nota de Débito B"),
        ("NDC", "Nota de Débito C"),
    ]

    ESTADOS = [
        ("BORRADOR", "Borrador"),
        ("PENDIENTE", "Pendiente"),
        ("APROBADO", "Aprobado"),
        ("RECHAZADO", "Rechazado"),
        ("ANULADO", "Anulado"),
    ]

    tipo = models.CharField(
        max_length=3,
        choices=TIPOS
    )

    punto_venta = models.ForeignKey(
        PuntoVenta,
        on_delete=models.PROTECT,
        related_name="comprobantes"
    )

    numero = models.PositiveIntegerField()

    fecha = models.DateField()

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="comprobantes"
    )

    cuit_emisor = models.CharField(
        max_length=20
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="BORRADOR"
    )

    importe_neto = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    importe_iva = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    importe_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    cae = models.CharField(
        max_length=20,
        blank=True
    )

    cae_vencimiento = models.DateField(
        null=True,
        blank=True
    )

    numero_comprobante_asociado = (
        models.PositiveIntegerField(
            null=True,
            blank=True
        )
    )

    respuesta_arca = models.JSONField(
        null=True,
        blank=True
    )

    observaciones = models.TextField(
        blank=True
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = [
            "-fecha",
            "-numero"
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tipo",
                    "punto_venta",
                    "numero"
                ],
                name="unique_comprobante"
            )
        ]

    def __str__(self):
        return (
            f"{self.tipo} "
            f"{self.punto_venta.numero:04d}-"
            f"{self.numero:08d}"
        )


class ComprobanteItem(models.Model):

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name="items"
    )

    descripcion = models.CharField(
        max_length=255
    )

    cantidad = models.DecimalField(
        max_digits=15,
        decimal_places=3
    )

    precio_unitario = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    importe = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    alicuota_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=21
    )

    def __str__(self):
        return self.descripcion
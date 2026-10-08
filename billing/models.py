from django.db import models

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
        (
            "CONSUMIDOR_FINAL",
            "Consumidor Final"
        ),
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
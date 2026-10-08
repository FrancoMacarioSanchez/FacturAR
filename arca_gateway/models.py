from django.db import models


class ArcaConfiguracion(models.Model):

    METODOS = [
        (
            "DELEGACION",
            "Delegación a FacturAR"
        ),
        (
            "PROPIO",
            "Certificado propio"
        ),
    ]

    AMBIENTES = [
        (
            "HOMOLOGACION",
            "Homologación"
        ),
        (
            "PRODUCCION",
            "Producción"
        ),
    ]

    metodo = models.CharField(
        max_length=20,
        choices=METODOS,
        default="DELEGACION"
    )

    ambiente = models.CharField(
        max_length=20,
        choices=AMBIENTES,
        default="HOMOLOGACION"
    )

    activo = models.BooleanField(
        default=True
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"ARCA - "
            f"{self.get_metodo_display()} - "
            f"{self.get_ambiente_display()}"
        )


class ArcaDelegacion(models.Model):

    ESTADOS = [
        (
            "PENDIENTE",
            "Pendiente"
        ),
        (
            "ACTIVA",
            "Activa"
        ),
        (
            "REVOCADA",
            "Revocada"
        ),
        (
            "ERROR",
            "Error"
        ),
    ]

    configuracion = models.OneToOneField(
        ArcaConfiguracion,
        on_delete=models.CASCADE,
        related_name="delegacion"
    )

    cuit_cliente = models.CharField(
        max_length=20
    )

    cuit_facturar = models.CharField(
        max_length=20
    )

    servicio = models.CharField(
        max_length=100,
        default="wsfe"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="PENDIENTE"
    )

    fecha_delegacion = models.DateTimeField(
        null=True,
        blank=True
    )

    ultima_verificacion = models.DateTimeField(
        null=True,
        blank=True
    )

    mensaje = models.TextField(
        blank=True
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"{self.cuit_cliente} → "
            f"{self.cuit_facturar}"
        )


class ArcaToken(models.Model):

    AMBIENTES = [
        ("HOMOLOGACION", "Homologación"),
        ("PRODUCCION", "Producción"),
    ]

    servicio = models.CharField(
        max_length=100
    )

    ambiente = models.CharField(
        max_length=20,
        choices=AMBIENTES,
        default="HOMOLOGACION",
    )

    token = models.TextField()

    sign = models.TextField()

    expiracion = models.DateTimeField()

    creado = models.DateTimeField(
        auto_now_add=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return (
            f"{self.servicio} - "
            f"{self.ambiente} - "
            f"{self.expiracion}"
        )

from django.db import models
from django.db.models import F
from django.utils import timezone


class Plan(models.Model):
    class Soporte(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        PRIORITARIO = "PRIORITARIO", "Prioritario"
        EXCLUSIVO = "EXCLUSIVO", "Grupo exclusivo"

    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    descripcion = models.TextField(blank=True)

    precio_mensual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    precio_anual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    # None equivale a ilimitado.
    max_clientes = models.PositiveIntegerField(default=5, null=True, blank=True)
    max_puntos_venta = models.PositiveIntegerField(default=1, null=True, blank=True)
    max_usuarios = models.PositiveIntegerField(default=1, null=True, blank=True)

    tipo_soporte = models.CharField(
        max_length=20,
        choices=Soporte.choices,
        default=Soporte.NORMAL,
    )

    api_habilitada = models.BooleanField(default=False)
    aidy_habilitado = models.BooleanField(default=False)
    aidy_consultas_diarias = models.PositiveIntegerField(
        default=0,
        null=True,
        blank=True,
        help_text="0 significa sin consultas permitidas; vacío significa ilimitado.",
    )
    app_habilitada = models.BooleanField(default=False)

    # Disponibilidad operativa independiente de lo que incluye el plan.
    api_operativa = models.BooleanField(default=False)
    aidy_operativo = models.BooleanField(default=False)
    app_operativa = models.BooleanField(default=False)

    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden", "precio_mensual"]
        verbose_name = "Plan"
        verbose_name_plural = "Planes"

    def __str__(self):
        return self.nombre

    def permite_funcionalidad(self, funcionalidad):
        """
        Comprueba tanto la inclusión comercial como la disponibilidad
        operativa de una funcionalidad.
        """
        configuracion = {
            "api": (self.api_habilitada, self.api_operativa),
            "aidy": (self.aidy_habilitado, self.aidy_operativo),
            "app": (self.app_habilitada, self.app_operativa),
        }

        if funcionalidad not in configuracion:
            return False

        incluida, operativa = configuracion[funcionalidad]
        return incluida and operativa


class Suscripcion(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        PENDIENTE = "PENDIENTE", "Pendiente"
        SUSPENDIDA = "SUSPENDIDA", "Suspendida"
        CANCELADA = "CANCELADA", "Cancelada"

    class FrecuenciaPago(models.TextChoices):
        MENSUAL = "MENSUAL", "Mensual"
        ANUAL = "ANUAL", "Anual"

    # Tenant vive en el esquema compartido public.
    tenant = models.OneToOneField(
        "tenant.Tenant",
        on_delete=models.PROTECT,
        related_name="suscripcion_facturar",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="suscripciones",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVA,
    )

    frecuencia_pago = models.CharField(
        max_length=10,
        choices=FrecuenciaPago.choices,
        default=FrecuenciaPago.MENSUAL,
    )

    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"

    def __str__(self):
        return f"{self.tenant} - {self.plan}"

    @property
    def vigente(self):
        hoy = timezone.localdate()
        return (
            self.estado == self.Estado.ACTIVA
            and (self.fecha_fin is None or self.fecha_fin >= hoy)
        )


class UsoDiario(models.Model):
    """
    Contabiliza las consultas de Aidy por empresa y día,
    compartidas entre todos los usuarios de esa empresa.
    """

    tenant = models.ForeignKey(
        "tenant.Tenant",
        on_delete=models.CASCADE,
        related_name="uso_diario_facturar",
    )

    fecha = models.DateField(default=timezone.localdate)
    consultas_aidy = models.PositiveIntegerField(default=0)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "fecha"],
                name="uniq_uso_aidy_tenant_fecha",
            )
        ]
        ordering = ["-fecha"]
        verbose_name = "Uso diario"
        verbose_name_plural = "Uso diario"

    def __str__(self):
        return f"{self.tenant} - {self.fecha}: {self.consultas_aidy}"

    @classmethod
    def consultas_hoy(cls, tenant):
        registro, _ = cls.objects.get_or_create(
            tenant=tenant,
            fecha=timezone.localdate(),
        )
        return registro.consultas_aidy

    @classmethod
    def registrar_consulta(cls, tenant):
        """
        Incrementa el contador. La vista que llama a este método debe
        comprobar primero el límite del plan.
        """
        registro, _ = cls.objects.get_or_create(
            tenant=tenant,
            fecha=timezone.localdate(),
        )

        cls.objects.filter(pk=registro.pk).update(
            consultas_aidy=F("consultas_aidy") + 1
        )

        registro.refresh_from_db()
        return registro.consultas_aidy

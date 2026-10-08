from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class MonotributoCategoria(models.Model):
    categoria = models.CharField(
        max_length=1,
        unique=True,
        choices=[
            ("A", "Categoría A"),
            ("B", "Categoría B"),
            ("C", "Categoría C"),
            ("D", "Categoría D"),
            ("E", "Categoría E"),
            ("F", "Categoría F"),
            ("G", "Categoría G"),
            ("H", "Categoría H"),
            ("I", "Categoría I"),
            ("J", "Categoría J"),
            ("K", "Categoría K"),
        ],
    )

    ingresos_brutos_anuales = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    superficie_maxima_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    energia_maxima_kw = models.PositiveIntegerField()

    alquileres_maximos_anuales = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    precio_unitario_maximo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    vigente_desde = models.DateField()

    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categoria", "-vigente_desde"]
        verbose_name = "Categoría de Monotributo"
        verbose_name_plural = "Categorías de Monotributo"

    def __str__(self):
        return f"Categoría {self.categoria}"

    @property
    def superficie_display(self):
        return f"Hasta {self.superficie_maxima_m2:g} m²"

    @property
    def energia_display(self):
        return f"Hasta {self.energia_maxima_kw:,}".replace(",", ".") + " kWh"


class Tenant(TenantMixin):

    nombre = models.CharField(max_length=150)

    razon_social = models.CharField(max_length=200)

    cuit = models.CharField(
        max_length=20,
        unique=True,
    )

    email = models.EmailField()

    telefono = models.CharField(
        max_length=50,
        blank=True,
    )

    direccion = models.CharField(
        max_length=255,
        blank=True,
    )

    localidad = models.CharField(
        max_length=100,
        blank=True,
    )

    provincia = models.CharField(
        max_length=100,
        blank=True,
    )

    condicion_fiscal = models.CharField(
        max_length=50,
        choices=[
            ("MONOTRIBUTO", "Monotributo"),
            ("RESPONSABLE_INSCRIPTO", "Responsable Inscripto"),
            ("EXENTO", "Exento"),
            ("CONSUMIDOR_FINAL", "Consumidor Final"),
        ],
    )

    categoria_monotributo = models.CharField(
        max_length=1,
        choices=[
            ("A", "A"),
            ("B", "B"),
            ("C", "C"),
            ("D", "D"),
            ("E", "E"),
            ("F", "F"),
            ("G", "G"),
            ("H", "H"),
            ("I", "I"),
            ("J", "J"),
            ("K", "K"),
        ],
        blank=True,
    )

    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    auto_create_schema = True

    def __str__(self):
        return f"{self.razon_social} ({self.cuit})"


class Domain(DomainMixin):
    pass
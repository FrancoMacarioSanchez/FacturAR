from django.contrib import admin

from subscriptions.models import Plan, Suscripcion, UsoDiario

# Register your models here.
admin.site.register(Plan)
admin.site.register(Suscripcion)
admin.site.register(UsoDiario)
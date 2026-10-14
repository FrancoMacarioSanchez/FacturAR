from django import forms
from .models import Tenant # Asegúrate de importar tu modelo

class EditarTenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        # AQUI RESTRINGIMOS QUÉ SE PUEDE EDITAR:
        fields = ['email', 'telefono', 'direccion'] 
        
        # Le damos un poco de estilo con Tailwind a los inputs
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'w-full border border-slate-300 rounded-lg px-4 py-2 mt-1 focus:outline-none focus:border-blue-500'}),
            'telefono': forms.TextInput(attrs={'class': 'w-full border border-slate-300 rounded-lg px-4 py-2 mt-1 focus:outline-none focus:border-blue-500'}),
            'direccion': forms.TextInput(attrs={'class': 'w-full border border-slate-300 rounded-lg px-4 py-2 mt-1 focus:outline-none focus:border-blue-500'}),
        }
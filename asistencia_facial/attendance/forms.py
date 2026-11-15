from django import forms

from .models import Persona


class PersonaForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = ["codigo", "nombres"]
        widgets = {
            "codigo": forms.TextInput(attrs={"placeholder": "Ej. 0912345678", "autocomplete": "off"}),
            "nombres": forms.TextInput(attrs={"placeholder": "Nombres y apellidos", "autocomplete": "off"}),
        }

    def clean_nombres(self):
        return " ".join(self.cleaned_data["nombres"].split()).title()

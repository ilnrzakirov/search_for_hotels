from django import forms

from  .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            'extr_id',
            'name',
            'city',
            'city_id',
            'dist_min',
            'dist_max',
            'price_min',
            'price_max',
            'page_size',
        )
        widgets = {
            'name' : forms.TextInput,
            'city' : forms.TextInput,
        }
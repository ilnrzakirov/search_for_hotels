from django.contrib import admin

from .models import Profile
from .forms import ProfileForm
from .models import Message

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'extr_id', 'name', 'city', 'city_id')
    form = ProfileForm

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile', 'text', 'created_at')


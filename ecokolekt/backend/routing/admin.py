from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Route

admin.site.register(Route, GISModelAdmin)

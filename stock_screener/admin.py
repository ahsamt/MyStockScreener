from django.contrib import admin
from .models import User, SavedSearch, SignalConstructor

admin.site.register(User)
admin.site.register(SavedSearch)
admin.site.register(SignalConstructor)
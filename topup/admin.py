from django.contrib import admin
from .models import TopUpPackage,TopUpGame, TopUpField, TopUpFieldHelp, TopUpUserData


admin.site.register(TopUpPackage)
admin.site.register(TopUpGame)
admin.site.register(TopUpField)
admin.site.register(TopUpFieldHelp)
admin.site.register(TopUpUserData)

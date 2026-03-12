from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(AdminProfile)
admin.site.register(UserSettings)
admin.site.register(UserActivityLog)
admin.site.register(EmailOTP)
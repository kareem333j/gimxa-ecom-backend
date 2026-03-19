import rest_framework
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.conf.urls.static import static

"""
ملاحظات متنساش
سجل لوجز للحاجات المهمة
إضافة وظيفة لمسح التوكينز المنتهية كل يوم في الخلفية
متنساش تغير مدة التوكين
ظبط مسارات تحميل الصور
"""

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/users/', include('users.urls')),
    path('api/v1/auth/', include('users_auth.urls')),
    path('api/v1/catalog/', include('catalog.urls')),
    path('api/v1/topup/', include('topup.urls')),
    path('api/v1/cart/', include('cart.urls')),
    path('api/v1/codes/', include('codes.urls')),
    path('api/v1/coupons/', include('coupons.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/dashboard/', include('dashboard.urls')),
    path('api/v1/orders/', include('orders.urls')),
    path('api/v1/dashboard/', include('dashboard.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/auth', include("rest_framework.urls")),
    
    # OpenAPI Schema
    path(
        "api/schema/",
        SpectacularAPIView.as_view(
            authentication_classes=[],
            permission_classes=[AllowAny],
        ),
        name="schema",
    ),

    # Swagger UI
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            authentication_classes=[],
            permission_classes=[AllowAny],
        ),
        name="swagger-ui",
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
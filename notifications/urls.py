from django.urls import path
from notifications.views.public import *
from notifications.views.admin import *

urlpatterns = [
    # public
    path("all/", NotificationListView.as_view(), name="notification_list"),
    path("all/delete/", NotificationDeleteView.as_view(), name="notification_delete_all"),
    path("notification/<str:notification_id>/", NotificationDetailView.as_view(), name="notification_detail"),
    
    # admin
    path("admin/all/", NotificationAdminListView.as_view(), name="notification_admin_list"),
    path("admin/notification/<str:notification_id>/", NotificationAdminDetailView.as_view(), name="notification_admin_detail"),
]
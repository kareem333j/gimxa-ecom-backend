from django.urls import path
from users.views.public import (
    UserSimpleView, 
    UserSelfProfileView, 
    UserActivityLogsView, 
    UserProfileView,
    UserLocationView,
    UserProfileCurrencyView
)
from users.views.admin import (
    UserListView,
    UserDetail
)

urlpatterns = [
    # public
    path("user/<str:user_id>/", UserSimpleView.as_view(), name="user-simple"),
    path("user/my/profile/", UserSelfProfileView.as_view(), name="user-profile"),
    path("user/my/profile/update/", UserSelfProfileView.as_view(), name="user-profile-update"),
    path("user/<str:user_id>/profile/", UserProfileView.as_view(), name="user-profile"),
    path("user/<str:user_id>/profile/currency/", UserProfileCurrencyView.as_view(), name="user-profile-currency"),
    path("user/<str:user_id>/logs/", UserActivityLogsView.as_view(), name="user-logs"),

    # admin
    path("admin/users/", UserListView.as_view(), name="admin-user-list"),
    path("user/<str:user_id>/profile/update/", UserDetail.as_view(), name="admin-user-profile-update"),
    path("user/<str:user_id>/delete/", UserDetail.as_view(), name="admin-user-profile-delete"),
    path("user/<str:user_id>/location/current/", UserLocationView.as_view(), name="admin-user-location"),
]
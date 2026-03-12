from django.urls import path
from catalog.views.admin import *
from catalog.views.public import *
from catalog.views.search import SimpleSearchView, AdvancedSearchView
from catalog.views.search import *

urlpatterns = [
    # puclic
    path("public/categories/", CategoryListView.as_view(), name="category-list"),
    path("public/categories/<slug:slug>/", CategoryDetailView.as_view(), name="category-detail-view"),
    path("public/tags/", TagListView.as_view(), name="tag-list"),
    path("public/products/", ProductListView.as_view(), name="product-list"),
    path("public/products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    # search
    path("public/search/simple/", SimpleSearchView.as_view(), name="public-simple-search"),
    path("public/search/advanced/", AdvancedSearchView.as_view(), name="public-advanced-search"),
    # admin
    path("admin/categories/", CategoryAdminView.as_view(), name="admin-category-view"),
    path("admin/categories/<slug:slug>/", CategoryAdminDetailView.as_view(), name="admin-category-detail-view"),
    path("admin/tags/", TagAdminView.as_view(), name="admin-tag-view"),
    path("admin/tags/<slug:slug>/", TagAdminDetailView.as_view(), name="admin-tag-detail-view"),
    path("admin/products/", ProductAdminListView.as_view(), name="admin-product-view"),
    path("admin/products/<slug:slug>/", ProductDetailAdminView.as_view(), name="admin-product-detail-view"),
    path("admin/products/<slug:slug>/images/", ProductImageAdminView.as_view(), name="admin-product-image-view"),
    path("admin/products/<slug:slug>/images/<int:image_id>/", ProductImageAdminView.as_view(), name="admin-product-image-detail-view"),
    path("admin/products/<slug:slug>/attributes/", ProductAttributeAdminView.as_view(), name="admin-product-attribute-view"),
    path("admin/products/<slug:slug>/attributes/<int:attribute_id>/", ProductAttributeAdminView.as_view(), name="admin-product-attribute-detail-view"),
]
from django.contrib import admin
from .models import Category, Product, ProductAttribute, ProductImage, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'parent')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'get_categories', 'product_type', 'is_active', 'is_available', 'price')
    list_filter = ('is_active', 'is_available', 'product_type', 'category', 'tags')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductAttributeInline, ProductImageInline]
    filter_horizontal = ('tags','category')
    def get_categories(self, obj):
        return ", ".join(c.name for c in obj.category.all())

    get_categories.short_description = "Categories"


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'value')
    list_filter = ('product',)
    search_fields = ('product__name', 'name', 'value')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image')
    list_filter = ('product',)
    search_fields = ["product__name"]

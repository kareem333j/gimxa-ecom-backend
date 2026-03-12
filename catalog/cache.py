from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Product

@receiver([post_save, post_delete], sender=Product)
def clear_product_cache(sender, **kwargs):
    # delete cache for all product list pages (assuming pagination up to 100 pages)
    for i in range(1, 101):
        cache.delete(f'product_list_cache_page_{i}')

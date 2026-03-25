from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
# from rest_framework.pagination import PageNumberPagination
from core.pagination import DynamicPageNumberPagination
from payments.services.currency_service import CurrencyService, get_user_currency

from catalog.models import Product
from catalog.utils.choices import ProductType
from rest_framework.permissions import AllowAny
from users_auth.authentication import OptionalJWTAuthentication

# class CustomPagination(PageNumberPagination):
#     page_size = 24
#     page_size_query_param = 'page_size'
#     max_page_size = 100

def _get_image_url(request, image_field):
    if image_field and hasattr(image_field, 'url'):
        return request.build_absolute_uri(image_field.url)
    return None

def serialize_product_row(product, request, advanced=False, currency="USD", service=None):
    main_image = product.images.filter(is_main=True).first()
    main_image_url = _get_image_url(request, main_image.image) if main_image else None
    
    logo_url = _get_image_url(request, product.logo)
    if product.product_type == ProductType.TOPUP and hasattr(product, 'topup'):
        if product.topup.logo:
            logo_url = _get_image_url(request, product.topup.logo)

    # start_from: min active package price for topup products
    start_from = None
    if product.product_type == ProductType.TOPUP and hasattr(product, 'topup'):
        min_pkg = product.topup.packages.filter(is_active=True).order_by('price').first()
        if min_pkg:
            start_from = min_pkg.price

    price = product.price
    if service and currency != "USD":
        if price is not None:
            price = round(service.convert(price, currency), 2)
        if start_from is not None:
            start_from = round(service.convert(start_from, currency), 2)

    data = {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "is_popular": product.is_popular,
        "region":product.region,
        "is_featured":product.is_featured,
        "price": str(price) if price is not None else None,
        "product_type": product.product_type,
        "short_description": product.short_description,
        "logo": logo_url,
        "main_image": main_image_url if main_image else None,
        "is_available": product.is_available,
        "start_from": str(start_from) if start_from is not None else None,
        "currency": currency,
    }
    
    if advanced:
        data["description"] = product.description
        data["tags"] = [
            {"id": tag.id, "name": tag.name, "slug": tag.slug} 
            for tag in product.tags.filter(is_active=True)
        ]
        data["categories"] = [
            {"name": cat.name, "slug": cat.slug, "id": cat.id} 
            for cat in product.category.filter(is_active=True)
        ]
        
    return data

def serialize_package_row(product, package, request, advanced=False, currency="USD", service=None):
    base_data = serialize_product_row(product, request, advanced, currency, service)
    
    # Override price and image for package
    price = package.price
    if service and currency != "USD" and price is not None:
        price = round(service.convert(price, currency), 2)
        
    base_data["price"] = str(price) if price is not None else None
    
    if package.image:
        package_image_url = _get_image_url(request, package.image)
        base_data["main_image"] = package_image_url if package.image else None
    
    # Add package data
    base_data["package"] = {
        "id": package.id,
        "name": package.name,
        "amount": package.amount,
        "image": _get_image_url(request, package.image),
    }

    base_data['is_popular'] = package.is_popular
    
    return base_data

def get_search_results(request, advanced=False):
    search_query = request.query_params.get('search', '').strip()
    
    if not search_query and not advanced:
        return []
        
    currency = get_user_currency(request)
    service = CurrencyService()
        
    products = Product.objects.filter(is_active=True).prefetch_related(
        'images', 'category', 'tags', 'topup__packages'
    )
    
    if search_query:
        # User requested search by name, short_description or description
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(slug__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(description__icontains=search_query)
        ).distinct()
        
    if advanced:
        tags = request.query_params.get('tags')
        if tags:
            # check if comma separated slugs
            tag_list = [t.strip() for t in tags.split(',')]
            products = products.filter(tags__slug__in=tag_list)
            
        categories = request.query_params.get('categories')
        if categories:
            cat_list = [c.strip() for c in categories.split(',')]
            products = products.filter(category__slug__in=cat_list)
            
        region = request.query_params.get('region')
        if region:
            products = products.filter(region=region)
            
        is_popular = request.query_params.get('is_popular')
        if is_popular:
            is_popular_bool = is_popular.lower() in ['true', '1', 'yes']
            products = products.filter(is_popular=is_popular_bool)

        is_featured = request.query_params.get('is_featured')
        if is_featured:
            is_featured_bool = is_featured.lower() in ['true', '1', 'yes']
            products = products.filter(is_featured=is_featured_bool)

            
        is_available = request.query_params.get('is_available')
        if is_available:
            is_available_bool = is_available.lower() in ['true', '1', 'yes']
            products = products.filter(is_available=is_available_bool)
            
        topups = request.query_params.get('topups')
        if topups:
            if topups.lower() in ['true', '1', 'yes']:
                products = products.filter(product_type=ProductType.TOPUP)
            elif topups.lower() in ['false', '0', 'no']:
                products = products.exclude(product_type=ProductType.TOPUP)

    products = products.distinct()
    
    results = []
    
    for product in products:
        if product.product_type == ProductType.TOPUP and hasattr(product, 'topup'):
            packages = product.topup.packages.filter(is_active=True)
            if packages.exists():
                for package in packages:
                    if advanced:
                        is_pop = request.query_params.get('is_popular')
                        if is_pop:
                            is_pop_bool = is_pop.lower() in ['true', '1', 'yes']
                            if package.is_popular != is_pop_bool:
                                continue
                    results.append(serialize_package_row(product, package, request, advanced, currency, service))
            else:
                results.append(serialize_product_row(product, request, advanced, currency, service))
        else:
            results.append(serialize_product_row(product, request, advanced, currency, service))

    # Price range filter (applied on built list so topup expanded rows work correctly)
    if advanced:
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')

        if price_min:
            try:
                price_min_val = float(price_min)
                results = [
                    r for r in results
                    if r.get('price') is not None and float(r['price']) >= price_min_val
                ]
            except ValueError:
                pass

        if price_max:
            try:
                price_max_val = float(price_max)
                results = [
                    r for r in results
                    if r.get('price') is not None and float(r['price']) <= price_max_val
                ]
            except ValueError:
                pass

    # Sort results: ordering by price if requested, else by is_popular descending
    ordering = request.query_params.get('ordering') if advanced else None
    if ordering in ('price', '-price'):
        reverse = ordering == '-price'
        results.sort(
            key=lambda x: float(x['price']) if x.get('price') is not None else 0,
            reverse=reverse
        )
    else:
        results.sort(
            key=lambda x: (
                x.get('is_popular', False),
                x.get('package', {}).get('is_popular', False) if 'package' in x else False
            ),
            reverse=True
        )
    
    return results

class SimpleSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]
    
    def get(self, request, *args, **kwargs):
        results = get_search_results(request, advanced=False)
        
        # Limit to 24 rows
        results_subset = results[:24]
        
        search_query = request.query_params.get('search', '')
        
        return Response({
            "products": results_subset,
            "total_count": len(results),
            "view_all": f"/products?name={search_query}" if search_query else "/products"
        })

class AdvancedSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]
    
    def get(self, request, *args, **kwargs):
        results = get_search_results(request, advanced=True)
        paginator = DynamicPageNumberPagination(page_size=24)
        page = paginator.paginate_queryset(results, request, view=self)
        
        if page is not None:
            return paginator.get_paginated_response(page)
            
        return Response({
            "count": len(results),
            "next": None,
            "previous": None,
            "results": results
        })
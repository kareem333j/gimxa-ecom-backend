from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from cart.serializers import CartSerializer, AddToCartSerializer, CartItemUpdateSerializer
from cart.models import CartItem
from topup.models import TopUpPackage
from cart.utils.helpers import get_or_create_cart, make_topup_hash
from core.response_schema import get_response_schema_1
import json
from cart.utils.helpers import build_cookie_cart_response
from django.db import transaction
from users_auth.authentication import OptionalJWTAuthentication


class CartItemCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if request.user.is_authenticated:
            return self._add_to_db_cart(request, serializer)
        else:
            return self._add_to_cookie_cart(request, serializer)

    def _add_to_db_cart(self, request, serializer):
        with transaction.atomic():
            cart = get_or_create_cart(request.user)
            product = serializer.validated_data["product"]
            quantity = serializer.validated_data["quantity"]
            is_topup = serializer.validated_data["is_topup"]

            topup_package = None
            unit_price = product.price

            if is_topup:
                try:
                    topup_package = TopUpPackage.public.get(
                        id=serializer.validated_data["topup_package_id"],
                        game__product=product
                    )
                except TopUpPackage.DoesNotExist:
                    return Response(get_response_schema_1(
                        data={},
                        status=400,
                        message="Top-up package not found or inactive"
                    ), status=400)
                    
                unit_price = topup_package.price

            topup_data = serializer.validated_data.get("topup_data", {})
            topup_hash = None

            if is_topup:
                topup_hash = make_topup_hash(topup_data)

            item = (
                CartItem.objects
                .select_for_update()
                .filter(
                    cart=cart,
                    product=product,
                    topup_package=topup_package,
                    topup_hash=topup_hash
                )
                .first()
            )

            if item:
                item.quantity += quantity
                item.unit_price = unit_price
                if is_topup:
                    item.topup_data = topup_data
                item.save()
            else:
                CartItem.objects.create(
                    cart=cart,
                    product=product,
                    topup_package=topup_package,
                    topup_hash=topup_hash,
                    topup_data=topup_data if is_topup else None,
                    quantity=quantity,
                    unit_price=unit_price,
                    is_topup=is_topup,
                )
            

        return Response(get_response_schema_1(
            data=CartSerializer(cart, context={"request": request}).data,
            status=201, 
            message="Added to cart"
        ), status=201)

    def _add_to_cookie_cart(self, request, serializer):
        cart = request.COOKIES.get("cart")
        cart = json.loads(cart) if cart else {"items": []}
        product = serializer.validated_data["product"]
        unit_price = product.price
        if serializer.validated_data["is_topup"]:
            try:
                package = TopUpPackage.public.get(
                    id=serializer.validated_data["topup_package_id"],
                    game__product=product
                )
            except TopUpPackage.DoesNotExist:
                return Response(get_response_schema_1(
                    data={},
                    status=400,
                    message="Top-up package not found or inactive"
                ), status=400)
                
            unit_price = package.price
            
        quantity = serializer.validated_data["quantity"]
        
        found = False

        topup_data = serializer.validated_data.get("topup_data", {}) 
        topup_hash = make_topup_hash(topup_data) if serializer.validated_data["is_topup"] else None 

        for item in cart["items"]:
            if (
                item.get("product", {}).get("slug") == product.slug
                and item.get("topup_package") == serializer.validated_data.get("topup_package_id") 
                and item.get("topup_hash") == topup_hash 
            ):
                item["quantity"] += quantity
                item["total_price"] = str(
                    Decimal(item["unit_price"]) * item["quantity"]
                )
                found = True
                break

        if not found:
            cart["items"].append({
                "product":{
                    "id": product.id,
                    "name": product.name,
                    "slug": product.slug,
                    "is_topup": serializer.validated_data["is_topup"],
                },
                "quantity": quantity,
                "unit_price": str(unit_price),
                "total_price": str(unit_price * quantity),
                "topup_package": serializer.validated_data.get("topup_package_id"),
                "topup_data": serializer.validated_data.get("topup_data"),
                "topup_hash": topup_hash, 
            })
            
        cart_response = build_cookie_cart_response(cart["items"], cart.get("coupon"), request=request)

        response = Response(get_response_schema_1(
            data=cart_response,
            status=201,
            message="Added to cart"
        ), status=201)

        response.set_cookie("cart", json.dumps(cart), max_age=7 * 24 * 60 * 60)
        return response


class CartDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request):
        user = request.user
        if user.is_authenticated:
            cart = get_or_create_cart(user)
            # update prices
            items_to_update = []

            for item in cart.items.select_related("product", "topup_package"):
                if item.is_topup and item.topup_package:
                    current_price = item.topup_package.price
                else:
                    current_price = item.product.price

                if item.unit_price != current_price:
                    item.unit_price = current_price
                    item.total_price = current_price * item.quantity
                    items_to_update.append(item)

            if items_to_update:
                CartItem.objects.bulk_update(
                    items_to_update,
                    ["unit_price", "total_price"]
                )

            serializer = CartSerializer(cart, context={"request": request})
            return Response(get_response_schema_1(
                data=serializer.data,
                status=200,
                message="Cart retrieved successfully"
            ), status=200)
        else:
            cart_raw = request.COOKIES.get("cart")
            cart = json.loads(cart_raw) if cart_raw else {"items": []}
            cart_response = build_cookie_cart_response(cart["items"], cart.get("coupon"), request=request)
            return Response(get_response_schema_1(
                data=cart_response,
                status=200,
                message="Cart retrieved successfully"
            ), status=200)
            
    def delete(self, request):
        user = request.user
        if user.is_authenticated:
            cart = get_or_create_cart(user)
            cart.delete()
            return Response(get_response_schema_1(
                data={},
                status=204,
                message="Cart cleared successfully"
            ), status=204)
        else:
            response = Response(get_response_schema_1(
                data={},
                status=204,
                message="Cart cleared successfully"
            ), status=204)
            response.delete_cookie("cart")
            return response
        
class CartItemUpdateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def patch(self, request):
        """
            body:
            {
                "product_slug": "mobile-legends",
                "topup_package_id": 1,
                "topup_data": {...},
                "action": "increase" | "decrease"
            }
        """
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if request.user.is_authenticated:
            return self._update_db_cart(request, serializer)
        else:
            return self._update_cookie_cart(request, serializer)

    def _update_db_cart(self, request, serializer):
        with transaction.atomic():
            cart = get_or_create_cart(request.user)
            product = serializer.validated_data["product"]
            is_topup = serializer.validated_data["is_topup"]

            quantity = request.data.get("quantity")
            quantity_delta = request.data.get("quantity_delta")

            if quantity is not None and quantity_delta is not None:
                return Response(
                    get_response_schema_1({}, 400, "Use either quantity or quantity_delta"),
                    status=400
                )

            topup_package = None
            if is_topup:
                topup_package = TopUpPackage.public.get(
                    id=serializer.validated_data["topup_package_id"],
                    game__product=product
                )

            topup_data = serializer.validated_data.get("topup_data", {})
            topup_hash = make_topup_hash(topup_data) if is_topup else None

            item = (
                CartItem.objects
                .select_for_update()
                .filter(
                    cart=cart,
                    product=product,
                    topup_package=topup_package,
                    topup_hash=topup_hash
                )
                .first()
            )

            if not item:
                return Response(
                    get_response_schema_1({}, 404, "Item not found"),
                    status=404
                )

            if quantity is not None:
                try:
                    quantity = int(quantity)
                except ValueError:
                    return Response(
                        get_response_schema_1({}, 400, "Invalid quantity"),
                        status=400
                    )

                if quantity <= 0:
                    item.delete()
                else:
                    item.quantity = quantity
                    item.save()

            elif quantity_delta is not None:
                try:
                    quantity_delta = int(quantity_delta)
                except ValueError:
                    return Response(
                        get_response_schema_1({}, 400, "Invalid quantity_delta"),
                        status=400
                    )

                new_quantity = item.quantity + quantity_delta

                if new_quantity <= 0:
                    item.delete()
                else:
                    item.quantity = new_quantity
                    item.save()

            else:
                return Response(
                    get_response_schema_1({}, 400, "quantity or quantity_delta required"),
                    status=400
                )

            return Response(
                get_response_schema_1(
                    CartSerializer(cart, context={"request": request}).data,
                    200,
                    "Cart updated"
                ),
                status=200
            )
    
    def _update_cookie_cart(self, request, serializer):
        cart = request.COOKIES.get("cart")
        cart = json.loads(cart) if cart else {"items": []}

        product = serializer.validated_data["product"]
        is_topup = serializer.validated_data["is_topup"]

        quantity = request.data.get("quantity")
        quantity_delta = request.data.get("quantity_delta")

        if quantity is not None and quantity_delta is not None:
            return Response(
                get_response_schema_1({}, 400, "Use either quantity or quantity_delta"),
                status=400
            )

        topup_data = serializer.validated_data.get("topup_data", {})
        topup_hash = make_topup_hash(topup_data) if is_topup else None

        for item in cart["items"]:
            if (
                item.get("product", {}).get("slug") == product.slug
                and item.get("topup_hash") == topup_hash
            ):

                if quantity is not None:
                    quantity = int(quantity)
                    if quantity <= 0:
                        cart["items"].remove(item)
                        break
                    item["quantity"] = quantity

                elif quantity_delta is not None:
                    quantity_delta = int(quantity_delta)
                    new_quantity = item["quantity"] + quantity_delta

                    if new_quantity <= 0:
                        cart["items"].remove(item)
                        break
                    item["quantity"] = new_quantity

                else:
                    return Response(
                        get_response_schema_1({}, 400, "quantity or quantity_delta required"),
                        status=400
                    )

                item["total_price"] = str(
                    Decimal(item["unit_price"]) * item["quantity"]
                )
                break

        cart_response = build_cookie_cart_response(cart["items"], cart.get("coupon"), request=request)

        response = Response(
            get_response_schema_1(cart_response, 200, "Cart updated"),
            status=200
        )

        response.set_cookie("cart", json.dumps(cart), max_age=7 * 24 * 60 * 60)
        return response


class CartItemDeleteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def delete(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if request.user.is_authenticated:
            return self._delete_from_db_cart(request, serializer)
        else:
            return self._delete_from_cookie_cart(request, serializer)

    def _delete_from_db_cart(self, request, serializer):
        with transaction.atomic():
            cart = get_or_create_cart(request.user)
            product = serializer.validated_data["product"]
            is_topup = serializer.validated_data["is_topup"]

            topup_package = None
            if is_topup:
                topup_package = TopUpPackage.public.get(
                    id=serializer.validated_data["topup_package_id"],
                    game__product=product
                )

            topup_data = serializer.validated_data.get("topup_data", {})
            topup_hash = make_topup_hash(topup_data) if is_topup else None

            item = CartItem.objects.filter(
                cart=cart,
                product=product,
                topup_package=topup_package,
                topup_hash=topup_hash
            ).first()

            if not item:
                return Response(
                    get_response_schema_1({}, 404, "Item not found"),
                    status=404
                )

            item.delete()

            return Response(
                get_response_schema_1(
                    CartSerializer(cart, context={"request": request}).data,
                    200,
                    "Item removed successfully"
                ),
                status=200
            )

    def _delete_from_cookie_cart(self, request, serializer):
        cart = request.COOKIES.get("cart")
        cart = json.loads(cart) if cart else {"items": []}

        product = serializer.validated_data["product"]
        is_topup = serializer.validated_data["is_topup"]

        topup_data = serializer.validated_data.get("topup_data", {})
        topup_hash = make_topup_hash(topup_data) if is_topup else None

        cart["items"] = [
            item for item in cart["items"]
            if not (
                item.get("product", {}).get("slug") == product.slug
                and item.get("topup_hash") == topup_hash
            )
        ]

        cart_response = build_cookie_cart_response(cart["items"], cart.get("coupon"), request=request)

        response = Response(
            get_response_schema_1(
                cart_response,
                200,
                "Item removed successfully"
            ),
            status=200
        )

        response.set_cookie("cart", json.dumps(cart), max_age=7 * 24 * 60 * 60)
        return response
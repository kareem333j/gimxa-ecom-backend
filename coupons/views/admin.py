from rest_framework.views import APIView
from rest_framework.response import Response

from core.response_schema import get_response_schema_1
from coupons.models import Coupon, CouponProduct, CouponCategory, CouponPackage, CouponUsage
from coupons.serializers import (
    CouponSerializer,
    CouponUsageSerializer,
    AdminCouponCreateSerializer,
    AdminCouponProductCreateSerializer,
    AdminCouponCategoryCreateSerializer,
    AdminCouponPackageCreateSerializer,
    SimpleCouponSerializer,
)
from permissions.custom import AdminPermission
from users_auth.authentication import CookieJWTAuthentication


class AdminCouponListCreateView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        coupons = Coupon.objects.all().order_by("-created_at")
        
        is_active = request.query_params.get("is_active")
        scope = request.query_params.get("scope")
        
        if is_active is not None:
            coupons = coupons.filter(is_active=is_active.lower() == "true")
        if scope:
            coupons = coupons.filter(scope=scope)
        
        serializer = SimpleCouponSerializer(coupons, many=True)
        return Response(
            get_response_schema_1(serializer.data, 200, "coupons fetched successfully"),
            status=200
        )

    def post(self, request):
        serializer = AdminCouponCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        coupon = serializer.save()
        
        return Response(
            get_response_schema_1(
                CouponSerializer(coupon).data,
                201,
                "coupon created successfully"
            ),
            status=201
        )


class AdminCouponDetailView(APIView):
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get_object(self, pk):
        return Coupon.objects.filter(pk=pk).first()

    def get(self, request, pk):
        coupon = self.get_object(pk)
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        serializer = CouponSerializer(coupon)
        return Response(
            get_response_schema_1(serializer.data, 200, "coupon details fetched successfully"),
            status=200
        )

    def put(self, request, pk):
        coupon = self.get_object(pk)
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        serializer = AdminCouponCreateSerializer(coupon, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            get_response_schema_1(
                CouponSerializer(coupon).data,
                200,
                "coupon updated successfully"
            ),
            status=200
        )

    def delete(self, request, pk):
        coupon = self.get_object(pk)
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        if coupon.used_count > 0:
            return Response(
                get_response_schema_1(
                    {},
                    400,
                    "coupon can't be deleted because it has been used"
                ),
                status=400
            )
        
        coupon.delete()
        return Response(
            get_response_schema_1({}, 204, "coupon deleted successfully"),
            status=204
        )


class AdminCouponProductView(APIView):
    """
    إدارة منتجات الكوبون
    POST /api/admin/coupons/<coupon_id>/products/
    DELETE /api/admin/coupons/<coupon_id>/products/<product_id>/
    """
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, coupon_id):
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        data = request.data.copy()
        data["coupon"] = coupon_id
        
        serializer = AdminCouponProductCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            get_response_schema_1(
                CouponSerializer(coupon).data,
                201,
                "product added to coupon successfully"
            ),
            status=201
        )

    def delete(self, request, coupon_id, product_id):
        coupon_product = CouponProduct.objects.filter(
            coupon_id=coupon_id,
            product_id=product_id
        ).first()
        
        if not coupon_product:
            return Response(
                get_response_schema_1({}, 404, "product not found in coupon"),
                status=404
            )
        
        coupon_product.delete()
        return Response(
            get_response_schema_1({}, 204, "product removed from coupon successfully"),
            status=204
        )


class AdminCouponCategoryView(APIView):
    """
    إدارة فئات الكوبون
    POST /api/admin/coupons/<coupon_id>/categories/
    DELETE /api/admin/coupons/<coupon_id>/categories/<category_id>/
    """
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, coupon_id):
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        data = request.data.copy()
        data["coupon"] = coupon_id
        
        serializer = AdminCouponCategoryCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            get_response_schema_1(
                CouponSerializer(coupon).data,
                201,
                "category added to coupon successfully"
            ),
            status=201
        )

    def delete(self, request, coupon_id, category_id):
        coupon_category = CouponCategory.objects.filter(
            coupon_id=coupon_id,
            category_id=category_id
        ).first()
        
        if not coupon_category:
            return Response(
                get_response_schema_1({}, 404, "category not found in coupon"),
                status=404
            )
        
        coupon_category.delete()
        return Response(
            get_response_schema_1({}, 204, "category removed from coupon successfully"),
            status=204
        )


class AdminCouponUsageListView(APIView):
    """
    قائمة استخدامات الكوبون
    GET /api/admin/coupons/<coupon_id>/usages/
    """
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, coupon_id):
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        usages = CouponUsage.objects.filter(coupon=coupon).select_related(
            "user", "order"
        ).order_by("-used_at")
        
        serializer = CouponUsageSerializer(usages, many=True)
        return Response(
            get_response_schema_1(serializer.data, 200, "coupon usages fetched successfully"),
            status=200
        )


class AdminCouponPackageView(APIView):
    """
    إدارة باقات الكوبون
    POST /api/admin/coupons/<coupon_id>/packages/
    DELETE /api/admin/coupons/<coupon_id>/packages/<package_id>/
    """
    permission_classes = [AdminPermission]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, coupon_id):
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if not coupon:
            return Response(
                get_response_schema_1({}, 404, "coupon not found"),
                status=404
            )
        
        data = request.data.copy()
        data["coupon"] = coupon_id
        
        serializer = AdminCouponPackageCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            get_response_schema_1(
                CouponSerializer(coupon).data,
                201,
                "package added to coupon successfully"
            ),
            status=201
        )

    def delete(self, request, coupon_id, package_id):
        coupon_package = CouponPackage.objects.filter(
            coupon_id=coupon_id,
            package_id=package_id
        ).first()
        
        if not coupon_package:
            return Response(
                get_response_schema_1({}, 404, "package not found in coupon"),
                status=404
            )
        
        coupon_package.delete()
        return Response(
            get_response_schema_1({}, 204, "package removed from coupon successfully"),
            status=204
        )

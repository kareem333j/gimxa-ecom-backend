from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from catalog.models import Product, Category
from orders.services.services import OrderService, OrderItemData
from coupons.models import Coupon
from coupons.utils.choices import CouponScope, DiscountType
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class MockPaymentGateway:
    def __init__(self, tax_rate):
        self.tax_rate = tax_rate

class OrderServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.product1 = Product.objects.create(
            name='Product 1',
            slug='product-1',
            price=Decimal('100.0000'),
            is_active=True
        )
        self.product1.category.add(self.category)
        
        self.product2 = Product.objects.create(
            name='Product 2',
            slug='product-2',
            price=Decimal('50.0000'),
            is_active=True
        )
        
        self.coupon = Coupon.objects.create(
            code='SAVE10',
            activity='active',
            scope=CouponScope.GLOBAL,
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal('10.0000'),
            start_at=timezone.now() - timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1),
            max_usage=100,
            used_count=0
        )

    def test_create_order_simple(self):
        item_data = OrderItemData(
            product=self.product1,
            quantity=1,
            unit_price=self.product1.price
        )
        
        order, total, error = OrderService.create_order(
            user=self.user,
            items_data=[item_data]
        )
        
        self.assertIsNotNone(order)
        self.assertIsNone(error)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.subtotal, Decimal('100.0000'))
        self.assertEqual(order.total_price, Decimal('100.0000'))
        self.assertEqual(order.tax, Decimal('0.0000'))

    def test_create_order_multiple_items(self):
        items = [
            OrderItemData(self.product1, 1, self.product1.price),
            OrderItemData(self.product2, 2, self.product2.price)
        ]
        
        order, total, error = OrderService.create_order(
            user=self.user,
            items_data=items
        )
        
        # Subtotal: 100*1 + 50*2 = 200
        self.assertEqual(order.subtotal, Decimal('200.0000'))
        self.assertEqual(order.items.count(), 2)

    def test_create_order_with_coupon(self):
        item_data = OrderItemData(
            product=self.product1,
            quantity=1,
            unit_price=Decimal('100.0000')
        )
        
        # Coupon gives 10% off
        order, total, error = OrderService.create_order(
            user=self.user,
            items_data=[item_data],
            coupon_code='SAVE10'
        )
        
        self.assertIsNone(error)
        self.assertEqual(order.coupon_code, 'SAVE10')
        # Discount: 10% of 100 = 10
        self.assertEqual(order.discount_total, Decimal('10.0000'))
        self.assertEqual(order.total_price, Decimal('90.0000'))

    def test_create_order_with_tax(self):
        item_data = OrderItemData(
            product=self.product1,
            quantity=1,
            unit_price=Decimal('100.0000')
        )
        
        # Tax rate 5%
        gateway = MockPaymentGateway(Decimal('5.0000'))
        order, total, error = OrderService.create_order(
            user=self.user,
            items_data=[item_data],
            payment_gateway=gateway
        )
        
        # Tax: 5% of 100 = 5
        self.assertEqual(order.tax, Decimal('5.0000'))
        self.assertEqual(order.total_price, Decimal('105.0000'))

    def test_create_order_with_tax_and_coupon(self):
        item_data = OrderItemData(
            product=self.product1,
            quantity=1,
            unit_price=Decimal('100.0000')
        )
        
        # Tax 5% -> 5.00
        # Discount 10% -> 10.00
        # Total = 100 + 5 - 10 = 95
        gateway = MockPaymentGateway(Decimal('5.0000'))
        order, total, error = OrderService.create_order(
            user=self.user,
            items_data=[item_data],
            coupon_code='SAVE10',
            payment_gateway=gateway
        )
        
        self.assertEqual(order.subtotal, Decimal('100.0000'))
        self.assertEqual(order.tax, Decimal('5.0000'))
        self.assertEqual(order.discount_total, Decimal('10.0000'))
        self.assertEqual(order.total_price, Decimal('95.0000'))

    def test_invalid_coupon(self):
        item_data = OrderItemData(self.product1, 1, self.product1.price)
        
        order, total, error = OrderService.create_order(
            user=self.user,
            items_data=[item_data],
            coupon_code='INVALID'
        )
        
        self.assertIsNone(order)
        self.assertIn("not found", error.lower())

    def test_empty_items(self):
        order, total, error = OrderService.create_order(self.user, [])
        self.assertIsNone(order)
        self.assertEqual(error, "No items to order")

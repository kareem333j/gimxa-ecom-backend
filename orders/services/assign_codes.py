from django.db import transaction
from django.utils import timezone

from catalog.utils.choices import StockMode
from codes.models import FulfillmentCode
from orders.utils.choices import OrderStatus


def fulfill_order_item(item):
    """
    Handles fulfillment logic for a single OrderItem
    Automatic  -> assign codes
    Manual     -> wait for admin action
    """

    source = item.topup_package if item.is_topup else item.product

    if source.stock_mode == StockMode.AUTOMATIC:
        _fulfill_automatic(item, source)
    else:
        _mark_waiting_manual(item)


def _fulfill_automatic(item, source):
    with transaction.atomic():
        codes = (
            source.codes
            .select_for_update()
            .filter(is_used=False)[: item.quantity]
        )

        if codes.count() < item.quantity:
            raise Exception("Not enough available codes")

        for code in codes:
            code.is_used = True
            code.used_at = timezone.now()
            code.save()

        # هنا لاحقًا:
        # send_email()
        # create_notification()

        item.order.status = OrderStatus.COMPLETED
        item.order.save(update_fields=["status"])


def _mark_waiting_manual(item):
    item.order.status = OrderStatus.PAID
    item.order.save(update_fields=["status"])
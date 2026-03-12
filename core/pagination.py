from rest_framework.pagination import PageNumberPagination
import math
from rest_framework.response import Response

class DynamicPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 40

    def __init__(self, page_size=None, max_page_size=None):
        super().__init__()
        if page_size:
            self.page_size = page_size
        if max_page_size:
            self.max_page_size = max_page_size

    def get_paginated_response(self, data):
        total_count = self.page.paginator.count
        page_size = self.page.paginator.per_page
        total_pages = math.ceil(total_count / page_size)

        return Response({
            "count": total_count,
            "total_pages": total_pages,
            "current_page": self.page.number,
            "page_size": page_size,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })

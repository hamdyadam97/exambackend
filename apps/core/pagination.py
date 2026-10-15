"""
Pagination classes with a stable response shape.
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'per_page'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'code': 200,
            'status': True,
            'message': 'Fetched Successfully',
            'data': data,
            'pagination': {
                'total': self.page.paginator.count,
                'count': len(data),
                'per_page': self.get_page_size(self.request),
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'next_page_url': self.get_next_link(),
                'pages': self._build_links(),
            }
        })

    def _build_links(self):
        links = []
        for num in self.page.paginator.page_range:
            links.append({
                'url': self.request.build_absolute_uri(f'?page={num}') if num != self.page.number else None,
                'label': str(num),
                'active': num == self.page.number,
            })
        return links

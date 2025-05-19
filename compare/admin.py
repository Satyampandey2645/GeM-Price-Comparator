from django.contrib import admin
from .models import Product, PriceComparison, SearchHistory, ComparisonHistory

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_at')
    search_fields = ('name', 'category')
    list_filter = ('category', 'created_at')

@admin.register(PriceComparison)
class PriceComparisonAdmin(admin.ModelAdmin):
    list_display = ('product', 'ecommerce_site', 'price', 'last_updated')
    list_filter = ('ecommerce_site', 'last_updated')
    search_fields = ('product__name',)

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'query', 'searched_at')
    list_filter = ('searched_at',)
    search_fields = ('query', 'user__username')

@admin.register(ComparisonHistory)
class ComparisonHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'compared_at')
    list_filter = ('compared_at',)
    search_fields = ('user__username', 'product__name')
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    image_url = models.URLField(blank=True)
    gem_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class PriceComparison(models.Model):
    ECOMMERCE_CHOICES = [
        ('GEM', 'Government e-Marketplace'),
        ('AMAZON', 'Amazon'),
        ('FLIPKART', 'Flipkart'),
        ('SNAPDEAL', 'Snapdeal'),
        ('MEESHO', 'Meesho'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    ecommerce_site = models.CharField(max_length=20, choices=ECOMMERCE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    url = models.URLField()
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'ecommerce_site')
    
    def __str__(self):
        return f"{self.product.name} - {self.ecommerce_site}"

class SearchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    query = models.CharField(max_length=255)
    searched_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.query} - {self.searched_at}"

class ComparisonHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    compared_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"
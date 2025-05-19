from django.urls import path
from .views import HomeView, ProductDetailView, scrape_gem, ProfileView, HistoryView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('product/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('scrape/', scrape_gem, name='scrape_gem'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('history/', HistoryView.as_view(), name='history'),
]
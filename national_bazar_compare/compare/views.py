from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Product, PriceComparison, SearchHistory, ComparisonHistory
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from django.shortcuts import render
from django.views.generic import ListView
from django.db.models import Q
from .models import Product
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from .models import SearchHistory, ComparisonHistory
import requests
from urllib.parse import quote


class HomeView(ListView):
    model = Product
    template_name = 'compare/home.html'
    context_object_name = 'products'
    paginate_by = 10
    
    def get(self, request, *args, **kwargs):
        # Save search history if user is authenticated and there's a query
        query = self.request.GET.get('q')
        if query and self.request.user.is_authenticated:
            SearchHistory.objects.create(user=self.request.user, query=query)
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        
        if query:
            # Search in name, description, and category
            return queryset.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query) |
                Q(category__icontains=query)
            ).distinct().order_by('-created_at')
        
        return queryset.order_by('-created_at')

class ProductDetailView(DetailView):
    model = Product
    template_name = 'compare/product_detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        comparisons = PriceComparison.objects.filter(product=product)
        
        # Save comparison history if user is authenticated
        if self.request.user.is_authenticated:
            ComparisonHistory.objects.create(user=self.request.user, product=product)
        
        context['comparisons'] = comparisons
        return context

@login_required
def scrape_gem(request):
    if request.method == 'POST':
        query = request.POST.get('query', '').strip()
        
        # Save search history if user is authenticated
        if request.user.is_authenticated:
            SearchHistory.objects.create(user=request.user, query=query)
            
        try:
            # Configure retry strategy
            session = requests.Session()
            retries = Retry(
                total=3,  # Maximum retries
                backoff_factor=1,  # Delay between retries
                status_forcelist=[500, 502, 503, 504]  # Retry on these status codes
            )
            session.mount('https://', HTTPAdapter(max_retries=retries))

            # Make request with longer timeout
            response = session.get(
                f"https://mkp.gem.gov.in/search?q={query}",
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                },
                timeout=30  # Increased timeout to 30 seconds
            )
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Debug: Print the first 500 characters of HTML
            # print("HTML Sample:", response.text[:500])
            
            # Extract category groups
            category_groups = soup.select('li.bn-group')  # Each category group
            
            if not category_groups:
                return render(request, 'compare/scrape_error.html', {
                    'error': 'No categories found for the query.',
                    'query': query,
                    'html_sample': response.text[:1000]
                })
            
            # Collect all category links
            category_links = []
            for group in category_groups:
                category_name = group.find('strong').get_text(strip=True)  # Category name
                links = group.select('.bn-list .bn-link a')  # Links within the category
                
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = f"https://mkp.gem.gov.in{href}"
                        category_links.append({
                            'name': category_name,
                            'url': full_url
                        })
            
            if not category_links:
                return render(request, 'compare/scrape_error.html', {
                    'error': 'No valid category links found.',
                    'query': query,
                    'html_sample': response.text[:1000]
                })
            
            # Step 2: Scrape products from each category
            products = []
            for category in category_links:
                try:
                    # logger.info(f"Scraping products from category: {category['name']} ({category['url']})")
                    
                    # Fetch the category page
                    category_response = session.get(
                        category['url'],
                        headers={'User-Agent': 'Mozilla/5.0'},
                        timeout=30
                    )
                    category_response.raise_for_status()
                    
                    # Parse the category page
                    category_soup = BeautifulSoup(category_response.text, 'html.parser')
                    
                    # Extract product items
                    product_items = category_soup.select('.variant-wrapper')  # Updated selector
                    
                    for item in product_items[:10]:  # Limit to 10 products per category
                        try:
                            # Extract product details
                            name_tag = item.select_one('.variant-title a')
                            name = name_tag.get_text(strip=True) if name_tag else 'Unknown Product'
                            
                            price_tag = item.select_one('.variant-final-price .m-w')
                            price_text = price_tag.get_text(strip=True) if price_tag else '0'
                            try:
                                price_value = float(price_text.replace('₹', '').replace(',', '').strip())
                            except ValueError:
                                price_value = 0
                            
                            link_tag = item.select_one('.variant-title a[href]')
                            url = ("https://mkp.gem.gov.in" + link_tag['href']) if link_tag and link_tag.has_attr('href') else ''
                            
                            img_tag = item.select_one('.variant-image img[src]')
                            image_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else ''
                            
                            brand_tag = item.select_one('.variant-brand')
                            brand = brand_tag.get_text(strip=True).replace('Brand:', '').strip() if brand_tag else 'Unknown Brand'
                            
                            moq_tag = item.select_one('.variant-moq')
                            min_order_quantity = moq_tag.get_text(strip=True).replace('Min. Qty. Per Consignee:', '').strip() if moq_tag else 'N/A'
                            
                            # Create/update product
                            product, created = Product.objects.get_or_create(
                                gem_url=url,
                                defaults={
                                    'name': name[:200],
                                    'description': f"{brand} - {min_order_quantity}",
                                    'category': category['name'],
                                    'image_url': image_url,
                                    'gem_url': url
                                }
                            )
                            
                            # Update price comparison
                            PriceComparison.objects.update_or_create(
                                product=product,
                                ecommerce_site='GEM',
                                defaults={'price': price_value, 'url': url}
                            )

                            # Step 3: Compare with Amazon
                            amazon_price = compare_prices_with_ecommerce(name, session)
                            
                            # Update Amazon price comparison
                            if amazon_price:
                                PriceComparison.objects.update_or_create(
                                    product=product,
                                    ecommerce_site='Amazon',
                                    defaults={'price': amazon_price, 'url': f"https://www.amazon.in/s?k={quote(name)}"}
                                )                            
                            
                            products.append(product)
                        
                        except Exception as e:
                            # logger.error(f"Error processing product: {e}")
                            continue
                
                except Exception as e:
                    # logger.error(f"Error processing category link {category['url']}: {e}")
                    continue
            
            if not products:
                return render(request, 'compare/scrape_error.html', {
                    'error': 'No products found in any category.',
                    'query': query,
                    'html_sample': response.text[:1000]
                })
            
            return render(request, 'compare/scrape_results.html', {
                'products': products,
                'query': query
            })
            
        except Exception as e:
            # logger.error(f"Scraping failed: {e}")
            return render(request, 'compare/scrape_error.html', {
                'error': str(e),
                'query': query,
                'html_sample': response.text[:1000] if 'response' in locals() else 'No response captured'
            })
    
    return render(request, 'compare/scrape_form.html')


def compare_prices_with_ecommerce(product_name, session):
    """
    Compare prices of the given product on Amazon and Flipkart.
    """
    amazon_price = None
    
    try:
        # Search on Amazon
        amazon_search_url = f"https://www.amazon.in/s?k={quote(product_name)}"
        amazon_response = session.get(
            amazon_search_url,
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=30
        )
        amazon_response.raise_for_status()
        amazon_soup = BeautifulSoup(amazon_response.text, 'html.parser')
        
        # Extract Amazon price
        amazon_price_tag = amazon_soup.select_one('.a-price-whole')
        if amazon_price_tag:
            try:
                amazon_price = float(amazon_price_tag.get_text(strip=True).replace(',', ''))
            except ValueError:
                amazon_price = None
    
    except Exception as e:
        logger.error(f"Error comparing prices with e-commerce sites: {e}")
    
    return amazon_price

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'compare/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Count searches
        context['search_count'] = SearchHistory.objects.filter(user=user).count()
        
        # Count comparisons
        context['comparison_count'] = ComparisonHistory.objects.filter(user=user).count()
        
        # Count unique products compared
        context['product_count'] = ComparisonHistory.objects.filter(
            user=user
        ).values('product').distinct().count()
        
        return context

class HistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'compare/history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_history'] = SearchHistory.objects.filter(user=self.request.user).order_by('-searched_at')
        context['comparison_history'] = ComparisonHistory.objects.filter(user=self.request.user).order_by('-compared_at')
        return context

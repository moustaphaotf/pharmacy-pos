from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

# Utiliser le site admin par défaut mais avec notre template personnalisé
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/sales/', include('sales.api_urls')),
    path('invoices/', include('sales.invoice_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


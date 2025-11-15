"""
Vues pour la génération de factures.
"""

from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa
from io import BytesIO

from .models import Invoice, Sale


def generate_invoice_html(invoice):
    """
    Génère le HTML de la facture.
    """
    from decimal import Decimal
    from django.db.models import Sum
    
    sale = invoice.sale
    pharmacy_settings = settings.PHARMACY_SETTINGS
    
    # Construire l'URL complète du logo si fourni
    if pharmacy_settings.get('logo_path'):
        from django.contrib.staticfiles.storage import staticfiles_storage
        logo_url = staticfiles_storage.url(pharmacy_settings['logo_path'])
    else:
        logo_url = None
    
    # Calculer le subtotal avant remise pour l'affichage de la remise
    items_subtotal = sale.items.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
    discount_amount = sale.calculate_discount_amount(items_subtotal)
    
    context = {
        'invoice': invoice,
        'sale': sale,
        'pharmacy_settings': {
            **pharmacy_settings,
            'logo_path': logo_url,
        },
        'items_subtotal': items_subtotal,
        'discount_amount': discount_amount,
    }
    
    return render_to_string('sales/invoice.html', context)


def invoice_preview(request, invoice_id):
    """
    Affiche la prévisualisation HTML de la facture.
    """
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    html_content = generate_invoice_html(invoice)
    return HttpResponse(html_content, content_type='text/html')


def invoice_pdf(request, invoice_id):
    """
    Génère et retourne le PDF de la facture.
    """
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    html_content = generate_invoice_html(invoice)
    
    # Générer le PDF avec xhtml2pdf
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_content.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="facture_{invoice.invoice_number}.pdf"'
        return response
    else:
        return HttpResponse('Erreur lors de la génération du PDF', status=500)


def generate_invoice_for_sale(sale, save_pdf=True):
    """
    Génère une facture pour une vente.
    
    Args:
        sale: Instance de Sale
        save_pdf: Si True, sauvegarde le PDF dans le champ pdf de l'Invoice
    
    Returns:
        Instance de Invoice créée
    """
    # Créer la facture
    invoice = Invoice.objects.create(
        sale=sale,
        invoice_date=timezone.now(),
    )
    
    # Générer le HTML
    html_content = generate_invoice_html(invoice)
    
    # Générer le PDF avec xhtml2pdf
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_content.encode("UTF-8")), result)
    
    if pdf.err:
        raise Exception(f'Erreur lors de la génération du PDF: {pdf.err}')
    
    pdf_file = result.getvalue()
    
    # Sauvegarder le PDF si demandé
    if save_pdf:
        from django.core.files.base import ContentFile
        
        filename = f'invoices/facture_{invoice.invoice_number}.pdf'
        invoice.pdf.save(filename, ContentFile(pdf_file), save=True)
    
    return invoice

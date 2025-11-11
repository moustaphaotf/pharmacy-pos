from __future__ import annotations

from io import BytesIO
from typing import Iterable, Optional

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Prefetch, Q

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from sales.models import Invoice, Sale, SaleItem


class Command(BaseCommand):
    help = 'Génère des factures PDF pour les ventes sélectionnées et les rattache aux enregistrements.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--sale-id',
            type=int,
            dest='sale_id',
            help='Génère la facture uniquement pour la vente spécifiée (ID).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regénère les factures même si un PDF existe déjà.',
        )

    def handle(self, *args, **options) -> None:
        sale_id: Optional[int] = options.get('sale_id')
        force: bool = options.get('force', False)

        sales = self._get_sales_queryset(sale_id, force)

        if not sales:
            self.stdout.write(self.style.WARNING('Aucune vente correspondante.'))
            return

        for sale in sales:
            invoice, _ = Invoice.objects.get_or_create(
                sale=sale,
                defaults={'invoice_number': Invoice.generate_invoice_number()},
            )

            if invoice.pdf and not force:
                self.stdout.write(f'Vente #{sale.pk} ignorée (PDF déjà présent).')
                continue

            buffer = BytesIO()
            self._build_pdf(buffer, sale, invoice)
            pdf_name = f'{invoice.invoice_number}.pdf'
            invoice.pdf.save(pdf_name, ContentFile(buffer.getvalue()), save=False)
            invoice.save(update_fields=['pdf', 'updated_at'])
            self.stdout.write(self.style.SUCCESS(f'Facture générée pour la vente #{sale.pk} → {pdf_name}'))

    def _get_sales_queryset(self, sale_id: Optional[int], force: bool) -> Iterable[Sale]:
        queryset = (
            Sale.objects.select_related('customer', 'user')
            .prefetch_related(
                Prefetch('items', queryset=SaleItem.objects.select_related('product'))
            )
            .order_by('pk')
        )

        if sale_id:
            queryset = queryset.filter(pk=sale_id)
        elif not force:
            queryset = queryset.filter(
                Q(invoice__isnull=True)
                | Q(invoice__pdf__isnull=True)
                | Q(invoice__pdf='')
            )

        return list(queryset)

    def _build_pdf(self, buffer: BytesIO, sale: Sale, invoice: Invoice) -> None:
        document = canvas.Canvas(buffer, pagesize=A4)

        width, height = A4
        margin = 40
        y_position = height - margin

        document.setFont('Helvetica-Bold', 16)
        document.drawString(margin, y_position, 'Facture - Pharmacy POS')

        document.setFont('Helvetica', 10)
        y_position -= 25
        document.drawString(margin, y_position, f'Numéro de facture : {invoice.invoice_number}')
        y_position -= 15
        document.drawString(margin, y_position, f'ID Vente : {sale.pk}')
        y_position -= 15
        document.drawString(margin, y_position, f'Date : {sale.sale_date.strftime("%d/%m/%Y %H:%M")}')
        y_position -= 15
        document.drawString(margin, y_position, f'Client : {sale.customer or "Client de passage"}')

        y_position -= 25
        document.setFont('Helvetica-Bold', 12)
        document.drawString(margin, y_position, 'Articles')
        y_position -= 20

        document.setFont('Helvetica', 10)
        document.drawString(margin, y_position, 'Produit')
        document.drawString(margin + 220, y_position, 'Qté')
        document.drawString(margin + 260, y_position, 'Prix unitaire')
        document.drawString(margin + 350, y_position, 'Total')
        y_position -= 15
        document.line(margin, y_position, width - margin, y_position)
        y_position -= 10

        for item in sale.items.all():
            if y_position < margin + 100:
                document.showPage()
                y_position = height - margin
            document.drawString(margin, y_position, item.product.name)
            document.drawString(margin + 220, y_position, str(item.quantity))
            document.drawString(margin + 260, y_position, f'{item.unit_price:.2f}')
            document.drawString(margin + 350, y_position, f'{item.line_total:.2f}')
            y_position -= 15

        y_position -= 10
        document.line(margin, y_position, width - margin, y_position)
        y_position -= 20

        document.setFont('Helvetica-Bold', 11)
        document.drawString(margin + 260, y_position, 'Sous-total :')
        document.drawString(margin + 350, y_position, f'{sale.subtotal:.2f}')
        y_position -= 15

        document.drawString(margin + 260, y_position, 'Taxe :')
        document.drawString(margin + 350, y_position, f'{sale.tax_amount:.2f}')
        y_position -= 15

        document.drawString(margin + 260, y_position, 'Total :')
        document.drawString(margin + 350, y_position, f'{sale.total_amount:.2f}')
        y_position -= 25

        document.setFont('Helvetica', 10)
        document.drawString(margin, y_position, f'Montant payé : {sale.amount_paid:.2f}')
        y_position -= 15
        document.drawString(margin, y_position, f'Reste à payer : {sale.balance_due:.2f}')

        document.showPage()
        document.save()


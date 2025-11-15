"""
API Views pour le formulaire de vente dynamique.
"""

import json
from decimal import Decimal
from datetime import date

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q, Sum
from django.contrib.auth import get_user_model

from catalog.models import Product, Lot
from .models import Customer, Sale, SaleItem, Payment
from .views import generate_invoice_for_sale

User = get_user_model()


@csrf_exempt
@require_http_methods(["GET"])
def product_search(request):
    """
    Recherche de produits par nom ou code-barres.
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(barcode__icontains=query)
    ).select_related('category', 'dosage_form', 'supplier')[:20]
    
    results = []
    today = date.today()
    
    for product in products:
        # Calculer le stock disponible
        from catalog.models import Lot
        available_lots = Lot.objects.filter(
            product=product,
            is_active=True,
            expiration_date__gt=today,
            remaining_quantity__gt=0,
        ).aggregate(total=Sum('remaining_quantity'))['total'] or 0
        
        results.append({
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode or '',
            'sale_price': str(product.sale_price),
            'stock_available': available_lots,
        })
    
    return JsonResponse({'products': results})


@csrf_exempt
@require_http_methods(["GET"])
def product_stock_info(request, product_id):
    """
    Récupère les informations de stock détaillées d'un produit.
    """
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé'}, status=404)
    
    today = date.today()
    
    # Lots disponibles (non expirés)
    available_lots = Lot.objects.filter(
        product=product,
        is_active=True,
        expiration_date__gt=today,
        remaining_quantity__gt=0,
    ).order_by('expiration_date', 'created_at')
    
    lots_info = []
    total_available = 0
    
    for lot in available_lots:
        lots_info.append({
            'lot_id': lot.id,
            'batch_number': lot.batch_number or '',
            'expiration_date': lot.expiration_date.isoformat(),
            'remaining_quantity': lot.remaining_quantity,
            'sale_price': str(lot.sale_price),
        })
        total_available += lot.remaining_quantity
    
    # Stock expiré
    expired_lots = Lot.objects.filter(
        product=product,
        is_active=True,
        expiration_date__lte=today,
        remaining_quantity__gt=0,
    ).aggregate(total=Sum('remaining_quantity'))['total'] or 0
    
    # Prix de vente (basé sur le dernier lot)
    sale_price = product.sale_price
    
    return JsonResponse({
        'product_id': product.id,
        'product_name': product.name,
        'sale_price': str(sale_price),
        'total_available': total_available,
        'expired_stock': expired_lots,
        'stock_threshold': product.stock_threshold,
        'is_below_threshold': total_available <= product.stock_threshold,
        'available_lots': lots_info,
    })


@csrf_exempt
@require_http_methods(["POST"])
def validate_sale_item(request):
    """
    Valide un item de vente et retourne le prix moyen pondéré.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    
    if not product_id:
        return JsonResponse({'error': 'Données invalides'}, status=400)
    
    if quantity <= 0:
        return JsonResponse({'error': 'La quantité doit être positive'}, status=400)
    
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé'}, status=404)
    
    today = date.today()
    
    # Récupérer les lots disponibles (FEFO)
    available_lots = Lot.objects.filter(
        product=product,
        is_active=True,
        expiration_date__gt=today,
        remaining_quantity__gt=0,
    ).order_by('expiration_date', 'created_at')
    
    # Calculer combien on peut prendre de chaque lot
    lots_to_use = []
    remaining_quantity = quantity
    
    for lot in available_lots:
        if remaining_quantity <= 0:
            break
        
        quantity_from_lot = min(lot.remaining_quantity, remaining_quantity)
        lots_to_use.append({
            'lot': lot,
            'quantity': quantity_from_lot,
        })
        remaining_quantity -= quantity_from_lot
    
    if remaining_quantity > 0:
        total_available = quantity - remaining_quantity
        return JsonResponse({
            'valid': False,
            'error': f'Stock insuffisant. Disponible: {total_available}, Demandé: {quantity}',
            'available': total_available,
            'requested': quantity,
        })
    
    # Calculer le prix moyen pondéré
    # Documentation: docs/AVERAGE_PRICE.md
    # Quand plusieurs lots avec des prix différents sont utilisés pour une vente,
    # on calcule un prix moyen pondéré pour afficher un prix unitaire unique.
    total_price = Decimal('0.00')
    for lot_info in lots_to_use:
        lot = lot_info['lot']
        qty = lot_info['quantity']
        total_price += lot.sale_price * Decimal(str(qty))
    
    average_price = total_price / Decimal(str(quantity))
    total_price = average_price * Decimal(str(quantity))
    
    return JsonResponse({
        'valid': True,
        'product_id': product.id,
        'product_name': product.name,
        'quantity': quantity,
        'lots': lots_to_use,
        'average_price': str(average_price),
        'total_price': str(total_price),
    })


@csrf_exempt
@require_http_methods(["GET"])
def customer_list(request):
    """
    Liste des clients pour le select.
    Exclut les clients anonymes par défaut.
    """
    # Exclure les clients anonymes de la liste déroulante
    # Utiliser .only() pour ne charger que les champs nécessaires
    customers = Customer.objects.filter(
        is_anonymous=False
    ).only(
        'id', 'name', 'phone', 'email', 'credit_balance'
    ).order_by('name')[:100]
    
    results = []
    for customer in customers:
        results.append({
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone or '',
            'email': customer.email or '',
            'credit_balance': str(customer.credit_balance),
        })
    
    return JsonResponse({'customers': results})


@csrf_exempt
@require_http_methods(["GET"])
def customer_credit_info(request, customer_id):
    """
    Récupère les informations de crédit d'un client.
    """
    try:
        customer = Customer.objects.only('credit_balance').get(pk=customer_id)
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Client non trouvé'}, status=404)
    
    return JsonResponse({
        'customer_id': customer.id,
        'credit_balance': str(customer.credit_balance),
    })


@csrf_exempt
@require_http_methods(["GET"])
def sale_detail(request, sale_id):
    """
    Récupère les détails d'une vente existante pour l'édition.
    """
    try:
        sale = Sale.objects.select_related('customer', 'user').prefetch_related(
            'items__product',
            'payments',
            'invoices'
        ).get(pk=sale_id)
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Vente non trouvée'}, status=404)
    
    # Récupérer les items
    items = []
    for item in sale.items.all():
        items.append({
            'product_id': item.product.id,
            'product_name': item.product.name,
            'product_barcode': item.product.barcode,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'line_total': str(item.line_total),
        })
    
    # Récupérer les paiements
    payments = []
    for payment in sale.payments.all():
        payments.append({
            'id': payment.id, # ID pour la mise à jour
            'amount': payment.amount,
            'payment_method': payment.payment_method,
        })
    
    # Vérifier si le client est anonyme
    customer_is_anonymous = False
    anonymous_customer_info = None
    if sale.customer:
        customer_is_anonymous = sale.customer.is_anonymous
        if customer_is_anonymous:
            anonymous_customer_info = {
                'name': sale.customer.name,
                'phone': sale.customer.phone or '',
                'email': sale.customer.email or '',
            }
    
    # Récupérer les factures
    invoices = []
    for invoice in sale.invoices.all().order_by('-invoice_date'):
        invoices.append({
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            'has_pdf': bool(invoice.pdf),
        })
    
    return JsonResponse({
        'sale_id': sale.id,
        'reference': sale.reference,
        'customer_id': sale.customer_id,
        'customer_is_anonymous': customer_is_anonymous,
        'anonymous_customer': anonymous_customer_info,
        'sale_date': sale.sale_date.isoformat() if sale.sale_date else None,
        'notes': sale.notes or '',
        'tax_amount': str(sale.tax_amount),
        'discount_type': sale.discount_type,
        'discount_value': str(sale.discount_value),
        'subtotal': str(sale.subtotal),
        'total_amount': str(sale.total_amount),
        'amount_paid': str(sale.amount_paid),
        'balance_due': str(sale.balance_due),
        'status': sale.status,
        'items': items,
        'payments': payments,
        'invoices': invoices,
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_sale(request):
    """
    Crée une vente complète en une seule transaction.
    
    Payload attendu:
    {
        "customer_id": 1,
        "sale_date": "2024-01-01T10:00:00Z",
        "tax_amount": "0.00",
        "discount_type": "amount",
        "discount_value": "0.00",
        "notes": "",
        "items": [
            {"product_id": 1, "quantity": 2}
        ],
        "payments": [
            {"amount": "100.00", "payment_method": "cash"}
        ],
        "anonymous_customer": {
            "name": "John Doe",
            "phone": "123456789",
            "email": "john@example.com"
        }
    }
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Non authentifié'}, status=401)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    
    errors = {}
    
    # Validation des données de base
    customer_id = data.get('customer_id')
    anonymous_customer_data = data.get('anonymous_customer')
    
    # Gérer le client anonyme ou le client existant
    customer = None
    if anonymous_customer_data:
        # Créer ou réutiliser un client anonyme
        name = anonymous_customer_data.get('name', '').strip()
        phone = (anonymous_customer_data.get('phone') or '').strip() or ''
        email = (anonymous_customer_data.get('email') or '').strip() or ''
        
        if not name:
            errors['anonymous_customer'] = {'name': 'Le nom est requis pour un client anonyme'}
        else:
            # Chercher un client anonyme existant avec le même nom et téléphone
            existing_customer = Customer.objects.filter(
                is_anonymous=True,
                name=name,
                phone=phone,
            ).first()
            
            if existing_customer:
                customer = existing_customer
            else:
                customer = Customer.objects.create(
                    name=name,
                    phone=phone,
                    email=email,
                    is_anonymous=True,
                )
    elif customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors['customer_id'] = 'Client non trouvé'
    else:
        errors['customer'] = 'Un client est requis'
    
    tax_amount = Decimal(str(data.get('tax_amount', '0.00')))
    discount_type = data.get('discount_type', 'amount')
    discount_value = Decimal(str(data.get('discount_value', '0.00')))
    
    # Validation du type de remise
    if discount_type not in ['amount', 'percentage']:
        errors['discount_type'] = 'Type de remise invalide (amount ou percentage)'
    
    # Validation de la valeur de remise
    if discount_value < 0:
        errors['discount_value'] = 'La valeur de remise ne peut pas être négative'
    
    # Validation des items
    items_data = data.get('items', [])
    if not items_data:
        errors['items'] = 'Au moins un produit est requis'
    
    validated_items = []
    for item_data in items_data:
        product_id = item_data.get('product_id')
        quantity = item_data.get('quantity', 1)
        
        if not product_id:
            errors['items'] = 'product_id est requis pour chaque item'
            continue
        
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            errors['items'] = f'Produit {product_id} non trouvé'
            continue
        
        if quantity <= 0:
            errors['items'] = 'La quantité doit être positive'
            continue
        
        # Valider le stock disponible
        today = date.today()
        available_lots = Lot.objects.filter(
            product=product,
            is_active=True,
            expiration_date__gt=today,
            remaining_quantity__gt=0,
        ).order_by('expiration_date', 'created_at')
        
        total_available = sum(lot.remaining_quantity for lot in available_lots)
        if total_available < quantity:
            errors['items'] = f'Stock insuffisant pour {product.name}. Disponible: {total_available}, Demandé: {quantity}'
            continue
        
        # Calculer le prix moyen pondéré
        lots_to_use = []
        remaining_qty = quantity
        total_price = Decimal('0.00')
        
        for lot in available_lots:
            if remaining_qty <= 0:
                break
            qty_from_lot = min(lot.remaining_quantity, remaining_qty)
            lots_to_use.append({
                'lot': lot,
                'quantity': qty_from_lot,
            })
            total_price += lot.sale_price * Decimal(str(qty_from_lot))
            remaining_qty -= qty_from_lot
        
        average_price = total_price / Decimal(str(quantity))
        line_total = average_price * Decimal(str(quantity))
        
        validated_items.append({
            'product': product,
            'product_id': product_id,
            'quantity': quantity,
            'unit_price': average_price,
            'line_total': line_total,
            'lots': lots_to_use,
        })
    
    # Validation des paiements
    payments_data = data.get('payments', [])
    if not payments_data:
        errors['payments'] = 'Au moins un paiement est requis'
    
    validated_payments = []
    for payment_data in payments_data:
        amount = Decimal(str(payment_data.get('amount', '0.00')))
        payment_method = payment_data.get('payment_method', 'cash')
        
        if amount <= 0:
            errors['payments'] = 'Le montant du paiement doit être positif'
            continue
        
        if payment_method not in ['cash', 'card', 'mobile_money', 'bank_transfer', 'other']:
            errors['payments'] = 'Méthode de paiement invalide'
            continue
        
        validated_payments.append({
            'amount': amount,
            'payment_method': payment_method,
        })
    
    if errors:
        return JsonResponse({
            'success': False,
            'errors': errors,
        }, status=400)
    
    # Créer la vente dans une transaction
    try:
        with transaction.atomic():
            # Calculer le sous-total
            subtotal = sum(item['line_total'] for item in validated_items)
            
            # Calculer le montant réel de la remise selon le type
            if discount_type == 'percentage':
                # Validation : pourcentage ne doit pas dépasser 100%
                if discount_value > 100:
                    return JsonResponse({
                        'success': False,
                        'errors': {'discount_value': 'Le pourcentage ne peut pas dépasser 100%'},
                    }, status=400)
                discount_amount = subtotal * (discount_value / Decimal('100.00'))
            else:  # amount
                discount_amount = discount_value
                # Validation : montant ne doit pas dépasser le sous-total
                if discount_amount > subtotal:
                    return JsonResponse({
                        'success': False,
                        'errors': {'discount_value': 'La remise ne peut pas dépasser le sous-total'},
                    }, status=400)
            
            # Appliquer la remise
            subtotal_after_discount = subtotal - discount_amount
            if subtotal_after_discount < 0:
                return JsonResponse({
                    'success': False,
                    'errors': {'discount_value': 'La remise ne peut pas dépasser le sous-total'},
                }, status=400)
            
            # Calculer le total
            total_amount = subtotal_after_discount + tax_amount
            
            # Créer la vente
            sale = Sale.objects.create(
                customer=customer,
                user=request.user,
                sale_date=data.get('sale_date') or None,
                subtotal=subtotal_after_discount,
                tax_amount=tax_amount,
                discount_type=discount_type,
                discount_value=discount_value,
                total_amount=total_amount,
                notes=data.get('notes', ''),
                status=Sale.Status.PENDING,
            )
            
            # Créer les items et ajuster les stocks
            for item_data in validated_items:
                sale_item = SaleItem.objects.create(
                    sale=sale,
                    product=item_data['product'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    line_total=item_data['line_total'],
                )
                
                # Ajuster les stocks (FEFO)
                for lot_info in item_data['lots']:
                    lot = lot_info['lot']
                    qty = lot_info['quantity']
                    lot.adjust_quantity(quantity_delta=-qty)
                    
                    # Créer le mouvement de stock
                    from catalog.models import StockMovement
                    StockMovement.objects.create(
                        lot=lot,
                        movement_type=StockMovement.MovementType.OUT,
                        quantity=qty,
                        source=f'Sale #{sale.id}',
                        comment=f'Vente - Item #{sale_item.id}',
                    )
            
            # Créer les paiements
            total_paid = Decimal('0.00')
            for payment_data in validated_payments:
                Payment.objects.create(
                    sale=sale,
                    amount=payment_data['amount'],
                    payment_method=payment_data['payment_method'],
                )
                total_paid += payment_data['amount']
            
            # Mettre à jour les totaux de la vente
            sale.amount_paid = total_paid
            sale.balance_due = sale.total_amount - total_paid
            sale.status = sale.compute_status()
            sale.save(update_fields=['amount_paid', 'balance_due', 'status', 'updated_at'])
            
            # Mettre à jour le crédit client si nécessaire
            if customer:
                Sale.recalculate_customer_credit(customer.id)
            
            # Générer automatiquement la facture
            try:
                invoice = generate_invoice_for_sale(sale, save_pdf=True)
                invoice_id = invoice.id
                invoice_number = invoice.invoice_number
            except Exception as invoice_error:
                # Ne pas faire échouer la création de vente si la génération de facture échoue
                print(f'Erreur lors de la génération de la facture: {invoice_error}')
                invoice_id = None
                invoice_number = None
            
            return JsonResponse({
                'success': True,
                'sale_id': sale.id,
                'invoice_id': invoice_id,
                'invoice_number': invoice_number,
                'sale': {
                    'id': sale.id,
                    'subtotal': str(sale.subtotal),
                    'tax_amount': str(sale.tax_amount),
                    'discount_type': sale.discount_type,
                    'discount_value': str(sale.discount_value),
                    'total_amount': str(sale.total_amount),
                    'amount_paid': str(sale.amount_paid),
                    'balance_due': str(sale.balance_due),
                    'status': sale.status,
                },
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la création: {str(e)}',
        }, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def update_sale(request, sale_id):
    """
    Met à jour une vente existante.
    Même logique que create_sale mais pour la mise à jour.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Non authentifié'}, status=401)
    
    try:
        sale = Sale.objects.get(pk=sale_id)
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Vente non trouvée'}, status=404)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    
    errors = {}
    
    # Validation des données de base
    customer_id = data.get('customer_id')
    anonymous_customer_data = data.get('anonymous_customer')
    
    # Gérer le client anonyme ou le client existant (même logique que create_sale)
    customer = None
    if anonymous_customer_data:
        # Créer ou réutiliser un client anonyme
        name = anonymous_customer_data.get('name', '').strip()
        phone = (anonymous_customer_data.get('phone') or '').strip() or ''
        email = (anonymous_customer_data.get('email') or '').strip() or ''
        
        if not name:
            errors['anonymous_customer'] = {'name': 'Le nom est requis pour un client anonyme'}
        else:
            # Chercher un client anonyme existant avec le même nom et téléphone
            existing_customer = Customer.objects.filter(
                is_anonymous=True,
                name=name,
                phone=phone,
            ).first()
            
            if existing_customer:
                customer = existing_customer
            else:
                customer = Customer.objects.create(
                    name=name,
                    phone=phone,
                    email=email,
                    is_anonymous=True,
                )
    elif customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors['customer_id'] = 'Client non trouvé'
    else:
        errors['customer'] = 'Un client est requis'
    
    tax_amount = Decimal(str(data.get('tax_amount', '0.00')))
    discount_type = data.get('discount_type', 'amount')
    discount_value = Decimal(str(data.get('discount_value', '0.00')))
    
    # Validation du type de remise
    if discount_type not in ['amount', 'percentage']:
        errors['discount_type'] = 'Type de remise invalide (amount ou percentage)'
    
    # Validation de la valeur de remise
    if discount_value < 0:
        errors['discount_value'] = 'La valeur de remise ne peut pas être négative'
    
    # Validation des items
    items_data = data.get('items', [])
    if not items_data:
        errors['items'] = 'Au moins un produit est requis'
    
    validated_items = []
    for item_data in items_data:
        product_id = item_data.get('product_id')
        quantity = item_data.get('quantity', 1)
        
        if not product_id:
            errors['items'] = 'product_id est requis pour chaque item'
            continue
        
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            errors['items'] = f'Produit {product_id} non trouvé'
            continue
        
        if quantity <= 0:
            errors['items'] = 'La quantité doit être positive'
            continue
        
        # Valider le stock disponible (en tenant compte du stock déjà réservé par cette vente)
        today = date.today()
        available_lots = Lot.objects.filter(
            product=product,
            is_active=True,
            expiration_date__gt=today,
            remaining_quantity__gt=0,
        ).order_by('expiration_date', 'created_at')
        
        # Calculer le stock disponible en tenant compte des items existants de cette vente
        existing_item = sale.items.filter(product_id=product_id).first()
        existing_quantity = existing_item.quantity if existing_item else 0
        
        total_available = sum(lot.remaining_quantity for lot in available_lots) + existing_quantity
        if total_available < quantity:
            errors['items'] = f'Stock insuffisant pour {product.name}. Disponible: {total_available}, Demandé: {quantity}'
            continue
        
        # Calculer le prix moyen pondéré
        lots_to_use = []
        remaining_qty = quantity
        total_price = Decimal('0.00')
        
        # Si on augmente la quantité, on doit prendre en compte le stock déjà réservé
        if existing_item and quantity > existing_quantity:
            # Restaurer le stock des items existants d'abord
            for sale_item_lot in existing_item.lot_items.all():
                lot = sale_item_lot.lot
                lot.adjust_quantity(quantity_delta=sale_item_lot.quantity)
                remaining_qty -= sale_item_lot.quantity
        
        for lot in available_lots:
            if remaining_qty <= 0:
                break
            qty_from_lot = min(lot.remaining_quantity, remaining_qty)
            lots_to_use.append({
                'lot': lot,
                'quantity': qty_from_lot,
            })
            total_price += lot.sale_price * Decimal(str(qty_from_lot))
            remaining_qty -= qty_from_lot
        
        average_price = total_price / Decimal(str(quantity))
        line_total = average_price * Decimal(str(quantity))
        
        validated_items.append({
            'product': product,
            'product_id': product_id,
            'quantity': quantity,
            'unit_price': average_price,
            'line_total': line_total,
            'lots': lots_to_use,
        })
    
    # Validation des paiements
    payments_data = data.get('payments', [])
    if not payments_data:
        errors['payments'] = 'Au moins un paiement est requis'
    
    validated_payments = []
    for payment_data in payments_data:
        amount = Decimal(str(payment_data.get('amount', '0.00')))
        payment_method = payment_data.get('payment_method', 'cash')
        payment_id = payment_data.get('id')  # ID pour la mise à jour
        
        if amount <= 0:
            errors['payments'] = 'Le montant du paiement doit être positif'
            continue
        
        if payment_method not in ['cash', 'card', 'mobile_money', 'bank_transfer', 'other']:
            errors['payments'] = 'Méthode de paiement invalide'
            continue
        
        validated_payments.append({
            'id': payment_id,
            'amount': amount,
            'payment_method': payment_method,
        })
    
    if errors:
        return JsonResponse({
            'success': False,
            'errors': errors,
        }, status=400)
    
    # Mettre à jour la vente dans une transaction
    try:
        with transaction.atomic():
            # Restaurer les stocks des items existants
            for existing_item in sale.items.all():
                # Récupérer les SaleItemLot pour restaurer les stocks
                # Le related_name est 'lot_items', pas 'lots_used'
                for sale_item_lot in existing_item.lot_items.all():
                    lot = sale_item_lot.lot
                    lot.adjust_quantity(quantity_delta=sale_item_lot.quantity)
                    
                    # Créer le mouvement de stock
                    from catalog.models import StockMovement
                    StockMovement.objects.create(
                        lot=lot,
                        movement_type=StockMovement.MovementType.IN,
                        quantity=sale_item_lot.quantity,
                        source=f'Sale #{sale.id}',
                        comment=f'Annulation vente - Item #{existing_item.id}',
                    )
            
            # Supprimer les anciens items (les paiements seront mis à jour, pas supprimés)
            sale.items.all().delete()
            
            # Calculer le sous-total
            subtotal = sum(item['line_total'] for item in validated_items)
            
            # Calculer le montant réel de la remise selon le type
            if discount_type == 'percentage':
                # Validation : pourcentage ne doit pas dépasser 100%
                if discount_value > 100:
                    return JsonResponse({
                        'success': False,
                        'errors': {'discount_value': 'Le pourcentage ne peut pas dépasser 100%'},
                    }, status=400)
                discount_amount = subtotal * (discount_value / Decimal('100.00'))
            else:  # amount
                discount_amount = discount_value
                # Validation : montant ne doit pas dépasser le sous-total
                if discount_amount > subtotal:
                    return JsonResponse({
                        'success': False,
                        'errors': {'discount_value': 'La remise ne peut pas dépasser le sous-total'},
                    }, status=400)
            
            # Appliquer la remise
            subtotal_after_discount = subtotal - discount_amount
            if subtotal_after_discount < 0:
                return JsonResponse({
                    'success': False,
                    'errors': {'discount_value': 'La remise ne peut pas dépasser le sous-total'},
                }, status=400)
            
            # Calculer le total
            total_amount = subtotal_after_discount + tax_amount
            
            # Mettre à jour la vente
            sale.customer = customer
            sale.subtotal = subtotal_after_discount
            sale.tax_amount = tax_amount
            sale.discount_type = discount_type
            sale.discount_value = discount_value
            sale.total_amount = total_amount
            sale.notes = data.get('notes', '')
            if data.get('sale_date'):
                from django.utils.dateparse import parse_datetime
                sale.sale_date = parse_datetime(data.get('sale_date'))
            sale.save()
            
            # Créer les nouveaux items et ajuster les stocks
            for item_data in validated_items:
                sale_item = SaleItem.objects.create(
                    sale=sale,
                    product=item_data['product'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    line_total=item_data['line_total'],
                )
                
                # Ajuster les stocks (FEFO)
                for lot_info in item_data['lots']:
                    lot = lot_info['lot']
                    qty = lot_info['quantity']
                    lot.adjust_quantity(quantity_delta=-qty)
                    
                    # Créer le mouvement de stock
                    from catalog.models import StockMovement
                    StockMovement.objects.create(
                        lot=lot,
                        movement_type=StockMovement.MovementType.OUT,
                        quantity=qty,
                        source=f'Sale #{sale.id}',
                        comment=f'Vente - Item #{sale_item.id}',
                    )
            
            # Gérer les paiements en préservant l'horodatage
            # Récupérer tous les paiements existants indexés par ID
            existing_payments_dict = {p.id: p for p in sale.payments.all()}
            payment_ids_to_keep = set()
            total_paid = Decimal('0.00')
            
            # Mettre à jour ou créer les paiements
            for payment_data in validated_payments:
                amount = payment_data['amount']
                payment_method = payment_data['payment_method']
                payment_id = payment_data.get('id')
                
                if payment_id and payment_id in existing_payments_dict:
                    # Mettre à jour le paiement existant (préserve created_at et payment_date)
                    existing_payment = existing_payments_dict[payment_id]
                    existing_payment.amount = amount
                    existing_payment.payment_method = payment_method
                    # Ne pas modifier payment_date ni created_at
                    existing_payment.save(update_fields=['amount', 'payment_method', 'updated_at'])
                    payment_ids_to_keep.add(payment_id)
                    total_paid += amount
                else:
                    # Créer un nouveau paiement
                    new_payment = Payment.objects.create(
                        sale=sale,
                        amount=amount,
                        payment_method=payment_method,
                    )
                    payment_ids_to_keep.add(new_payment.id)
                    total_paid += amount
            
            # Supprimer les paiements qui ne sont plus dans la liste
            for payment_id, payment in existing_payments_dict.items():
                if payment_id not in payment_ids_to_keep:
                    payment.delete()
            
            # Mettre à jour les totaux de la vente
            sale.amount_paid = total_paid
            sale.balance_due = sale.total_amount - total_paid
            sale.status = sale.compute_status()
            sale.save(update_fields=['amount_paid', 'balance_due', 'status', 'updated_at'])
            
            # Mettre à jour le crédit client si nécessaire
            if customer:
                Sale.recalculate_customer_credit(customer.id)
            
            return JsonResponse({
                'success': True,
                'sale_id': sale.id,
                'sale': {
                    'id': sale.id,
                    'subtotal': str(sale.subtotal),
                    'tax_amount': str(sale.tax_amount),
                    'discount_type': sale.discount_type,
                    'discount_value': str(sale.discount_value),
                    'total_amount': str(sale.total_amount),
                    'amount_paid': str(sale.amount_paid),
                    'balance_due': str(sale.balance_due),
                    'status': sale.status,
                },
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la mise à jour: {str(e)}',
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_invoice(request, sale_id):
    """
    Génère une nouvelle facture pour une vente existante.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Non authentifié'}, status=401)
    
    try:
        sale = Sale.objects.get(pk=sale_id)
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Vente non trouvée'}, status=404)
    
    try:
        # Générer la facture
        invoice = generate_invoice_for_sale(sale, save_pdf=True)
        
        return JsonResponse({
            'success': True,
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'preview_url': f'/invoices/{invoice.id}/preview/',
            'pdf_url': f'/invoices/{invoice.id}/pdf/',
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la génération de la facture: {str(e)}',
        }, status=500)

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

User = get_user_model()


@csrf_exempt
@require_http_methods(["GET"])
def product_search(request):
    """
    Recherche de produits avec informations de stock.
    """
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(barcode__icontains=query)
    ).select_related('category', 'dosage_form', 'supplier')[:20]
    
    results = []
    today = date.today()
    
    for product in products:
        # Calculer le stock disponible
        available_lots = Lot.objects.filter(
            product=product,
            is_active=True,
            expiration_date__gt=today,
            remaining_quantity__gt=0,
        )
        total_stock = available_lots.aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        
        # Récupérer le prix de vente (dernier lot)
        last_lot = Lot.objects.filter(
            product=product,
            is_active=True,
        ).order_by('-created_at').first()
        
        sale_price = last_lot.sale_price if last_lot else Decimal('0.00')
        
        # Vérifier les alertes
        is_below_threshold = total_stock <= product.stock_threshold
        expired_stock = Lot.objects.filter(
            product=product,
            is_active=True,
            expiration_date__lte=today,
            remaining_quantity__gt=0,
        ).aggregate(total=Sum('remaining_quantity'))['total'] or 0
        
        results.append({
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode,
            'category': product.category.name,
            'dosage_form': product.dosage_form.name,
            'sale_price': str(sale_price),
            'stock_available': total_stock,
            'stock_threshold': product.stock_threshold,
            'is_below_threshold': is_below_threshold,
            'has_expired_stock': expired_stock > 0,
            'expired_stock': expired_stock,
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
        total_available += lot.remaining_quantity
        lots_info.append({
            'id': lot.id,
            'batch_number': lot.batch_number or f'Lot #{lot.id}',
            'expiration_date': lot.expiration_date.isoformat(),
            'remaining_quantity': lot.remaining_quantity,
            'sale_price': str(lot.sale_price),
        })
    
    # Lots expirés
    expired_lots = Lot.objects.filter(
        product=product,
        is_active=True,
        expiration_date__lte=today,
        remaining_quantity__gt=0,
    )
    expired_stock = expired_lots.aggregate(
        total=Sum('remaining_quantity')
    )['total'] or 0
    
    # Prix de vente (dernier lot)
    last_lot = Lot.objects.filter(
        product=product,
        is_active=True,
    ).order_by('-created_at').first()
    
    sale_price = last_lot.sale_price if last_lot else Decimal('0.00')
    
    return JsonResponse({
        'product_id': product.id,
        'product_name': product.name,
        'sale_price': str(sale_price),
        'total_available': total_available,
        'expired_stock': expired_stock,
        'stock_threshold': product.stock_threshold,
        'is_below_threshold': total_available <= product.stock_threshold,
        'available_lots': lots_info,
    })


@csrf_exempt
@require_http_methods(["POST"])
def validate_sale_item(request):
    """
    Valide si une quantité peut être vendue pour un produit.
    Retourne les lots qui seront utilisés (FEFO).
    """
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 0))
    except (json.JSONDecodeError, ValueError, KeyError):
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
    
    lots_to_use = []
    remaining_quantity = quantity
    total_available = 0
    
    for lot in available_lots:
        total_available += lot.remaining_quantity
        if remaining_quantity <= 0:
            break
        
        quantity_from_lot = min(lot.remaining_quantity, remaining_quantity)
        lots_to_use.append({
            'lot_id': lot.id,
            'batch_number': lot.batch_number or f'Lot #{lot.id}',
            'expiration_date': lot.expiration_date.isoformat(),
            'quantity': quantity_from_lot,
            'sale_price': str(lot.sale_price),
            'remaining_in_lot': lot.remaining_quantity,
        })
        remaining_quantity -= quantity_from_lot
    
    if remaining_quantity > 0:
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
    # Exemple: 10 unités à 1000 FCFA + 2 unités à 1200 FCFA = 1033.33 FCFA/unité
    total_price = Decimal('0.00')
    for lot_info in lots_to_use:
        total_price += Decimal(lot_info['sale_price']) * lot_info['quantity']
    
    average_price = total_price / quantity if quantity > 0 else Decimal('0.00')
    
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
def sale_detail(request, sale_id):
    """
    Récupère les détails d'une vente existante pour l'édition.
    """
    try:
        sale = Sale.objects.select_related('customer', 'user').prefetch_related(
            'items__product',
            'payments'
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
            'amount': str(payment.amount),
            'payment_method': payment.payment_method,
        })
    
    return JsonResponse({
        'sale_id': sale.id,
        'customer_id': sale.customer_id,
        'sale_date': sale.sale_date.isoformat() if sale.sale_date else None,
        'notes': sale.notes or '',
        'tax_amount': str(sale.tax_amount),
        'discount_amount': str(sale.discount_amount),
        'subtotal': str(sale.subtotal),
        'total_amount': str(sale.total_amount),
        'amount_paid': str(sale.amount_paid),
        'balance_due': str(sale.balance_due),
        'status': sale.status,
        'items': items,
        'payments': payments,
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
        "discount_amount": "0.00",
        "notes": "",
        "items": [
            {
                "product_id": 1,
                "quantity": 2
            }
        ],
        "payments": [
            {
                "amount": "100.00",
                "payment_method": "cash"
            }
        ]
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
    if customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors['customer_id'] = 'Client non trouvé'
    else:
        customer = None
    
    tax_amount = Decimal(str(data.get('tax_amount', '0.00')))
    discount_amount = Decimal(str(data.get('discount_amount', '0.00')))
    
    if discount_amount < 0:
        errors['discount_amount'] = 'La remise ne peut pas être négative'
    
    # Validation des items
    items_data = data.get('items', [])
    if not items_data:
        errors['items'] = 'Au moins un produit est requis'
    
    validated_items = []
    for idx, item_data in enumerate(items_data):
        item_errors = {}
        product_id = item_data.get('product_id')
        quantity = item_data.get('quantity', 0)
        
        if not product_id:
            item_errors['product_id'] = 'Produit requis'
        else:
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                item_errors['product_id'] = 'Produit non trouvé'
                product = None
        if quantity <= 0:
            item_errors['quantity'] = 'La quantité doit être positive'
        
        if item_errors:
            errors[f'items.{idx}'] = item_errors
        elif product:
            # Valider le stock
            today = date.today()
            available_lots = Lot.objects.filter(
                product=product,
                is_active=True,
                expiration_date__gt=today,
                remaining_quantity__gt=0,
            ).order_by('expiration_date', 'created_at')
            
            total_available = available_lots.aggregate(
                total=Sum('remaining_quantity')
            )['total'] or 0
            
            if quantity > total_available:
                item_errors['quantity'] = f'Stock insuffisant. Disponible: {total_available}'
                errors[f'items.{idx}'] = item_errors
            else:
                # Calculer le prix moyen pondéré (FEFO)
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
                    total_price += lot.sale_price * qty_from_lot
                    remaining_qty -= qty_from_lot
                
                average_price = total_price / quantity if quantity > 0 else Decimal('0.00')
                
                validated_items.append({
                    'product': product,
                    'quantity': quantity,
                    'unit_price': average_price,
                    'line_total': total_price,
                    'lots': lots_to_use,
                })
    
    # Validation des paiements
    payments_data = data.get('payments', [])
    validated_payments = []
    for idx, payment_data in enumerate(payments_data):
        payment_errors = {}
        amount = payment_data.get('amount')
        payment_method = payment_data.get('payment_method', 'cash')
        
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                payment_errors['amount'] = 'Le montant doit être positif'
        except (ValueError, TypeError):
            payment_errors['amount'] = 'Montant invalide'
        
        if payment_method not in [choice[0] for choice in Payment.PaymentMethod.choices]:
            payment_errors['payment_method'] = 'Mode de paiement invalide'
        
        if payment_errors:
            errors[f'payments.{idx}'] = payment_errors
        else:
            validated_payments.append({
                'amount': amount,
                'payment_method': payment_method,
            })
    
    # Si erreurs, retourner
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
            
            # Appliquer la remise
            subtotal_after_discount = subtotal - discount_amount
            if subtotal_after_discount < 0:
                return JsonResponse({
                    'success': False,
                    'errors': {'discount_amount': 'La remise ne peut pas dépasser le sous-total'},
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
                discount_amount=discount_amount,
                total_amount=total_amount,
                notes=data.get('notes', ''),
                status=Sale.Status.DRAFT,
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
                    lot.adjust_stock(
                        quantity_delta=-qty,
                        movement_type='out',
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
            
            return JsonResponse({
                'success': True,
                'sale_id': sale.id,
                'sale': {
                    'id': sale.id,
                    'subtotal': str(sale.subtotal),
                    'tax_amount': str(sale.tax_amount),
                    'discount_amount': str(discount_amount),
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
    if customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors['customer_id'] = 'Client non trouvé'
    else:
        customer = None
    
    tax_amount = Decimal(str(data.get('tax_amount', '0.00')))
    discount_amount = Decimal(str(data.get('discount_amount', '0.00')))
    
    if discount_amount < 0:
        errors['discount_amount'] = 'La remise ne peut pas être négative'
    
    # Validation des items
    items_data = data.get('items', [])
    if not items_data:
        errors['items'] = 'Au moins un produit est requis'
    
    validated_items = []
    for idx, item_data in enumerate(items_data):
        item_errors = {}
        product_id = item_data.get('product_id')
        quantity = item_data.get('quantity', 0)
        
        if not product_id:
            item_errors['product_id'] = 'Produit requis'
        else:
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                item_errors['product_id'] = 'Produit non trouvé'
                product = None
        if quantity <= 0:
            item_errors['quantity'] = 'La quantité doit être positive'
        
        if item_errors:
            errors[f'items.{idx}'] = item_errors
        elif product:
            # Valider le stock (en tenant compte des quantités déjà vendues)
            today = date.today()
            available_lots = Lot.objects.filter(
                product=product,
                is_active=True,
                expiration_date__gt=today,
                remaining_quantity__gt=0,
            ).order_by('expiration_date', 'created_at')
            
            # Calculer le stock disponible + ce qui a déjà été vendu dans cette vente
            total_available = available_lots.aggregate(
                total=Sum('remaining_quantity')
            )['total'] or 0
            
            # Récupérer la quantité déjà vendue pour ce produit dans cette vente
            existing_item = sale.items.filter(product=product).first()
            already_sold = existing_item.quantity if existing_item else 0
            
            # Stock disponible = stock actuel + ce qui a déjà été vendu (qu'on peut remettre en stock)
            total_available_with_return = total_available + already_sold
            
            if quantity > total_available_with_return:
                item_errors['quantity'] = f'Stock insuffisant. Disponible: {total_available_with_return}'
                errors[f'items.{idx}'] = item_errors
            else:
                # Calculer le prix moyen pondéré (FEFO)
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
                    total_price += lot.sale_price * qty_from_lot
                    remaining_qty -= qty_from_lot
                
                average_price = total_price / quantity if quantity > 0 else Decimal('0.00')
                
                validated_items.append({
                    'product': product,
                    'quantity': quantity,
                    'unit_price': average_price,
                    'line_total': total_price,
                    'lots': lots_to_use,
                    'existing_item': existing_item,
                })
    
    # Validation des paiements
    payments_data = data.get('payments', [])
    validated_payments = []
    for idx, payment_data in enumerate(payments_data):
        payment_errors = {}
        amount = payment_data.get('amount')
        payment_method = payment_data.get('payment_method', 'cash')
        
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                payment_errors['amount'] = 'Le montant doit être positif'
        except (ValueError, TypeError):
            payment_errors['amount'] = 'Montant invalide'
        
        if payment_method not in [choice[0] for choice in Payment.PaymentMethod.choices]:
            payment_errors['payment_method'] = 'Mode de paiement invalide'
        
        if payment_errors:
            errors[f'payments.{idx}'] = payment_errors
        else:
            validated_payments.append({
                'amount': amount,
                'payment_method': payment_method,
            })
    
    # Si erreurs, retourner
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
                for sale_item_lot in existing_item.lots_used.all():
                    lot = sale_item_lot.lot
                    lot.adjust_stock(
                        quantity_delta=sale_item_lot.quantity,
                        movement_type='in',
                        source=f'Sale #{sale.id}',
                        comment=f'Annulation vente - Item #{existing_item.id}',
                    )
            
            # Supprimer les anciens items et paiements
            sale.items.all().delete()
            sale.payments.all().delete()
            
            # Calculer le sous-total
            subtotal = sum(item['line_total'] for item in validated_items)
            
            # Appliquer la remise
            subtotal_after_discount = subtotal - discount_amount
            if subtotal_after_discount < 0:
                return JsonResponse({
                    'success': False,
                    'errors': {'discount_amount': 'La remise ne peut pas dépasser le sous-total'},
                }, status=400)
            
            # Calculer le total
            total_amount = subtotal_after_discount + tax_amount
            
            # Mettre à jour la vente
            sale.customer = customer
            sale.subtotal = subtotal_after_discount
            sale.tax_amount = tax_amount
            sale.discount_amount = discount_amount
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
                    lot.adjust_stock(
                        quantity_delta=-qty,
                        movement_type='out',
                        source=f'Sale #{sale.id}',
                        comment=f'Vente - Item #{sale_item.id}',
                    )
            
            # Créer les nouveaux paiements
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
            
            return JsonResponse({
                'success': True,
                'sale_id': sale.id,
                'sale': {
                    'id': sale.id,
                    'subtotal': str(sale.subtotal),
                    'tax_amount': str(sale.tax_amount),
                    'discount_amount': str(discount_amount),
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
@require_http_methods(["GET"])
def customer_list(request):
    """
    Liste des clients pour le select.
    """
    customers = Customer.objects.all().order_by('name')[:100]
    
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
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Client non trouvé'}, status=404)
    
    return JsonResponse({
        'customer_id': customer.id,
        'customer_name': customer.name,
        'credit_balance': str(customer.credit_balance),
    })

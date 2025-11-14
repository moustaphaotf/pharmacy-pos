# Prix Moyen Pondéré (Average Price) - Documentation

## Vue d'ensemble

Dans un système de gestion de stock basé sur les lots (FEFO - First Expired, First Out), un même produit peut avoir plusieurs lots avec des **prix de vente différents**. Le concept de **prix moyen pondéré** permet de calculer un prix unitaire unique pour une vente qui utilise des quantités provenant de plusieurs lots.

## Le problème

### Scénario réel

Imaginez un produit "Paracétamol 500mg" qui a été acheté à deux moments différents :

- **Lot A** : 10 unités à **1000 FCFA** l'unité (expire le 01/01/2025)
- **Lot B** : 5 unités à **1200 FCFA** l'unité (expire le 15/01/2025)

### Situation de vente

Un client veut acheter **12 unités** de ce produit.

Selon la logique **FEFO** (First Expired, First Out), le système doit :
1. Prendre d'abord les produits qui expirent en premier
2. Utiliser le Lot A en premier (expire le 01/01/2025)
3. Compléter avec le Lot B si nécessaire

**Répartition :**
- 10 unités du Lot A à 1000 FCFA = 10 000 FCFA
- 2 unités du Lot B à 1200 FCFA = 2 400 FCFA
- **Total : 12 400 FCFA**

### Question

Quel prix unitaire afficher sur la facture pour cette ligne de vente ?

## La solution : Prix Moyen Pondéré

Le **prix moyen pondéré** calcule un prix unitaire unique en fonction des quantités et prix de chaque lot utilisé.

### Formule

```
Prix moyen pondéré = (Somme des (prix_lot × quantité_lot)) / quantité_totale
```

### Calcul pour notre exemple

```
Total = (10 × 1000) + (2 × 1200)
Total = 10 000 + 2 400
Total = 12 400 FCFA

Prix moyen = 12 400 / 12
Prix moyen = 1 033.33 FCFA
```

**Résultat :** La ligne de vente affichera :
- Quantité : 12 unités
- Prix unitaire : **1 033.33 FCFA**
- Total ligne : **12 400 FCFA**

## Implémentation dans le code

### Endpoint : `validate_sale_item`

**Fichier :** `sales/api_views.py` (lignes 151-226)

Cet endpoint valide si une quantité peut être vendue et calcule le prix moyen pondéré.

#### Étape 1 : Sélection des lots (FEFO)

```python
# Récupérer les lots disponibles triés par date d'expiration
available_lots = Lot.objects.filter(
    product=product,
    is_active=True,
    expiration_date__gt=today,
    remaining_quantity__gt=0,
).order_by('expiration_date', 'created_at')

# Sélectionner les lots nécessaires
lots_to_use = []
remaining_quantity = quantity

for lot in available_lots:
    if remaining_quantity <= 0:
        break
    
    quantity_from_lot = min(lot.remaining_quantity, remaining_quantity)
    lots_to_use.append({
        'lot_id': lot.id,
        'quantity': quantity_from_lot,
        'sale_price': str(lot.sale_price),
        # ...
    })
    remaining_quantity -= quantity_from_lot
```

#### Étape 2 : Calcul du prix moyen pondéré

```python
# Calculer le prix moyen pondéré
total_price = Decimal('0.00')
for lot_info in lots_to_use:
    total_price += Decimal(lot_info['sale_price']) * lot_info['quantity']

average_price = total_price / quantity if quantity > 0 else Decimal('0.00')
```

#### Étape 3 : Retour de la réponse

```python
return JsonResponse({
    'valid': True,
    'product_id': product.id,
    'quantity': quantity,
    'lots': lots_to_use,  # Détails des lots utilisés
    'average_price': str(average_price),  # Prix moyen pondéré
    'total_price': str(total_price),  # Prix total
})
```

### Utilisation dans le frontend

**Fichier :** `static/admin/js/sale_form_react.jsx`

Lorsqu'un produit est ajouté ou que sa quantité est modifiée :

```javascript
const response = await fetch(getApiUrl('validate-item/'), {
    method: 'POST',
    body: JSON.stringify({
        product_id: product.id,
        quantity: 1,
    }),
});
const data = await response.json();

// Utiliser le prix moyen retourné
const newItem = {
    productId: product.id,
    quantity: 1,
    unitPrice: parseFloat(data.average_price),  // Prix moyen pondéré
    lineTotal: parseFloat(data.total_price),
    lots: data.lots,  // Informations sur les lots utilisés
};
```

## Exemples concrets

### Exemple 1 : Vente simple (un seul lot)

**Situation :**
- Lot A : 20 unités à 1000 FCFA
- Vente : 5 unités

**Calcul :**
```
Prix moyen = (5 × 1000) / 5 = 1000 FCFA
```

**Résultat :** Prix unitaire = 1000 FCFA (identique au prix du lot)

### Exemple 2 : Vente avec deux lots

**Situation :**
- Lot A : 10 unités à 1000 FCFA (expire le 01/01/2025)
- Lot B : 8 unités à 1200 FCFA (expire le 15/01/2025)
- Vente : 15 unités

**Répartition FEFO :**
- 10 unités du Lot A à 1000 FCFA = 10 000 FCFA
- 5 unités du Lot B à 1200 FCFA = 6 000 FCFA

**Calcul :**
```
Total = 10 000 + 6 000 = 16 000 FCFA
Prix moyen = 16 000 / 15 = 1 066.67 FCFA
```

**Résultat :** Prix unitaire = 1 066.67 FCFA

### Exemple 3 : Vente avec trois lots

**Situation :**
- Lot A : 5 unités à 1000 FCFA (expire le 01/01/2025)
- Lot B : 3 unités à 1200 FCFA (expire le 10/01/2025)
- Lot C : 4 unités à 1100 FCFA (expire le 20/01/2025)
- Vente : 8 unités

**Répartition FEFO :**
- 5 unités du Lot A à 1000 FCFA = 5 000 FCFA
- 3 unités du Lot B à 1200 FCFA = 3 600 FCFA

**Calcul :**
```
Total = 5 000 + 3 600 = 8 600 FCFA
Prix moyen = 8 600 / 8 = 1 075 FCFA
```

**Résultat :** Prix unitaire = 1 075 FCFA

## Avantages

1. **Simplicité pour l'utilisateur** : Un seul prix unitaire affiché, même si plusieurs lots sont utilisés
2. **Traçabilité** : Les détails des lots utilisés sont conservés dans `SaleItemLot`
3. **Cohérence** : Le prix total de la ligne correspond toujours à la somme réelle des prix des lots
4. **Flexibilité** : Permet de gérer des variations de prix entre les lots sans complexifier l'interface

## Traçabilité

Même si un prix moyen est affiché, le système conserve la trace exacte de quels lots ont été utilisés via le modèle `SaleItemLot` :

```python
class SaleItemLot(models.Model):
    sale_item = models.ForeignKey(SaleItem, ...)
    lot = models.ForeignKey(Lot, ...)
    quantity = models.PositiveIntegerField()  # Quantité prise de ce lot
    unit_price = models.DecimalField(...)  # Prix unitaire de ce lot spécifique
```

Cela permet de :
- Retracer exactement quels lots ont été vendus
- Connaître le prix réel de chaque lot utilisé
- Effectuer des analyses de rentabilité par lot

## Notes importantes

1. **Le prix moyen est calculé à la validation** : Il est recalculé à chaque fois que la quantité change
2. **Les lots sont sélectionnés selon FEFO** : Toujours les lots qui expirent en premier
3. **Le prix total est toujours exact** : La somme des (prix_lot × quantité_lot) est toujours correcte
4. **Le prix moyen est arrondi** : Utilise la précision décimale configurée (2 décimales par défaut)

## Références dans le code

- **Calcul du prix moyen** : `sales/api_views.py`, fonction `validate_sale_item()` (lignes 211-216)
- **Utilisation dans les ventes** : `sales/api_views.py`, fonctions `create_sale()` et `update_sale()` (lignes 391-396, 631-636)
- **Affichage frontend** : `static/admin/js/sale_form_react.jsx` (lignes 190, 242)
- **Modèle de traçabilité** : `sales/models/sale_item.py`, classe `SaleItemLot`


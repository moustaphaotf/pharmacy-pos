/**
 * Application React pour le formulaire de vente
 * Utilise React via CDN et Babel Standalone pour le JSX
 */

(function() {
  'use strict';

  // Configuration globale
  let apiBaseUrl = window.SALE_FORM_CONFIG?.apiBaseUrl || '/api/sales/';
  // S'assurer que l'URL se termine par /
  if (!apiBaseUrl.endsWith('/')) {
    apiBaseUrl += '/';
  }
  // Utiliser une fonction pour construire les URLs correctement
  const getApiUrl = (endpoint) => {
    // Enlever le / au début de l'endpoint s'il existe
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    return apiBaseUrl + cleanEndpoint;
  };
  const CSRF_TOKEN = window.SALE_FORM_CONFIG?.csrfToken || '';
  
  // Durée d'affichage des notifications (en millisecondes)
  const NOTIFICATION_DURATION = 5000;
  
  console.log('🔧 API Base URL configuré:', apiBaseUrl);
  console.log('🔧 Test URL customers:', getApiUrl('customers/'));
  console.log('🔧 Test URL products:', getApiUrl('products/search/'));

  /**
   * Composant principal du formulaire de vente
   */
  function SaleForm() {
    const [customerId, setCustomerId] = React.useState(null);
    const [customers, setCustomers] = React.useState([]);
    const [isAnonymousCustomer, setIsAnonymousCustomer] = React.useState(false);
    const [anonymousCustomerName, setAnonymousCustomerName] = React.useState('');
    const [anonymousCustomerPhone, setAnonymousCustomerPhone] = React.useState('');
    const [anonymousCustomerEmail, setAnonymousCustomerEmail] = React.useState('');
    const [saleDate, setSaleDate] = React.useState(new Date().toISOString().slice(0, 16));
    const [notes, setNotes] = React.useState('');
    const [taxAmount, setTaxAmount] = React.useState('0.00');
    const [discountType, setDiscountType] = React.useState('amount');
    const [discountValue, setDiscountValue] = React.useState('0.00');
    
    const [items, setItems] = React.useState([]);
    const [payments, setPayments] = React.useState([]);
    const [invoices, setInvoices] = React.useState([]);
    
    const [searchQuery, setSearchQuery] = React.useState('');
    const [searchResults, setSearchResults] = React.useState([]);
    const [showSearchResults, setShowSearchResults] = React.useState(false);
    const [hasSearched, setHasSearched] = React.useState(false); // Pour savoir si une recherche a été effectuée
    const searchContainerRef = React.useRef(null); // Référence pour détecter les clics en dehors
    
    const [errors, setErrors] = React.useState({});
    const [isSubmitting, setIsSubmitting] = React.useState(false);
    const [submitSuccess, setSubmitSuccess] = React.useState(false);
    const [isLoading, setIsLoading] = React.useState(true);
    const [notification, setNotification] = React.useState(null); // Notification pour les actions

    const saleId = window.SALE_FORM_CONFIG?.saleId;
    const isNewSale = !saleId;

    // Charger les clients et les données de la vente (si modification)
    React.useEffect(() => {
      const loadData = async () => {
        try {
          // Charger les clients
          const customersResponse = await fetch(getApiUrl('customers/'), {
            headers: {
              'X-CSRFToken': CSRF_TOKEN,
            },
          });
          const customersData = await customersResponse.json();
          setCustomers(customersData.customers || []);
          // Si modification, charger les données de la vente
          if (!isNewSale && saleId) {
            console.log('📥 Chargement des données de la vente:', saleId);
            const saleResponse = await fetch(getApiUrl(`${saleId}/`), {
              headers: {
                'X-CSRFToken': CSRF_TOKEN,
              },
            });
            
            if (!saleResponse.ok) {
              console.error('❌ Erreur HTTP lors du chargement de la vente:', saleResponse.status, saleResponse.statusText);
              throw new Error(`Erreur ${saleResponse.status}: ${saleResponse.statusText}`);
            }
            
            const saleData = await saleResponse.json();
            console.log('📦 Données de la vente reçues:', saleData);
            
            if (saleData.error) {
              console.error('❌ Erreur dans la réponse:', saleData.error);
              throw new Error(saleData.error);
            }
            
            if (saleData.sale_id) {
              // Remplir le formulaire avec les données existantes
              // Gérer le client anonyme si nécessaire
              if (saleData.customer_is_anonymous && saleData.anonymous_customer) {
                setIsAnonymousCustomer(true);
                setAnonymousCustomerName(saleData.anonymous_customer.name || '');
                setAnonymousCustomerPhone(saleData.anonymous_customer.phone || '');
                setAnonymousCustomerEmail(saleData.anonymous_customer.email || '');
                setCustomerId(null);
              } else {
                setCustomerId(saleData.customer_id);
                setIsAnonymousCustomer(false);
              }
              if (saleData.sale_date) {
                const date = new Date(saleData.sale_date);
                setSaleDate(date.toISOString().slice(0, 16));
              }
              setNotes(saleData.notes || '');
              setTaxAmount(saleData.tax_amount || '0.00');
              setDiscountType(saleData.discount_type || 'amount');
              setDiscountValue(saleData.discount_value || '0.00');
              
              // Charger les items
              const loadedItems = saleData.items.map(item => ({
                productId: item.product_id,
                productName: item.product_name,
                productBarcode: item.product_barcode,
                quantity: item.quantity,
                unitPrice: parseFloat(item.unit_price),
                lineTotal: parseFloat(item.line_total),
              }));
              setItems(loadedItems);
              
              // Charger les paiements
              const loadedPayments = saleData.payments.map(payment => ({
                id: payment.id, // ID pour la mise à jour
                amount: payment.amount,
                paymentMethod: payment.payment_method,
              }));
              setPayments(loadedPayments);
              
              // Charger les factures
              setInvoices(saleData.invoices || []);
            } else {
              // Pour une nouvelle vente, initialiser avec un paiement vide
              setPayments([{ amount: '', paymentMethod: 'cash' }]);
            }
          } else {
            // Pour une nouvelle vente, initialiser avec un paiement vide
            setPayments([{ amount: '', paymentMethod: 'cash' }]);
          }
        } catch (error) {
          console.error('❌ Erreur lors du chargement des données:', error);
          setNotification({
            type: 'error',
            message: `Erreur lors du chargement: ${error.message || 'Erreur inconnue'}`,
          });
          setTimeout(() => {
            setNotification(null);
          }, NOTIFICATION_DURATION);
        } finally {
          setIsLoading(false);
        }
      };
      loadData();
    }, []);

    // Calculs
    const subtotal = items.reduce((sum, item) => sum + parseFloat(item.lineTotal || 0), 0);
    
    // Calculer le montant réel de la remise selon le type
    let discountAmount = 0;
    if (discountType === 'percentage') {
      discountAmount = subtotal * (parseFloat(discountValue || 0) / 100);
    } else {
      discountAmount = parseFloat(discountValue || 0);
    }
    
    const subtotalAfterDiscount = Math.max(0, subtotal - discountAmount);
    const totalAmount = subtotalAfterDiscount + parseFloat(taxAmount || 0);
    const totalPaid = payments.reduce((sum, payment) => sum + parseFloat(payment.amount || 0), 0);
    const balanceDue = totalAmount - totalPaid;

    // Recherche de produits
    const searchProducts = React.useCallback(async (query) => {
      if (query.length < 2) {
        setSearchResults([]);
        setShowSearchResults(false);
        setHasSearched(false);
        return;
      }

      try {
        const url = getApiUrl(`products/search/?q=${encodeURIComponent(query)}`);
        console.log('🔍 Recherche produits:', url);
        const response = await fetch(url, {
          headers: {
            'X-CSRFToken': CSRF_TOKEN,
          },
        });
        const data = await response.json();
        const products = data.products || [];
        setSearchResults(products);
        setShowSearchResults(true);
        setHasSearched(true); // Marquer qu'une recherche a été effectuée
      } catch (error) {
        console.error('Erreur lors de la recherche:', error);
        setSearchResults([]);
        setHasSearched(true);
      }
    }, []);

    React.useEffect(() => {
      const timer = setTimeout(() => {
        if (searchQuery) {
          searchProducts(searchQuery);
        }
      }, 300);
      return () => clearTimeout(timer);
    }, [searchQuery, searchProducts]);

    // Fermer les résultats de recherche quand on clique en dehors
    React.useEffect(() => {
      const handleClickOutside = (event) => {
        if (searchContainerRef.current && !searchContainerRef.current.contains(event.target)) {
          setShowSearchResults(false);
        }
      };

      if (showSearchResults) {
        document.addEventListener('mousedown', handleClickOutside);
      }

      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }, [showSearchResults]);

    // Ajouter un produit
    const addProduct = async (product) => {
      // Vérifier si le produit n'est pas déjà dans la liste
      if (items.find(item => item.productId === product.id)) {
        setNotification({
          type: 'error',
          message: 'Ce produit est déjà dans la vente',
        });
        setTimeout(() => {
          setNotification(null);
        }, NOTIFICATION_DURATION);
        return;
      }

      // Valider le stock
      try {
        const url = getApiUrl('validate-item/');
        console.log('✅ Validation ajout produit:', url);
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN,
          },
          body: JSON.stringify({
            product_id: product.id,
            quantity: 1,
          }),
        });
        const data = await response.json();
        
        if (!data.valid) {
          setNotification({
            type: 'error',
            message: data.error || 'Stock insuffisant',
          });
          setTimeout(() => {
            setNotification(null);
          }, NOTIFICATION_DURATION);
          return;
        }

        // Ajouter le produit avec quantité 1
        const newItem = {
          productId: product.id,
          productName: product.name,
          productBarcode: product.barcode,
          quantity: 1,
          unitPrice: parseFloat(data.average_price),
          lineTotal: parseFloat(data.total_price),
          lots: data.lots,
        };

        

        setItems([...items, newItem]);
        setSearchQuery('');
        setShowSearchResults(false);
        
        // Afficher une notification de succès
        setNotification({
          type: 'success',
          message: `${product.name} ajouté avec succès`,
        });
        
        // Fermer automatiquement après la durée définie
        setTimeout(() => {
          setNotification(null);
        }, NOTIFICATION_DURATION);
      } catch (error) {
        console.error('Erreur lors de l\'ajout du produit:', error);
        setNotification({
          type: 'error',
          message: 'Erreur lors de l\'ajout du produit',
        });
        setTimeout(() => {
          setNotification(null);
        }, NOTIFICATION_DURATION);
      }
    };

    // Mettre à jour la quantité d'un item
    const updateItemQuantity = async (index, newQuantity) => {
      if (newQuantity <= 0) {
        removeItem(index);
        return;
      }

      const item = items[index];
      
      // Valider le stock
      try {
        const url = getApiUrl('validate-item/');
        console.log('🔄 Validation mise à jour:', url);
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN,
          },
          body: JSON.stringify({
            product_id: item.productId,
            quantity: newQuantity,
          }),
        });
        const data = await response.json();
        
        if (!data.valid) {
          setNotification({
            type: 'error',
            message: data.error || 'Stock insuffisant',
          });
          setTimeout(() => {
            setNotification(null);
          }, NOTIFICATION_DURATION);
          return;
        }

        // Mettre à jour l'item
        const updatedItems = [...items];
        updatedItems[index] = {
          ...item,
          quantity: newQuantity,
          unitPrice: parseFloat(data.average_price),
          lineTotal: parseFloat(data.total_price),
          lots: data.lots,
        };
        setItems(updatedItems);
      } catch (error) {
        console.error('Erreur lors de la mise à jour:', error);
        setNotification({
          type: 'error',
          message: 'Erreur lors de la mise à jour de la quantité',
        });
        setTimeout(() => {
          setNotification(null);
        }, NOTIFICATION_DURATION);
      }
    };

    // Supprimer un item
    const removeItem = (index) => {
      setItems(items.filter((_, i) => i !== index));
    };

    // Ajouter un paiement
    const addPayment = () => {
      setPayments([...payments, { amount: '', paymentMethod: 'cash' }]);
    };

    // Mettre à jour un paiement
    const updatePayment = (index, field, value) => {
      const updatedPayments = [...payments];
      updatedPayments[index] = {
        ...updatedPayments[index],
        [field]: value,
      };
      setPayments(updatedPayments);
    };

    // Supprimer un paiement
    const removePayment = (index) => {
      // Pour les nouvelles ventes, ne pas permettre de supprimer le seul paiement
      if (isNewSale && payments.length === 1) {
        return;
      }
      setPayments(payments.filter((_, i) => i !== index));
    };

    // Copier le montant total dans le champ de paiement
    const copyTotalToPayment = () => {
      if (payments.length > 0 && totalAmount > 0) {
        const updatedPayments = [...payments];
        updatedPayments[0] = {
          ...updatedPayments[0],
          amount: totalAmount.toFixed(2),
        };
        setPayments(updatedPayments);
      }
    };

    // Soumettre la vente
    // Générer une facture
    const handleGenerateInvoice = async () => {
      if (!saleId) {
        setNotification({
          type: 'error',
          message: 'Impossible de générer une facture pour une vente non sauvegardée',
        });
        setTimeout(() => {
          setNotification(null);
        }, NOTIFICATION_DURATION);
        return;
      }

      try {
        // Appeler l'API pour générer la facture
        const response = await fetch(getApiUrl(`${saleId}/generate-invoice/`), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN,
          },
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          setNotification({
            type: 'error',
            message: data.error || 'Erreur lors de la génération de la facture',
          });
          setTimeout(() => {
            setNotification(null);
          }, NOTIFICATION_DURATION);
          return;
        }

        // Ouvrir la prévisualisation dans un nouvel onglet
        if (data.invoice_id) {
          const previewUrl = `/invoices/${data.invoice_id}/preview/`;
          window.open(previewUrl, '_blank');
          
          // Recharger les factures pour afficher la nouvelle
          const saleResponse = await fetch(getApiUrl(`${saleId}/`), {
            headers: {
              'X-CSRFToken': CSRF_TOKEN,
            },
          });
          const saleData = await saleResponse.json();
          if (saleData.invoices) {
            setInvoices(saleData.invoices);
          }
          
          setNotification({
            type: 'success',
            message: 'Facture générée avec succès !',
          });
          setTimeout(() => {
            setNotification(null);
          }, NOTIFICATION_DURATION);
        }
      } catch (error) {
        console.error('Erreur lors de la génération de la facture:', error);
        setNotification({
          type: 'error',
          message: 'Erreur lors de la génération de la facture',
        });
        setTimeout(() => {
          setNotification(null);
        }, NOTIFICATION_DURATION);
      }
    };

    const handleSubmit = async (e) => {
      e.preventDefault();
      setErrors({});
      setIsSubmitting(true);
      setSubmitSuccess(false);

      // Validation
      const validationErrors = {};
      
      if (!isAnonymousCustomer && !customerId) {
        validationErrors.customer = 'Le client est requis';
      }
      
      if (isAnonymousCustomer && !anonymousCustomerName.trim()) {
        validationErrors.anonymous_customer_name = 'Le nom du client anonyme est requis';
      }
      
      if (items.length === 0) {
        validationErrors.items = 'Au moins un produit est requis';
      }
      
      if (payments.length === 0) {
        validationErrors.payments = 'Au moins un paiement est requis';
      }

      // Valider les paiements
      payments.forEach((payment, index) => {
        const amount = parseFloat(payment.amount);
        if (!amount || amount <= 0) {
          validationErrors[`payments.${index}.amount`] = 'Montant invalide';
        }
      });

      if (Object.keys(validationErrors).length > 0) {
        setErrors(validationErrors);
        setIsSubmitting(false);
        return;
      }

      // Préparer les données
      const saleData = {
        customer_id: isAnonymousCustomer ? null : customerId,
        sale_date: saleDate,
        tax_amount: taxAmount || '0.00',
        discount_type: discountType,
        discount_value: discountValue || '0.00',
        notes: notes,
        items: items.map(item => ({
          product_id: item.productId,
          quantity: item.quantity,
        })),
        payments: payments.map(payment => ({
          id: payment.id || null, // ID pour la mise à jour (null si nouveau paiement)
          amount: payment.amount,
          payment_method: payment.paymentMethod,
        })),
      };
      
      // Ajouter les informations du client anonyme si nécessaire
      if (isAnonymousCustomer) {
        saleData.anonymous_customer = {
          name: anonymousCustomerName.trim(),
          phone: anonymousCustomerPhone.trim() || null,
          email: anonymousCustomerEmail.trim() || null,
        };
      }

      try {
        let response;
        if (isNewSale) {
          // Créer une nouvelle vente
          response = await fetch(getApiUrl('create/'), {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': CSRF_TOKEN,
            },
            body: JSON.stringify(saleData),
          });
        } else {
          // Mettre à jour une vente existante
          response = await fetch(getApiUrl(`${saleId}/update/`), {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': CSRF_TOKEN,
            },
            body: JSON.stringify(saleData),
          });
        }

        const data = await response.json();

        if (!response.ok || !data.success) {
          // Gérer les erreurs
          if (data.errors) {
            setErrors(data.errors);
          } else {
            setErrors({ _general: data.error || `Erreur lors de la ${isNewSale ? 'création' : 'mise à jour'} de la vente` });
          }
          setIsSubmitting(false);
          return;
        }

        // Succès
        setSubmitSuccess(true);
        if (isNewSale) {
          setNotification({
            type: 'success',
            message: 'Vente créée avec succès ! Redirection en cours ...',
          });
        } else {
          setNotification({
            type: 'success',
            message: 'Vente mise à jour avec succès ! Redirection en cours ...',
          });
        }
        setTimeout(() => {
          // Recharger la page pour voir les modifications
          if (isNewSale) {
            window.location.href = `/admin/sales/sale/`;
          } else {
            window.location.reload();
          }
        }, 1500);
      } catch (error) {
        console.error('Erreur lors de la soumission:', error);
        setErrors({ _general: 'Erreur de connexion' });
        setIsSubmitting(false);
      }
    };

    // Afficher un loader pendant le chargement
    if (isLoading) {
      return (
        <div className="sale-form-react">
          <div style={{ textAlign: 'center', padding: '50px' }}>
            <p>Chargement des données...</p>
          </div>
        </div>
      );
    }

    return (
      <div className="content-main">
        {/* Notification toast */}
        {notification && (
          <div className={`notification notification-${notification.type}`}>
            <span>{notification.message}</span>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="notification-close"
            >
              ×
            </button>
          </div>
        )}
        <form onSubmit={handleSubmit}>
          {/* En-tête */}
          <div className="sale-header">
            <div className="form-group">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <label style={{ margin: 0 }}>Client *</label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '5px', margin: 0, fontWeight: 'normal' }}>
                  <input
                    type="checkbox"
                    checked={isAnonymousCustomer}
                    onChange={(e) => {
                      setIsAnonymousCustomer(e.target.checked);
                      if (e.target.checked) {
                        setCustomerId(null);
                      }
                    }}
                  />
                  <span>Client anonyme</span>
                </label>
              </div>
              {!isAnonymousCustomer ? (
                <select
                  value={customerId || ''}
                  onChange={(e) => setCustomerId(e.target.value ? parseInt(e.target.value) : null)}
                  className={errors.customer ? 'error' : ''}
                >
                  <option value="">Sélectionner un client</option>
                  {customers.map(customer => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name}{customer.credit_balance > 0 ? ` (Crédit: ${customer.credit_balance} FCFA)` : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <input
                    type="text"
                    placeholder="Nom du client *"
                    value={anonymousCustomerName}
                    onChange={(e) => setAnonymousCustomerName(e.target.value)}
                    className={errors.anonymous_customer_name ? 'error' : ''}
                  />
                  <input
                    type="text"
                    placeholder="Téléphone (optionnel)"
                    value={anonymousCustomerPhone}
                    onChange={(e) => setAnonymousCustomerPhone(e.target.value)}
                  />
                  <input
                    type="email"
                    placeholder="Email (optionnel)"
                    value={anonymousCustomerEmail}
                    onChange={(e) => setAnonymousCustomerEmail(e.target.value)}
                  />
                </div>
              )}
              {errors.customer && <span className="error-message">{errors.customer}</span>}
              {errors.anonymous_customer_name && <span className="error-message">{errors.anonymous_customer_name}</span>}
            </div>
            <div className="form-group">
              <label>Date de vente</label>
              <input
                type="datetime-local"
                value={saleDate}
                onChange={(e) => setSaleDate(e.target.value)}
              />
            </div>
          </div>

          {/* Recherche de produits */}
          <div className="product-search-section">
            <h3>Produits</h3>
            <div className="search-container" ref={searchContainerRef}>
              <input
                type="text"
                placeholder="Rechercher un produit (nom ou code-barres)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  if (searchQuery.length >= 2) {
                    setShowSearchResults(true);
                  }
                }}
              />
              {showSearchResults && (
                <div className="search-results">
                  {searchResults.length > 0 ? (
                    searchResults.map(product => (
                      <div
                        key={product.id}
                        className={`search-result-item ${product.stock_available === 0 ? 'out-of-stock' : ''}`}
                        onClick={() => addProduct(product)}
                      >
                        <div className="product-name">{product.name}</div>
                        <div className="product-details">
                          <span>{product.barcode}</span>
                          <span>{parseFloat(product.sale_price).toFixed(2)} GNF</span>
                          <span>Stock: {product.stock_available}</span>
                        </div>
                      </div>
                    ))
                  ) : hasSearched && searchQuery.length >= 2 ? (
                    <div className="search-no-results">
                      Aucun produit trouvé pour "{searchQuery}"
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>

          {/* Tableau des items */}
          <div className="items-section">
            {errors.items && <div className="error-message">{errors.items}</div>}
            <table className="items-table">
              <thead>
                <tr>
                  <th>Produit</th>
                  <th>Quantité</th>
                  <th>Prix unitaire</th>
                  <th>Total</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, index) => (
                  <tr key={index}>
                    <td>{item.productName} ({item.productBarcode})</td>
                    <td>
                      <input
                        type="number"
                        min="1"
                        value={item.quantity}
                        onChange={(e) => updateItemQuantity(index, parseInt(e.target.value) || 1)}
                      />
                    </td>
                    <td>{item.unitPrice.toFixed(2)} GNF</td>
                    <td>{item.lineTotal.toFixed(2)} GNF</td>
                    <td>
                      <button
                        type="button"
                        onClick={() => removeItem(index)}
                        className="btn-remove"
                      >
                        Supprimer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Totaux et remise */}
          <div className="totals-section">
            <div className="totals-row">
              <span>Sous-total:</span>
              <span>{subtotal.toFixed(2)} GNF</span>
            </div>
            <div className="totals-row">
              <label>Remise:</label>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                <select
                  value={discountType}
                  onChange={(e) => {
                    setDiscountType(e.target.value);
                    setDiscountValue('0.00');
                  }}
                  style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
                >
                  <option value="amount">Montant</option>
                  <option value="percentage">Pourcentage</option>
                </select>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max={discountType === 'percentage' ? 100 : subtotal}
                  value={discountValue}
                  onChange={(e) => setDiscountValue(e.target.value)}
                  style={{ width: '120px', padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
                />
                <span>{discountType === 'percentage' ? '%' : 'GNF'}</span>
                {discountType === 'percentage' && parseFloat(discountValue || 0) > 0 && (
                  <span style={{ color: '#666', fontSize: '0.9em' }}>
                    ({discountAmount.toFixed(2)} GNF)
                  </span>
                )}
              </div>
            </div>
            <div className="totals-row">
              <span>Sous-total après remise:</span>
              <span>{subtotalAfterDiscount.toFixed(2)} GNF</span>
            </div>
            <div className="totals-row">
              <label>Taxe:</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={taxAmount}
                onChange={(e) => setTaxAmount(e.target.value)}
              />
            </div>
            <div className="totals-row total-main">
              <span>Total TTC:</span>
              <span>{totalAmount.toFixed(2)} GNF</span>
            </div>
          </div>

          {/* Paiements */}
          <div className="payments-section">
            <h3>Paiements</h3>
            {errors.payments && <div className="error-message">{errors.payments}</div>}
            {/* Afficher le bouton seulement pour les modifications */}
            {!isNewSale && (
              <button
                type="button"
                onClick={addPayment}
                className="btn-add"
              >
                + Ajouter un paiement
              </button>
            )}
            {payments.map((payment, index) => (
              <div key={index} className="payment-row">
                <div className="payment-amount-input-wrapper">
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="Montant"
                    value={payment.amount}
                    onChange={(e) => updatePayment(index, 'amount', e.target.value)}
                    className={errors[`payments.${index}.amount`] ? 'error' : ''}
                  />
                  {/* Bouton pour copier le total (seulement pour nouvelles ventes, premier paiement) */}
                  {isNewSale && index === 0 && totalAmount > 0 && (
                    <button
                      type="button"
                      onClick={copyTotalToPayment}
                      className="btn-copy-total"
                      title="Copier le montant total"
                    >
                      📋
                    </button>
                  )}
                </div>
                <select
                  value={payment.paymentMethod}
                  onChange={(e) => updatePayment(index, 'paymentMethod', e.target.value)}
                >
                  <option value="cash">Espèces</option>
                  <option value="card">Carte</option>
                  <option value="mobile_money">Mobile Money</option>
                  <option value="bank_transfer">Virement bancaire</option>
                  <option value="other">Autre</option>
                </select>
                {/* Cacher le bouton supprimer pour le premier paiement dans les nouvelles ventes */}
                {!(isNewSale && index === 0 && payments.length === 1) && (
                  <button
                    type="button"
                    onClick={() => removePayment(index)}
                    className="btn-remove"
                  >
                    Supprimer
                  </button>
                )}
                {errors[`payments.${index}.amount`] && (
                  <span className="error-message">{errors[`payments.${index}.amount`]}</span>
                )}
              </div>
            ))}
            <div className="payment-summary">
              <div className="summary-row">
                <span>Montant payé:</span>
                <span>{totalPaid.toFixed(2)} GNF</span>
              </div>
              <div className={`summary-row ${balanceDue > 0 ? 'has-balance' : 'no-balance'}`}>
                <span>Solde restant:</span>
                <span>{balanceDue.toFixed(2)} GNF</span>
              </div>
            </div>
          </div>

          {/* Factures générées */}
          {!isNewSale && invoices.length > 0 && (
            <div className="items-section">
              <h3>Factures générées</h3>
              <table className="items-table">
                <thead>
                  <tr>
                    <th>Numéro</th>
                    <th>Date</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map(invoice => (
                    <tr key={invoice.id}>
                      <td>{invoice.invoice_number}</td>
                      <td>{invoice.invoice_date ? new Date(invoice.invoice_date).toLocaleString('fr-FR') : '—'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '10px' , justifyContent: 'flex-end'}}>
                          <button
                            type="button"
                            onClick={() => window.open(`/invoices/${invoice.id}/preview/`, '_blank')}
                            className="btn-invoice-preview"
                            title="Prévisualiser"
                          >
                            Prévisualiser
                          </button>
                          <button
                            type="button"
                            onClick={() => window.open(`/invoices/${invoice.id}/pdf/`, '_blank')}
                            className="btn-invoice-download"
                            title="Télécharger PDF"
                          >
                            PDF
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Notes */}
          <div className="notes-section">
            <h3>Notes</h3>
            <textarea
              value={notes}
              placeholder="Fournissez des informations supplémentaires sur la vente ou le client..."
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>

          {/* Messages d'erreur généraux */}
          {errors._general && (
            <div className="error-message general-error">{errors._general}</div>
          )}


          {/* Bouton de soumission */}
          <div className="submit-section">
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              {/* Bouton générer facture (seulement pour les ventes existantes) */}
              {!isNewSale && saleId && (
                <button
                  type="button"
                  onClick={handleGenerateInvoice}
                  className="btn-generate-invoice"
                  disabled={isSubmitting}
                >
                  📄 Générer facture
                </button>
              )}
              <button
                type="submit"
                disabled={isSubmitting}
                className="btn-submit"
              >
                {isSubmitting ? 'Enregistrement...' : (isNewSale ? 'Enregistrer la vente' : 'Mettre à jour la vente')}
              </button>
            </div>
          </div>
        </form>
      </div>
    );
  }

  // Initialiser React quand le DOM est prêt
  function initReact() {
    console.log('🟡 Tentative d\'initialisation React...');
    const container = document.getElementById('content-main');
    console.log('🟡 Container:', container);
    console.log('🟡 React:', typeof window.React);
    console.log('🟡 ReactDOM:', typeof window.ReactDOM);
    
    if (!container) {
      console.error('❌ Container React non trouvé!');
      return;
    }
    
    if (!window.React || !window.ReactDOM) {
      console.error('❌ React ou ReactDOM non disponible!');
      // Réessayer après 500ms
      setTimeout(initReact, 500);
      return;
    }
    
    try {
      console.log('✅ Initialisation React...');
      const root = window.ReactDOM.createRoot(container);
      root.render(<SaleForm />);
      console.log('✅ React initialisé avec succès!');
    } catch (error) {
      console.error('❌ Erreur lors de l\'initialisation React:', error);
    }
  }

  // Essayer plusieurs fois au cas où React se charge après
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReact);
  } else {
    initReact();
  }
  
  // Fallback après 2 secondes
  setTimeout(initReact, 2000);
})();


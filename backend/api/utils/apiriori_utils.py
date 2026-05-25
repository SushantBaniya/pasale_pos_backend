
from api.models import Order, OrderItem
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
import pandas as pd


def get_transactions(business_id, days=180):
    """
    Extract basket transactions the POS orders.
    Each order becomes one transaction (basket of products).
    """
    from django.utils import timezone
    from datetime import timedelta

    since = timezone.now() - timedelta(days=days)

    # Get all completed orders for this business
    orders = Order.objects.filter(
        business_id=business_id,
        created_at__gte=since,
        order_status__name='Completed'   # adjust to your status name
    ).prefetch_related('items__product_id')

    transactions = []

    for order in orders:
        # Get product names in this order
        items = [
            item.product_id.product_name
            for item in order.items.all()
            if item.product_id is not None
        ]
        if len(items) >= 2:   # only baskets with 2+ items are useful
            transactions.append(items)

    return transactions


def run_apriori(business_id, min_support=0.2, min_confidence=0.5, min_lift=1.2):
    """
    Run Apriori algorithm on business transaction data.
    Returns association rules.
    """
    transactions = get_transactions(business_id)

    if len(transactions) < 10:
        return None, "Not enough transaction data yet (need at least 10 orders)"

    # Encode transactions into one-hot matrix
    te = TransactionEncoder()
    te_array = te.fit_transform(transactions)
    df = pd.DataFrame(te_array, columns=te.columns_)

    # Mine frequent itemsets
    frequent_itemsets = apriori(
        df,
        min_support=min_support,
        use_colnames=True
    )

    if frequent_itemsets.empty:
        return None, "No frequent patterns found. Try lowering min_support."

    # Generate association rules
    rules = association_rules(
        frequent_itemsets,
        metric="lift",
        min_threshold=min_lift
    )

    # Filter by confidence
    rules = rules[rules['confidence'] >= min_confidence]
    rules = rules.sort_values('confidence', ascending=False)

    return rules, f"{len(rules)} rules found from {len(transactions)} transactions"

from api.models import Product, StockAlert

def get_reorder_suggestions(business_id):
    """
    Check low stock products and suggest related items to reorder
    using Apriori rules. Integrates with your existing StockAlert model.
    """
    rules, message = run_apriori(business_id)

    # Get currently low stock products using dynamic check (quantity <= reorder_level)
    from django.db.models import F
    low_stock_products = Product.objects.filter(
        business_id=business_id,
        quantity__lte=F('reorder_level')
    )

    suggestions = []

    for product in low_stock_products:
        product_name = product.product_name

        # Find rules where this product is in the antecedent (if we have rules)
        related_items = []
        if rules is not None:
            matched_rules = rules[
                rules['antecedents'].apply(lambda x: product_name in x)
            ]

            for _, rule in matched_rules.iterrows():
                consequents = list(rule['consequents'])
                related_items.append({
                    'items': consequents,
                    'confidence': round(rule['confidence'], 2),
                    'lift': round(rule['lift'], 2)
                })

        # Always include the low stock product, even if no related items found
        suggestions.append({
            'low_stock_product': product_name,
            'also_reorder': related_items
        })

    return {
        "message": message if rules is not None else "Not enough sales data for 'also reorder' patterns yet.",
        "suggestions": suggestions
    }


from api.models import Product, StockAlert, Business


def create_apriori_stock_alerts(business_id):
    """
    Runs Apriori, finds low stock items, and auto-creates
    StockAlert entries for related items that should be reordered.
    """

    rules, message = run_apriori(business_id)

    if rules is None:
        return {"error": message}

    # Get all low stock products for this business
    low_stock_products = Product.objects.filter(
        business_id=business_id,
        is_low_stock=True
    )

    business = Business.objects.get(id=business_id)

    alerts_created = []
    alerts_skipped = []

    for product in low_stock_products:

        # Find rules where this product is the trigger
        matched_rules = rules[
            rules['antecedents'].apply(lambda x: product.product_name in x)
        ]

        for _, rule in matched_rules.iterrows():
            consequents = list(rule['consequents'])
            confidence = round(rule['confidence'] * 100)
            lift = round(rule['lift'], 2)

            # Find each related product that should be reordered
            for related_name in consequents:
                try:
                    related_product = Product.objects.get(
                        product_name=related_name,
                        business_id=business_id
                    )
                except Product.DoesNotExist:
                    continue

                # Build a clear alert message
                alert_message = (
                    f"'{product.product_name}' is low on stock — "
                    f"{confidence}% of customers also buy '{related_name}'. "
                    f"Consider reordering '{related_name}' soon. "
                    f"(Lift: {lift})"
                )

                # Use get_or_create to avoid duplicate alerts
                alert, created = StockAlert.objects.get_or_create(
                    business_id=business,
                    product=related_product,
                    is_resolved=False,
                    defaults={'message': alert_message}
                )

                if created:
                    alerts_created.append({
                        'trigger': product.product_name,
                        'reorder': related_name,
                        'confidence': f"{confidence}%",
                        'lift': lift,
                        'alert_id': alert.id
                    })
                else:
                    alerts_skipped.append(related_name)

    return {
        "status": "success",
        "rules_used": message,
        "alerts_created": alerts_created,
        "alerts_skipped": alerts_skipped,
        "total_created": len(alerts_created),
        "total_skipped": len(alerts_skipped)
    }


def resolve_apriori_alerts(business_id):
    """
    Resolves Apriori-generated alerts when stock is replenished.
    Call this after a restock/purchase order is completed.
    """
    # Find products that are no longer low stock
    healthy_products = Product.objects.filter(
        business_id=business_id,
        is_low_stock=False
    )

    resolved_count = 0
    for product in healthy_products:
        updated = StockAlert.objects.filter(
            business_id=business_id,
            product=product,
            is_resolved=False
        ).update(is_resolved=True)
        resolved_count += updated

    return {
        "status": "success",
        "alerts_resolved": resolved_count
    }


from api.models import AprioriRule, Business


def save_rules_to_db(business_id, rules):
    """
    Saves freshly generated Apriori rules to the database.
    Overwrites old rules for this business.
    """
    business = Business.objects.get(id=business_id)

    # Delete old rules for this business before saving new ones
    deleted_count, _ = AprioriRule.objects.filter(
        business_id=business
    ).delete()

    rules_saved = []
    for _, rule in rules.iterrows():
        antecedents = ', '.join(list(rule['antecedents']))
        consequents = ', '.join(list(rule['consequents']))

        apriori_rule = AprioriRule.objects.create(
            business_id=business,
            antecedent=antecedents,
            consequent=consequents,
            support=round(rule['support'], 4),
            confidence=round(rule['confidence'], 4),
            lift=round(rule['lift'], 4)
        )
        rules_saved.append(apriori_rule)

    return {
        "deleted_old_rules": deleted_count,
        "saved_new_rules": len(rules_saved)
    }


def load_rules_from_db(business_id):
    """
    Loads saved Apriori rules from the database.
    Used by the API so we don't recompute rules on every request.
    """
    rules = AprioriRule.objects.filter(
        business_id=business_id
    ).order_by('-confidence')

    return [
        {
            "if_customer_buys": rule.antecedent,
            "they_also_buy": rule.consequent,
            "confidence": f"{rule.confidence:.0%}",
            "lift": rule.lift,
            "support": rule.support,
            "last_updated": rule.updated_at.strftime("%Y-%m-%d %H:%M")
        }
        for rule in rules
    ]
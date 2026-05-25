from django.core.cache import cache

def get_or_set_product_cache(key, fetch_function, timeout=300):
    """
    Retrieves a product from the cache or sets it if not present.

    Args:
        key (str): The cache key for the product.
        fetch_function (callable): A function that fetches the product data if not in cache.
        timeout (int): Cache timeout in seconds.

    Returns:
        The product data, either from cache or fetched using the provided function.
    """
    data = cache.get(key)
    if data is not None:
        return data  
    data = fetch_function()
    cache.set(key, data, timeout)
    return data
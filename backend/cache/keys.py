def productkeys(user_id, version="v1"):
    return f'product:{user_id}:v{version}'

def productkey(user_id, product_id, version="v1"):
    return f'product:{user_id}:{product_id}:v{version}'
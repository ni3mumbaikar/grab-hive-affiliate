from src.models import Product

def generate_instagram_caption(product: Product) -> str:
    """Generate an Instagram caption for the product.
    
    Example format:
    🔥 Deal Alert
    
    Samsung Galaxy Buds
    
    ⭐ 4.6 Rating
    
    💰 ₹3499
    
    Buy Here 👇
    
    <affiliate link>
    
    #<provider> #deal #electronics
    """
    # Clean provider for hashtag format (lowercase, no spaces)
    provider_hashtag = product.provider.lower().replace(" ", "").replace("-", "")
    if not provider_hashtag:
        provider_hashtag = "deal"
        
    rating_str = f"⭐ {product.rating} Rating" if product.rating else "⭐ Top Rated"
    price_val = product.price.strip() if product.price else ""
    price_str = ""
    if price_val:
        if not price_val.startswith("₹") and not price_val.startswith("$"):
            price_str = f"💰 ₹{price_val}"
        else:
            price_str = f"💰 {price_val}"
            
    caption = (
        "🔥 Deal Alert\n\n"
        f"{product.name}\n\n"
    )
        
    caption += (
        "Buy Here 👇\n"
        f"{product.affiliate_link}\n\n"
        f"#{provider_hashtag} #deal"
    )
    return caption

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
    price_str = f"💰 {product.price}" if product.price else ""
    
    caption = (
        "🔥 Deal Alert\n\n"
        f"{product.name}\n\n"
        f"{rating_str}\n\n"
        f"{price_str}\n\n"
        "Buy Here 👇\n\n"
        f"{product.affiliate_link}\n\n"
        f"#{provider_hashtag} #deal #shopping #electronics"
    )
    return caption

from src.core.models import Product

def generate_whatsapp_message(product: Product) -> str:
    """Generate a WhatsApp message for the product."""
    rating_str = f"⭐ {product.rating}" if product.rating else "⭐ Top Rated"
    price_str = f"{product.price}" if product.price else ""
    
    msg = (
        "🔥 New Deal\n\n"
        f"{product.name}\n\n"
        f"{price_str}\n\n"
        f"{rating_str}\n\n"
        "Buy👇\n\n"
        f"{product.affiliate_link}"
    )
    return msg

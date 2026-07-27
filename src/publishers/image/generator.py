import os
import logging
import requests
import re
import time
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont
from src.core.interfaces import ImageGenerator
from src.core.models import Product

logger = logging.getLogger(__name__)

class PILImageGenerator(ImageGenerator):
    """Concrete implementation of ImageGenerator using Pillow (PIL) for image synthesis."""

    def __init__(self, temp_dir: str = "temp"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.tracked_files: List[Path] = []
        
        self.font_bold = self._load_font("segoeuib.ttf", 40)
        self.font_medium = self._load_font("segoeui.ttf", 32)
        self.font_large = self._load_font("segoeuib.ttf", 64)
        self.font_logo = self._load_font("segoeuib.ttf", 48)
        self.font_small = self._load_font("segoeui.ttf", 24)

    def _load_font(self, font_name: str, size: int) -> ImageFont.ImageFont:
        windows_font_path = Path("C:/Windows/Fonts") / font_name
        if windows_font_path.exists():
            try:
                return ImageFont.truetype(str(windows_font_path), size)
            except Exception as e:
                logger.warning("Failed to load font %s: %s. Using default.", font_name, e)
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            pass
        return ImageFont.load_default()

    def _scrape_image_url_from_affiliate_link(self, affiliate_link: str) -> Optional[str]:
        logger.info("Attempting to scrape image URL from: %s", affiliate_link)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            response = requests.get(affiliate_link, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning("Scraping failed: HTTP status %d", response.status_code)
                return None
                
            html = response.text
            og_image = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
            if og_image:
                logger.info("Found image URL in og:image tag.")
                return og_image.group(1)

            amazon_img = re.search(r'"large":"(https://images-na\.ssl-images-amazon\.com/images/I/[^"]+)"', html)
            if amazon_img:
                logger.info("Found Amazon large image pattern.")
                return amazon_img.group(1)
                
            img_matches = re.findall(r'https://[^"\']+\.(?:jpg|jpeg|png)', html)
            for img_url in img_matches:
                if "placeholder" not in img_url and "logo" not in img_url and "/I/" in img_url:
                    logger.info("Found generic matching product image URL: %s", img_url)
                    return img_url
                    
        except Exception as e:
            logger.warning("Failed to scrape affiliate link HTML: %s", e)
            
        return None

    def download_image(self, url: str, is_direct: bool = False) -> str:
        local_path = self.temp_dir / f"downloaded_{int(time.time())}.jpg"
        is_direct_image = is_direct or any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"])
        
        if not is_direct_image:
            scraped_url = self._scrape_image_url_from_affiliate_link(url)
            if scraped_url:
                url = scraped_url
            else:
                logger.warning("Could not scrape image URL. Using placeholder generator.")
                return self._create_fallback_product_image("No Image Available")

        logger.info("Downloading product image from: %s", url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            with open(local_path, "wb") as f:
                f.write(response.content)
                
            self.tracked_files.append(local_path)
            logger.info("Product image downloaded to: %s", local_path)
            return str(local_path.resolve())
            
        except Exception as e:
            logger.error("Failed to download image from %s: %s. Using placeholder.", url, e)
            return self._create_fallback_product_image("Download Failed")

    def _create_fallback_product_image(self, message: str) -> str:
        fallback_path = self.temp_dir / f"fallback_{int(time.time())}.jpg"
        img = Image.new("RGB", (600, 600), "#334155")
        draw = ImageDraw.Draw(img)
        
        text = f"[{message}]"
        bbox = draw.textbbox((0, 0), text, font=self.font_medium)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((600-w)//2, (600-h)//2), text, fill="#94A3B8", font=self.font_medium)
        
        img.save(fallback_path, "JPEG")
        self.tracked_files.append(fallback_path)
        return str(fallback_path.resolve())

    def generate_creative(self, product: Product, img_path: str) -> str:
        output_path = self.temp_dir / f"creative_{int(time.time())}.png"
        logger.info("Generating creative at: %s using product: %s", output_path, product.name)
        
        canvas_width, canvas_height = 1080, 1080
        img = Image.new("RGB", (canvas_width, canvas_height), "#0F172A")
        draw = ImageDraw.Draw(img)
        
        card_x1, card_y1 = 160, 190
        card_x2, card_y2 = 920, 950
        draw.rounded_rectangle(
            [(card_x1, card_y1), (card_x2, card_y2)],
            radius=24,
            fill="#1E293B",
            outline="#334155",
            width=2
        )
        
        try:
            prod_img = Image.open(img_path)
            max_w, max_h = 700, 700
            prod_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            
            card_w = card_x2 - card_x1
            card_h = card_y2 - card_y1
            offset_x = card_x1 + (card_w - prod_img.width) // 2
            offset_y = card_y1 + (card_h - prod_img.height) // 2
            
            if prod_img.mode in ("RGBA", "LA"):
                img.paste(prod_img, (offset_x, offset_y), prod_img)
            else:
                img.paste(prod_img, (offset_x, offset_y))
        except Exception as e:
            logger.error("Failed to load/draw product image inside creative: %s", e)
            
        logo_x, logo_y = 60, 60
        logo_file = Path("config/logo.png")
        logo_pasted = False
        
        if logo_file.exists():
            try:
                logo_img = Image.open(logo_file)
                logo_img.thumbnail((120, 120), Image.Resampling.LANCZOS)
                offset_logo_y = logo_y - 10
                if logo_img.mode in ("RGBA", "LA"):
                    img.paste(logo_img, (logo_x, offset_logo_y), logo_img)
                else:
                    img.paste(logo_img, (logo_x, offset_logo_y))
                logo_pasted = True
            except Exception as e:
                logger.error("Failed to load custom logo file: %s", e)

        if not logo_pasted:
            draw.polygon(
                [(logo_x, logo_y+15), (logo_x+13, logo_y), (logo_x+37, logo_y), 
                 (logo_x+50, logo_y+15), (logo_x+37, logo_y+30), (logo_x+13, logo_y+30)],
                fill="#F97316"
            )
        
        img.save(output_path, "PNG")
        self.tracked_files.append(output_path)
        logger.info("Successfully synthesized promotional creative.")
        return str(output_path.resolve())

    def cleanup(self) -> None:
        logger.info("Starting cleanup of %d temporary files.", len(self.tracked_files))
        for file_path in self.tracked_files:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning("Could not delete temporary file %s: %s", file_path, e)
        self.tracked_files.clear()

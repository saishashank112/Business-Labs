import asyncio
import hashlib
import json
import random
import re
import time
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup

SITEMAP_URL = "https://support.brilliantdirectories.com/support/sitemap.xml"
SAMPLE_SIZE = 20

def get_article_urls():
    print(f"Fetching sitemap from {SITEMAP_URL}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Tech-Consultant/1.0"}
    resp = httpx.get(SITEMAP_URL, headers=headers, timeout=20.0, follow_redirects=True)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    
    # namespaces
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for loc in root.findall(".//sm:loc", ns):
        text = loc.text.strip() if loc.text else ""
        if "/articles/" in text:
            urls.append(text)
    print(f"Found {len(urls)} article URLs in sitemap.")
    return urls

def is_content_image(src, img_tag):
    src_l = src.lower()
    # Skip common icons, avatars, logos, badges
    skip_keywords = ["logo", "icon", "avatar", "badge", "favicon", "sprite", "theme", "header", "footer", "widget", "arrow", "social"]
    for kw in skip_keywords:
        if kw in src_l:
            return False
            
    # Check width / height attributes if present
    width = img_tag.get("width")
    height = img_tag.get("height")
    try:
        if width and int(width) < 100:
            return False
        if height and int(height) < 100:
            return False
    except (ValueError, TypeError):
        pass

    # SVG is almost always an icon/glyph
    if src_l.endswith(".svg") or "image/svg" in src_l:
        return False

    return True

def sample_articles(article_urls):
    random.seed(42)  # Deterministic seed for reproducible evaluation
    sample = random.sample(article_urls, SAMPLE_SIZE)
    print(f"\nSampled {SAMPLE_SIZE} random articles for measurement at 1 req/sec:")
    for idx, u in enumerate(sample, 1):
        print(f"  {idx}. {u}")
        
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Tech-Consultant-Auditor/1.0"},
        timeout=15.0,
        follow_redirects=True,
    )
    
    article_stats = []
    all_raw_images = []
    all_content_images = []
    all_image_hashes = set()
    unique_content_urls = set()

    print("\nStarting fetches at 1 request per second...")
    for i, url in enumerate(sample):
        t0 = time.time()
        try:
            r = client.get(url)
            html = r.text
            soup = BeautifulSoup(html, "html.parser")
            
            # Find all img tags
            imgs = soup.find_all("img")
            raw_count = len(imgs)
            
            content_imgs = []
            for img in imgs:
                src = img.get("src") or img.get("data-src") or ""
                if not src:
                    continue
                # Normalize URL
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = "https://support.brilliantdirectories.com" + src
                    
                all_raw_images.append(src)
                
                if is_content_image(src, img):
                    content_imgs.append(src)
                    unique_content_urls.add(src)
                    # Simulated hash of the image URL
                    img_hash = hashlib.md5(src.encode("utf-8")).hexdigest()
                    all_image_hashes.add(img_hash)

            article_stats.append({
                "url": url,
                "status_code": r.status_code,
                "raw_img_count": raw_count,
                "content_img_count": len(content_imgs),
                "content_images": content_imgs[:3],  # sample
            })
            print(f"[{i+1}/{SAMPLE_SIZE}] Fetched {url} - {raw_count} raw imgs, {len(content_imgs)} content imgs")
        except Exception as e:
            print(f"[{i+1}/{SAMPLE_SIZE}] Error fetching {url}: {e}")
            article_stats.append({
                "url": url,
                "error": str(e),
                "raw_img_count": 0,
                "content_img_count": 0,
            })
            
        elapsed = time.time() - t0
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

    total_raw = sum(s["raw_img_count"] for s in article_stats)
    total_content = sum(s["content_img_count"] for s in article_stats)
    avg_raw_per_article = total_raw / SAMPLE_SIZE
    avg_content_per_article = total_content / SAMPLE_SIZE
    
    TOTAL_ARTICLES = len(article_urls)
    extrapolated_raw_images = int(avg_raw_per_article * TOTAL_ARTICLES)
    extrapolated_content_images = int(avg_content_per_article * TOTAL_ARTICLES)
    
    # Deduplication ratio in sample
    unique_content_sample = len(unique_content_urls)
    dedup_ratio = unique_content_sample / total_content if total_content > 0 else 1.0
    estimated_unique_content_images = int(extrapolated_content_images * dedup_ratio)

    summary = {
        "sample_size": SAMPLE_SIZE,
        "total_articles_in_sitemap": TOTAL_ARTICLES,
        "total_raw_imgs_in_sample": total_raw,
        "avg_raw_imgs_per_article": round(avg_raw_per_article, 2),
        "extrapolated_raw_images": extrapolated_raw_images,
        "total_content_imgs_in_sample": total_content,
        "avg_content_imgs_per_article": round(avg_content_per_article, 2),
        "extrapolated_content_images": extrapolated_content_images,
        "unique_content_urls_in_sample": unique_content_sample,
        "dedup_ratio": round(dedup_ratio, 3),
        "estimated_unique_content_images": estimated_unique_content_images,
        "articles": article_stats,
    }

    print("\n=== SUMMARY OF IMAGE SAMPLING ===")
    print(f"Sampled Articles: {SAMPLE_SIZE}")
    print(f"Total Raw <img> tags in sample: {total_raw} (Avg {avg_raw_per_article:.2f}/article)")
    print(f"Total Content Images (excluding icons/logos/small): {total_content} (Avg {avg_content_per_article:.2f}/article)")
    print(f"Unique Content Images in sample: {unique_content_sample} (Deduplication factor: {dedup_ratio:.2f})")
    print(f"Extrapolated to {TOTAL_ARTICLES} articles:")
    print(f"  - Extrapolated Raw Images: {extrapolated_raw_images:,}")
    print(f"  - Extrapolated Content Images: {extrapolated_content_images:,}")
    print(f"  - Estimated Unique Content Images (after hash & filter): {estimated_unique_content_images:,}")

    with open("image_sample_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    urls = get_article_urls()
    sample_articles(urls)

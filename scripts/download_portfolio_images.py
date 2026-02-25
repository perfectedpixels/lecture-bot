#!/usr/bin/env python3
"""
Download images from Perfect Pixels portfolio pages
"""

import requests
from bs4 import BeautifulSoup
import os
import json
from urllib.parse import urljoin, urlparse
import time

# Portfolio pages to scrape
PORTFOLIO_PAGES = [
    "https://www.perfectpixels.com/core/portfolio/amazon",
    "https://www.perfectpixels.com/core/portfolio/aws",
    "https://www.perfectpixels.com/core/portfolio/indeed",
    "https://www.perfectpixels.com/core/portfolio/stanford-university",
    "https://www.perfectpixels.com/core/portfolio/microsoft",
    "https://www.perfectpixels.com/core/portfolio/trulia",
    "https://www.perfectpixels.com/core/portfolio/classmates-com",
    "https://www.perfectpixels.com/core/portfolio/virgin-travel-group",
    "https://www.perfectpixels.com/core/portfolio/toyota",
    "https://www.perfectpixels.com/core/portfolio/careoregon",
    "https://www.perfectpixels.com/core/portfolio/washington-state-employment-security-department",
    "https://www.perfectpixels.com/core/portfolio/sealaska",
    "https://www.perfectpixels.com/core/portfolio/seattle-university",
    "https://www.perfectpixels.com/core/portfolio/jewish-family-service",
    "https://www.perfectpixels.com/core/portfolio/flutter",
    "https://www.perfectpixels.com/core/portfolio/getty-images",
    "https://www.perfectpixels.com/core/portfolio/snap-village",
    "https://www.perfectpixels.com/core/portfolio/township-110",
    "https://www.perfectpixels.com/core/portfolio/wild-tangent",
    "https://www.perfectpixels.com/core/portfolio/inner-agency",
    "https://www.perfectpixels.com/core/portfolio/all-recipes",
]

OUTPUT_DIR = "data/portfolio_images"
IMAGE_MAP_FILE = "data/portfolio_image_map.json"

def get_project_name(url):
    """Extract project name from URL"""
    return url.split("/")[-1]

def download_image(img_url, output_path):
    """Download a single image"""
    try:
        response = requests.get(img_url, timeout=10)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Error downloading {img_url}: {e}")
    return False

def scrape_portfolio_page(url):
    """Scrape images from a portfolio page"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch {url}: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        images = []
        
        # Find all img tags
        for img in soup.find_all('img'):
            img_url = img.get('src') or img.get('data-src')
            if img_url:
                # Convert relative URLs to absolute
                img_url = urljoin(url, img_url)
                
                # Skip small images (likely icons/logos)
                width = img.get('width')
                height = img.get('height')
                if width and height:
                    try:
                        if int(width) < 100 or int(height) < 100:
                            continue
                    except:
                        pass
                
                # Skip common non-content images
                if any(skip in img_url.lower() for skip in ['logo', 'icon', 'avatar', 'button']):
                    continue
                
                images.append({
                    'url': img_url,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
        
        return images
    
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

def main():
    """Main function to download all portfolio images"""
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    image_map = {}
    
    for page_url in PORTFOLIO_PAGES:
        project_name = get_project_name(page_url)
        print(f"\nProcessing {project_name}...")
        
        # Create project directory
        project_dir = os.path.join(OUTPUT_DIR, project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        # Scrape images
        images = scrape_portfolio_page(page_url)
        print(f"Found {len(images)} images")
        
        downloaded_images = []
        
        # Download each image
        for idx, img_info in enumerate(images):
            img_url = img_info['url']
            
            # Get file extension
            parsed = urlparse(img_url)
            ext = os.path.splitext(parsed.path)[1] or '.jpg'
            
            # Create filename
            filename = f"{project_name}_{idx+1}{ext}"
            output_path = os.path.join(project_dir, filename)
            
            print(f"  Downloading {filename}...")
            if download_image(img_url, output_path):
                downloaded_images.append({
                    'filename': filename,
                    'path': f"portfolio_images/{project_name}/{filename}",
                    'alt': img_info['alt'],
                    'title': img_info['title'],
                    'original_url': img_url
                })
            
            # Be nice to the server
            time.sleep(0.5)
        
        image_map[project_name] = {
            'project_url': page_url,
            'images': downloaded_images
        }
        
        print(f"Downloaded {len(downloaded_images)} images for {project_name}")
    
    # Save image map
    with open(IMAGE_MAP_FILE, 'w') as f:
        json.dump(image_map, f, indent=2)
    
    print(f"\n✓ Image map saved to {IMAGE_MAP_FILE}")
    print(f"✓ Total projects processed: {len(image_map)}")
    print(f"✓ Total images downloaded: {sum(len(p['images']) for p in image_map.values())}")

if __name__ == "__main__":
    main()

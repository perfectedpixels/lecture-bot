#!/usr/bin/env python3
"""
Update Portfolio Metadata with S3 URLs
"""

import json

def update_s3_urls(
    metadata_path: str = "data/portfolio_image_metadata.json",
    s3_bucket: str = "lecture-transcripts-427791004700",
    s3_prefix: str = ""  # Empty since path already includes portfolio_images
):
    """Update all S3 URLs in portfolio metadata"""
    
    print("Updating S3 URLs in portfolio metadata...")
    
    # Load metadata
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    updated_count = 0
    
    # Update each project's images
    for project_key, project_data in metadata.items():
        for img in project_data.get('images', []):
            # Build S3 URL
            path = img.get('path', '')
            if path:
                # Remove leading slash if present
                path = path.lstrip('/')
                
                # Build full S3 URL (path already includes portfolio_images/)
                if s3_prefix:
                    s3_url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_prefix}/{path}"
                else:
                    s3_url = f"https://{s3_bucket}.s3.amazonaws.com/{path}"
                
                img['s3_url'] = s3_url
                updated_count += 1
    
    # Save updated metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Updated {updated_count} image URLs")
    print(f"✓ Saved to {metadata_path}")
    
    # Print sample URLs
    print("\nSample URLs:")
    for project_key, project_data in list(metadata.items())[:2]:
        for img in project_data.get('images', [])[:2]:
            print(f"  {img['filename']}: {img['s3_url']}")


if __name__ == "__main__":
    update_s3_urls()

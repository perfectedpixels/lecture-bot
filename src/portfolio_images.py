"""
Portfolio Image Handler
Displays relevant portfolio images when bot discusses specific projects
"""

import json
import boto3
from typing import List, Dict, Optional
import re

class PortfolioImageHandler:
    def __init__(self, bucket_name: str = "lecture-transcripts-427791004700"):
        """
        Initialize portfolio image handler
        
        Args:
            bucket_name: S3 bucket containing portfolio images
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        self.image_map = self._load_image_map()
        
        # Project name mappings (handle variations in how projects might be mentioned)
        self.project_aliases = {
            'amazon': ['amazon', 'amazon.com', 'recommerce', 'trade-in', 'warehouse deals'],
            'aws': ['aws', 'amazon web services', 'emergent technologies'],
            'indeed': ['indeed'],
            'stanford-university': ['stanford', 'stanford university'],
            'microsoft': ['microsoft', 'msft', 'windows', 'azure', 'technet'],
            'trulia': ['trulia'],
            'classmates-com': ['classmates', 'classmates.com'],
            'virgin-travel-group': ['virgin', 'virgin travel', 'virgin travelstore'],
            'toyota': ['toyota', 'corolla'],
            'careoregon': ['careoregon', 'care oregon'],
            'washington-state-employment-security-department': ['washington state', 'esd', 'employment security'],
            'sealaska': ['sealaska'],
            'seattle-university': ['seattle university', 'matteo ricci'],
            'jewish-family-service': ['jewish family service', 'jfs'],
            'flutter': ['flutter', 'flutter.com'],
            'getty-images': ['getty', 'getty images'],
            'snap-village': ['snap village', 'snapvillage', 'corbis'],
            'township-110': ['township', 'township 110', 'township110'],
            'wild-tangent': ['wild tangent', 'wildtangent'],
            'inner-agency': ['inner agency'],
            'all-recipes': ['all recipes', 'allrecipes', 'allrecipes.com']
        }
    
    def _load_image_map(self) -> Dict:
        """Load image map from S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key='portfolio_image_map.json'
            )
            return json.loads(response['Body'].read())
        except Exception as e:
            print(f"Error loading image map: {e}")
            return {}
    
    def _detect_projects(self, text: str) -> List[str]:
        """
        Detect which projects are mentioned in the text
        
        Args:
            text: Text to analyze
            
        Returns:
            List of project keys mentioned
        """
        text_lower = text.lower()
        mentioned_projects = []
        
        for project_key, aliases in self.project_aliases.items():
            for alias in aliases:
                if alias in text_lower:
                    mentioned_projects.append(project_key)
                    break
        
        return list(set(mentioned_projects))  # Remove duplicates
    
    def get_project_images(self, project_key: str, max_images: int = 3) -> List[Dict]:
        """
        Get images for a specific project
        
        Args:
            project_key: Project identifier
            max_images: Maximum number of images to return
            
        Returns:
            List of image info dicts with S3 URLs
        """
        if project_key not in self.image_map:
            return []
        
        project_data = self.image_map[project_key]
        images = project_data.get('images', [])[:max_images]
        
        # Generate S3 URLs
        for img in images:
            img['s3_url'] = f"https://{self.bucket_name}.s3.amazonaws.com/{img['path']}"
        
        return images
    
    def get_images_for_response(self, response_text: str, max_images_per_project: int = 2) -> Dict[str, List[Dict]]:
        """
        Get relevant images based on bot response text
        
        Args:
            response_text: Bot's response text
            max_images_per_project: Max images to show per project
            
        Returns:
            Dict mapping project names to image lists
        """
        mentioned_projects = self._detect_projects(response_text)
        
        result = {}
        for project_key in mentioned_projects:
            images = self.get_project_images(project_key, max_images_per_project)
            if images:
                # Get display name from project key
                display_name = project_key.replace('-', ' ').title()
                result[display_name] = images
        
        return result
    
    def should_show_images(self, response_text: str) -> bool:
        """
        Determine if images should be shown for this response
        
        Args:
            response_text: Bot's response text
            
        Returns:
            True if images are relevant
        """
        # Show images if:
        # 1. A specific project is mentioned
        # 2. The response is discussing work examples or portfolio
        
        mentioned_projects = self._detect_projects(response_text)
        if mentioned_projects:
            return True
        
        # Check for portfolio-related keywords
        portfolio_keywords = [
            'project', 'work', 'designed', 'led', 'created', 'built',
            'example', 'experience at', 'worked on', 'portfolio'
        ]
        
        text_lower = response_text.lower()
        return any(keyword in text_lower for keyword in portfolio_keywords)

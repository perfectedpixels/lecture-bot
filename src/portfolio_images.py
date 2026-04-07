"""
Portfolio Image Handler
Displays relevant portfolio images when bot discusses specific projects.
Uses local filesystem instead of S3.
"""

import json
from typing import List, Dict, Optional
from pathlib import Path


class PortfolioImageHandler:
    def __init__(self, data_dir: str = None):
        """
        Initialize portfolio image handler with local filesystem.

        Args:
            data_dir: Path to data directory containing portfolio_image_map.json
                      and portfolio_images/
        """
        if data_dir is None:
            data_dir = str(Path(__file__).parent.parent / "data")
        self.data_dir = data_dir
        self.image_map = self._load_image_map()

        # Project name mappings
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
        """Load image map from local filesystem"""
        try:
            map_path = Path(self.data_dir) / "portfolio_image_map.json"
            with open(map_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading image map: {e}")
            return {}

    def _detect_projects(self, text: str) -> List[str]:
        """Detect which projects are mentioned in the text"""
        text_lower = text.lower()
        mentioned_projects = []

        for project_key, aliases in self.project_aliases.items():
            for alias in aliases:
                if alias in text_lower:
                    mentioned_projects.append(project_key)
                    break

        return list(set(mentioned_projects))

    def get_project_images(self, project_key: str, max_images: int = 3) -> List[Dict]:
        """
        Get images for a specific project.
        Returns local file paths instead of S3 URLs.
        """
        if project_key not in self.image_map:
            return []

        project_data = self.image_map[project_key]
        images = project_data.get('images', [])[:max_images]

        # Generate local paths
        for img in images:
            img['local_path'] = str(
                Path(self.data_dir) / "portfolio_images" / project_key / img.get('filename', img.get('path', '').split('/')[-1])
            )

        return images

    def get_images_for_response(self, response_text: str, max_images_per_project: int = 2) -> Dict[str, List[Dict]]:
        """Get relevant images based on bot response text"""
        mentioned_projects = self._detect_projects(response_text)

        result = {}
        for project_key in mentioned_projects:
            images = self.get_project_images(project_key, max_images_per_project)
            if images:
                display_name = project_key.replace('-', ' ').title()
                result[display_name] = images

        return result

    def should_show_images(self, response_text: str) -> bool:
        """Determine if images should be shown for this response"""
        mentioned_projects = self._detect_projects(response_text)
        if mentioned_projects:
            return True

        portfolio_keywords = [
            'project', 'work', 'designed', 'led', 'created', 'built',
            'example', 'experience at', 'worked on', 'portfolio'
        ]

        text_lower = response_text.lower()
        return any(keyword in text_lower for keyword in portfolio_keywords)

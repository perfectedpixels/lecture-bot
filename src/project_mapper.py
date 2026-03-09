"""
Project mapper - suggests relevant portfolio projects based on query keywords.
Ported from ppmg for use with lecture-bot and portfolio integration.
"""

from typing import List, Dict, Optional

# Portfolio project mapping with keywords (aligned with ppmg/portfolio/lib/content.ts)
PROJECTS = {
    "indeed": {
        "title": "Indeed",
        "keywords": [
            "job",
            "jobs",
            "career",
            "employment",
            "hiring",
            "resume",
            "profile",
            "job seeker",
            "recruitment",
            "qualified user",
            "experiment",
            "a/b test",
        ],
        "description": "Led UX redesign for 250M job seekers, increasing qualified users by 6.5%",
    },
    "careoregon": {
        "title": "CareOregon",
        "keywords": [
            "healthcare",
            "medical",
            "medicare",
            "medicaid",
            "health",
            "patient",
            "provider",
            "hipaa",
            "clinical",
            "accessibility",
        ],
        "description": "Redesigned Oregon's largest Medicare/Medicaid provider website with focus on accessibility",
    },
    "washington-state-employment-security-department": {
        "title": "Washington State ESD",
        "keywords": [
            "government",
            "state",
            "employment",
            "unemployment",
            "labor",
            "workforce",
            "bounce rate",
            "information architecture",
            "task completion",
        ],
        "description": "Reduced bounce rate from 70% to 30% through user-centered redesign",
    },
    "microsoft": {
        "title": "Microsoft",
        "keywords": [
            "microsoft",
            "msn",
            "enterprise",
            "windows",
            "responsive",
            "design system",
            "stakeholder",
            "content strategy",
        ],
        "description": "Reimagined MSN.com experience with modern responsive design system",
    },
    "amazon": {
        "title": "Amazon.com",
        "keywords": [
            "amazon",
            "ecommerce",
            "e-commerce",
            "recommerce",
            "trade-in",
            "marketplace",
            "gms",
            "global",
            "branding",
        ],
        "description": "Led UX for Amazon Recommerce Services totaling +$800M GMS",
    },
    "aws": {
        "title": "AWS Emergent Tech",
        "keywords": [
            "aws",
            "cloud",
            "automotive",
            "aerospace",
            "manufacturing",
            "iot",
            "digital twin",
            "twinmaker",
            "emergent",
        ],
        "description": "Head of UX for AWS Emergent Technologies across multiple industries",
    },
    "aws-healthcare-life-science": {
        "title": "AWS Healthcare / Life Science",
        "keywords": [
            "kariko",
            "mrna",
            "pulse",
            "hodgkin",
            "medical imaging",
            "patient monitoring",
            "life science",
            "healthcare ai",
            "clinical",
        ],
        "description": "Leading UX for Kariko (mRNA research), Pulse (patient monitoring), and Hodgkin (medical imaging AI)",
    },
    "american-express": {
        "title": "American Express",
        "keywords": [
            "amex",
            "american express",
            "financial",
            "credit card",
            "payment",
            "fintech",
            "banking",
        ],
        "description": "Created new products to excite young professionals for American Express",
    },
    "classmates-com": {
        "title": "Classmates.com",
        "keywords": [
            "social",
            "community",
            "nostalgia",
            "legacy brand",
            "42 million users",
            "social network",
        ],
        "description": "Rebranded legacy social platform for 42 million customers",
    },
    "stanford-university": {
        "title": "Stanford University",
        "keywords": [
            "university",
            "education",
            "academic",
            "professor",
            "appointment",
            "workflow",
            "process improvement",
        ],
        "description": "Simplified professorial appointment process with streamlined tool",
    },
    "all-recipes": {
        "title": "All Recipes",
        "keywords": [
            "recipe",
            "food",
            "cooking",
            "flash",
            "application",
            "game",
            "sponsored content",
            "monetization",
        ],
        "description": "Created Flash applications and games for sponsored content monetization",
    },
    "wild-tangent": {
        "title": "Wild Tangent",
        "keywords": [
            "gaming",
            "game",
            "casual game",
            "dynamic",
            "personalization",
            "user profile",
        ],
        "description": "Dynamic homepage with personalized views based on user profiles",
    },
}


def suggest_projects(
    query: str, max_suggestions: int = 2, exclude_slug: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Suggest relevant portfolio projects based on query keywords.
    Returns up to max_suggestions projects with highest relevance.
    Optionally exclude a project by slug (e.g. current page).
    """
    query_lower = query.lower()

    scores = []
    for slug, project in PROJECTS.items():
        score = 0
        matched_keywords = []

        for keyword in project["keywords"]:
            if keyword in query_lower:
                score += 1
                matched_keywords.append(keyword)

        if score > 0:
            scores.append(
                {
                    "slug": slug,
                    "title": project["title"],
                    "description": project["description"],
                    "score": score,
                    "matched_keywords": matched_keywords,
                }
            )

    scores.sort(key=lambda x: x["score"], reverse=True)
    relevant = [s for s in scores if s["score"] >= 1]

    if exclude_slug:
        exclude = exclude_slug.strip().lower()
        relevant = [s for s in relevant if s.get("slug", "").strip().lower() != exclude]

    return relevant[:max_suggestions]

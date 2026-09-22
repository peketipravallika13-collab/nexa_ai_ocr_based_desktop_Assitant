"""
Canva Design & Template Plugin for Nexa AI
------------------------------------------
Connects Nexa to Canva for generating design outlines, slide structures,
and launching Canva design editors with pre-filtered templates (presentations,
social media posts, posters, resumes, logos, and banners).
"""

import urllib.parse
import webbrowser
import logging

logger = logging.getLogger("canva_plugin")

PLUGIN_SCHEMA = {
    "name": "canva_designer",
    "description": "Create Canva designs, generate presentation/post outlines, or open Canva templates for presentations, social media, posters, resumes, logos, and infographics.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "design_type": {
                "type": "STRING",
                "description": "Type of design: 'presentation', 'instagram_post', 'poster', 'resume', 'logo', 'youtube_thumbnail', 'banner', 'infographic', or 'custom'."
            },
            "topic_or_query": {
                "type": "STRING",
                "description": "The topic, title, or keywords for the design (e.g. 'AI Technology Pitch Deck', 'Bakery Promo Post', 'Modern Minimalist Resume')."
            },
            "content_outline": {
                "type": "STRING",
                "description": "Optional generated text outline, slide bullet points, or captions to provide for the design."
            }
        },
        "required": ["design_type", "topic_or_query"]
    }
}

CANVA_URL_MAP = {
    "presentation": "https://www.canva.com/presentations/templates/?query=",
    "instagram_post": "https://www.canva.com/instagram-posts/templates/?query=",
    "poster": "https://www.canva.com/posters/templates/?query=",
    "resume": "https://www.canva.com/resumes/templates/?query=",
    "logo": "https://www.canva.com/logos/templates/?query=",
    "youtube_thumbnail": "https://www.canva.com/youtube-thumbnails/templates/?query=",
    "banner": "https://www.canva.com/banners/templates/?query=",
    "infographic": "https://www.canva.com/infographics/templates/?query=",
    "custom": "https://www.canva.com/templates/?query="
}

def run(design_type: str = "presentation", topic_or_query: str = "", content_outline: str = "") -> str:
    """Execute Canva design template generator and launcher."""
    design_type_clean = design_type.lower().strip().replace(" ", "_").replace("-", "_")
    base_url = CANVA_URL_MAP.get(design_type_clean, CANVA_URL_MAP["custom"])
    
    encoded_query = urllib.parse.quote(topic_or_query.strip())
    final_url = f"{base_url}{encoded_query}"
    
    try:
        webbrowser.open(final_url)
        
        outline_display = ""
        if content_outline:
            outline_display = f"\n\n📋 **Design & Content Blueprint:**\n{content_outline}"
            
        return (
            f"🎨 **Canva Project Initialized!**\n\n"
            f"- **Design Type:** {design_type.replace('_', ' ').title()}\n"
            f"- **Topic / Style:** {topic_or_query}\n"
            f"- **Canva Template Link:** [Open in Canva]({final_url}){outline_display}\n\n"
            f"🚀 *Opened Canva editor in your default browser.*"
        )
    except Exception as e:
        logger.error(f"Canva launch error: {e}")
        return f"Error launching Canva: {str(e)}"

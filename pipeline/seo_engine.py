#!/usr/bin/env python3
"""
SEO Engine for Aesop's Storyhouse Pipeline
Generates optimized YouTube + KDP metadata using keyword intelligence.
"""

import os
import sys
import json
import time
import re
import random
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from urllib.parse import quote_plus

# Fix Windows Unicode
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ===================================================================
# CONFIGURATION
# ===================================================================

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

CHANNEL_NAME = "Aesop's Storyhouse"
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@AesopsStoryhouse"
TIKTOK_URL = "https://www.tiktok.com/@aesopsstoryhouse"
INSTAGRAM_URL = "https://www.instagram.com/aesopsstoryhouse"

# Cache directory for keyword data
CACHE_DIR = Path("seo_cache")
CACHE_DIR.mkdir(exist_ok=True)

# ===================================================================
# 1. KEYWORD SCRAPERS
# ===================================================================

def scrape_youtube_autocomplete(seed: str, language: str = "en") -> List[str]:
    """Hit YouTube's autocomplete endpoint for real search suggestions."""
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "youtube", "ds": "yt", "q": seed, "hl": language}

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return []
        text = response.text
        start = text.index('[')
        data = json.loads(text[start:])
        if len(data) > 1 and isinstance(data[1], list):
            return [item[0] if isinstance(item, list) else str(item) for item in data[1]]
        return []
    except Exception as e:
        print(f"  [WARN] YouTube autocomplete failed for '{seed}': {e}")
        return []


def scrape_amazon_autocomplete(seed: str) -> List[str]:
    """Hit Amazon's autocomplete for book-related search suggestions."""
    url = "https://completion.amazon.com/api/2017/suggestions"
    params = {"mid": "ATVPDKIKX0DER", "alias": "stripbooks", "prefix": seed}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        return [s for s in (item.get("value", "") for item in data.get("suggestions", [])) if s]
    except Exception as e:
        print(f"  [WARN] Amazon autocomplete failed for '{seed}': {e}")
        return []


def expand_keyword_seeds(topic_info: Dict) -> List[str]:
    """Generate smart seed variations for a given topic."""
    keyword = topic_info['keyword']
    topic_type = topic_info['type']

    seeds = [
        f"learn {keyword} for kids", f"{keyword} for toddlers",
        f"{keyword} for preschoolers", f"teach {keyword} to kids",
        f"{keyword} educational video", f"{keyword} kids song",
        f"{keyword} baby learning", f"{keyword} for 2 year olds",
        f"{keyword} for 3 year olds",
    ]

    if topic_type == 'color':
        seeds.extend([f"learn {keyword} color", f"{keyword} color song",
                       f"{keyword} things for kids", f"learn colors for toddlers"])
    elif topic_type == 'number':
        seeds.extend(["counting for toddlers", "learn to count",
                       "numbers 1 to 10 for kids", "counting song for kids"])
    elif topic_type == 'shape':
        seeds.extend([f"learn {keyword} shape", "shapes for toddlers",
                       "learn shapes video"])
    elif topic_type == 'animal':
        seeds.extend([f"{keyword} sounds", f"{keyword} for babies",
                       "animal sounds for toddlers"])

    seeds.extend([f"{keyword} children's book", f"{keyword} board book toddler",
                   f"learn {keyword} book baby"])
    return seeds


def gather_keyword_intelligence(topic_info: Dict) -> Dict:
    """Main keyword intelligence function."""
    keyword = topic_info['keyword']
    cache_file = CACHE_DIR / f"keywords_{keyword}_{datetime.now().strftime('%Y%m%d')}.json"

    if cache_file.exists():
        print(f"  Loading cached keyword data for '{keyword}'")
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    print(f"\n  Gathering keyword intelligence for: {topic_info['topic']}")

    seeds = expand_keyword_seeds(topic_info)

    print(f"  Scraping YouTube autocomplete ({len(seeds)} seeds)...")
    yt_suggestions = set()
    for seed in seeds:
        results = scrape_youtube_autocomplete(seed)
        yt_suggestions.update(results)
        time.sleep(0.3)

    print(f"  Scraping Amazon autocomplete...")
    amz_suggestions = set()
    for seed in [s for s in seeds if 'book' in s or 'learn' in s][:8]:
        results = scrape_amazon_autocomplete(seed)
        amz_suggestions.update(results)
        time.sleep(0.3)

    all_keywords = sorted(yt_suggestions | amz_suggestions)
    topic_words = set(keyword.lower().split() + topic_info['topic'].lower().split())
    relevant_keywords = [
        kw for kw in all_keywords
        if any(tw in kw.lower() for tw in topic_words)
        or any(term in kw.lower() for term in ['kids', 'toddler', 'baby', 'learn', 'preschool'])
    ]

    result = {
        "topic": topic_info['topic'], "keyword": keyword,
        "youtube_suggestions": sorted(yt_suggestions),
        "amazon_suggestions": sorted(amz_suggestions),
        "relevant_keywords": relevant_keywords,
        "total_unique": len(all_keywords),
        "scraped_at": datetime.now().isoformat(),
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"  [OK] {len(yt_suggestions)} YouTube + {len(amz_suggestions)} Amazon suggestions")
    return result


# ===================================================================
# 2. SEO METADATA GENERATOR
# ===================================================================

def generate_optimized_metadata(topic_info, keyword_data, competitors=None, kid_order=None):
    """Use Claude to generate SEO-optimized metadata."""
    if not ANTHROPIC_API_KEY:
        return _fallback_metadata(topic_info, kid_order)

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    keyword = topic_info['keyword']
    topic = topic_info['topic']
    kids_str = ', '.join(kid_order) if kid_order else 'Liam, Noah, Oliver, Emma'

    yt_keywords = keyword_data.get('youtube_suggestions', [])[:20]
    amz_keywords = keyword_data.get('amazon_suggestions', [])[:15]

    prompt = f"""You are an expert YouTube SEO specialist for children's educational content (ages 2-5).

CHANNEL: {CHANNEL_NAME}
TOPIC: {topic}
KEYWORD: {keyword}
CHARACTERS: {kids_str} (real children, ages 5, 3, 2, and 7 months)

REAL YOUTUBE SEARCH DATA:
{chr(10).join(f'  - {kw}' for kw in yt_keywords)}

REAL AMAZON SEARCH DATA:
{chr(10).join(f'  - {kw}' for kw in amz_keywords)}

Generate ALL of the following as valid JSON:

{{
  "youtube_titles": ["3 title options under 60 chars each"],
  "youtube_description": "Full description with keyword blocks",
  "youtube_tags": ["25-30 tags"],
  "youtube_shorts_titles": {{"Liam": "...", "Noah": "...", "Oliver": "...", "Emma": "..."}},
  "hashtags": ["3-5 hashtags"],
  "kdp_keywords": ["7 Amazon KDP keyword phrases"],
  "kdp_title": "Book title with subtitle",
  "kdp_description": "150-200 word Amazon description"
}}

Return ONLY valid JSON, no code blocks."""

    try:
        print("  Generating optimized SEO metadata...")
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
            response_text = re.sub(r'\n?```\s*$', '', response_text)

        metadata = json.loads(response_text)

        # Inject social links
        if 'youtube_description' in metadata:
            social_block = (
                f"Subscribe for more magical learning adventures!\n"
                f"{YOUTUBE_CHANNEL_URL}\n"
                f"TikTok: {TIKTOK_URL}\n"
                f"Instagram: {INSTAGRAM_URL}"
            )
            if YOUTUBE_CHANNEL_URL not in metadata['youtube_description']:
                metadata['youtube_description'] += f"\n\n{social_block}"

        print(f"  [OK] SEO metadata generated")
        return metadata
    except Exception as e:
        print(f"  [WARN] SEO metadata generation failed: {e}")
        return _fallback_metadata(topic_info, kid_order)


def _fallback_metadata(topic_info, kid_order=None):
    """Fallback metadata if Claude fails."""
    keyword = topic_info['keyword']
    topic = topic_info['topic']
    kids = kid_order or ['Liam', 'Noah', 'Oliver', 'Emma']

    return {
        "youtube_titles": [
            f"Learn {topic} with {kids[0]} & Friends! Educational Video for Toddlers",
            f"Can You Find {keyword.title()}? {topic} for Kids Ages 2-5",
            f"{topic} Fun Learning for Toddlers | {CHANNEL_NAME}",
        ],
        "youtube_description": (
            f"Join {', '.join(kids[:3])}, and baby {kids[3]} as they learn about {keyword}! "
            f"This fun educational video teaches toddlers about {topic.lower()}.\n\n"
            f"Subscribe: {YOUTUBE_CHANNEL_URL}"
        ),
        "youtube_tags": [
            "educational video for kids", "learning for toddlers", "preschool learning",
            f"learn {keyword}", f"{keyword} for kids", f"{keyword} for toddlers",
            "toddler learning video", "aesops storyhouse",
        ],
        "youtube_shorts_titles": {kid: f"{kid} Learns {topic}!" for kid in kids},
        "hashtags": ["#ToddlerLearning", "#KidsEducation", "#PreschoolFun"],
        "kdp_keywords": [
            f"learn {keyword} toddler board book",
            f"{keyword} children's book ages 2-5",
            f"educational picture book {keyword}",
        ],
        "kdp_title": f"{topic}: A Fun Learning Book for Toddlers | {CHANNEL_NAME}",
        "kdp_description": f"Join {', '.join(kids[:3])}, and baby {kids[3]} learning about {keyword}!",
    }


def generate_spanish_seo(metadata_en, topic_info):
    """Generate Spanish SEO metadata."""
    keyword = topic_info['keyword']

    es_suggestions = set()
    for seed in [f"aprender {keyword} para ninos", f"video educativo para ninos"][:2]:
        results = scrape_youtube_autocomplete(seed, language="es")
        es_suggestions.update(results)
        time.sleep(0.3)

    if not ANTHROPIC_API_KEY:
        return {}

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Translate and adapt this YouTube metadata to neutral Latin American Spanish.

ENGLISH METADATA:
Title: {metadata_en['youtube_titles'][0]}
Tags: {', '.join(metadata_en['youtube_tags'][:15])}

Return JSON with:
{{
  "youtube_title_es": "...",
  "youtube_description_es": "...",
  "youtube_tags_es": ["..."],
  "shorts_titles_es": {{"Liam": "...", "Noah": "...", "Oliver": "...", "Emma": "..."}}
}}

Return ONLY valid JSON."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
            response_text = re.sub(r'\n?```\s*$', '', response_text)
        return json.loads(response_text)
    except Exception as e:
        print(f"  [WARN] Spanish SEO generation failed: {e}")
        return {}


# ===================================================================
# MAIN INTEGRATION FUNCTION
# ===================================================================

def run_seo_pipeline(topic_info, kid_order, youtube_service=None):
    """ONE CALL to run the full SEO pipeline."""
    print("\n" + "=" * 70)
    print("SEO ENGINE: Generating optimized metadata")
    print("=" * 70)

    keyword_data = gather_keyword_intelligence(topic_info)
    metadata_en = generate_optimized_metadata(topic_info, keyword_data, None, kid_order)
    metadata_es = generate_spanish_seo(metadata_en, topic_info)

    output = {
        "keyword_data": keyword_data,
        "competitors": [],
        "metadata_en": metadata_en,
        "metadata_es": metadata_es,
        "generated_at": datetime.now().isoformat(),
    }

    cache_file = CACHE_DIR / f"seo_output_{topic_info['keyword']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n[OK] SEO metadata saved: {cache_file}")
    return output


if __name__ == "__main__":
    test_topic = {"type": "color", "topic": "The Color Red", "keyword": "red", "emoji": "red_circle"}
    result = run_seo_pipeline(test_topic, ["Liam", "Noah", "Oliver", "Emma"])
    meta = result['metadata_en']
    print(f"\nTitles:")
    for i, t in enumerate(meta.get('youtube_titles', []), 1):
        print(f"  {i}. {t}")

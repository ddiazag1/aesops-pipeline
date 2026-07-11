#!/usr/bin/env python3
"""
Bilingual Educational Pipeline for Aesop's Storyhouse
EN + ES combined videos -- Spanish portions use horizontal flip as visual cue
Output: 1 bilingual video + 4 bilingual Shorts + KDP books (EN & ES separate)

Adapted for CI (GitHub Actions) and local use.
"""

import anthropic
import argparse
import os
import sys
import json
import time
import random
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for emoji output
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

KREA_API_KEY = os.getenv('KREA_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# TTS voices (edge-tts)
ENGLISH_VOICE = "en-US-AnaNeural"
SPANISH_VOICE = "es-MX-DaliaNeural"

# Video settings
SCENE_DURATION = 6   # seconds per scene clip
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
VIDEO_FPS = 24

# Kids configuration with LoRA IDs
KIDS = {
    "liam": {
        "name": "Liam",
        "age": "5 years",
        "lora_id": "u42zoi7l0",
        "trigger": "ra",
        "full_desc": "5-year-old boy named Liam wearing a bright blue t-shirt and dark pants with a short buzz cut hairstyle and friendly smile",
        "scenes": 4
    },
    "noah": {
        "name": "Noah",
        "age": "3 years",
        "lora_id": "rxud3si1o",
        "trigger": "wa",
        "full_desc": "3-year-old boy named Noah wearing a red t-shirt and blue jeans with shaggy brown hair and cheerful expression",
        "scenes": 3
    },
    "oliver": {
        "name": "Oliver",
        "age": "2 years",
        "lora_id": "ajvuyorfj",
        "trigger": "ja",
        "full_desc": "2-year-old boy named Oliver wearing a green t-shirt and shorts with a spiky mohawk hairstyle and playful grin",
        "scenes": 4
    },
    "emma": {
        "name": "Emma",
        "age": "7 months",
        "lora_id": "ozjcynyyb",
        "trigger": "ea",
        "full_desc": "baby girl named Emma wearing pink clothes and a pink knit beanie hat with a sweet gentle smile",
        "scenes": 3
    }
}

# Educational topics to cycle through
EDUCATIONAL_TOPICS = [
    # Colors
    {"type": "color", "topic": "Red Color", "keyword": "red", "emoji": "red_circle"},
    {"type": "color", "topic": "Blue Color", "keyword": "blue", "emoji": "blue_circle"},
    {"type": "color", "topic": "Yellow Color", "keyword": "yellow", "emoji": "yellow_circle"},
    {"type": "color", "topic": "Green Color", "keyword": "green", "emoji": "green_circle"},
    {"type": "color", "topic": "Orange Color", "keyword": "orange", "emoji": "orange_circle"},
    {"type": "color", "topic": "Purple Color", "keyword": "purple", "emoji": "purple_circle"},
    # Numbers
    {"type": "number", "topic": "Counting to 5", "keyword": "numbers 1-5", "emoji": "1234"},
    {"type": "number", "topic": "Counting to 10", "keyword": "numbers 1-10", "emoji": "1234"},
    # Shapes
    {"type": "shape", "topic": "Circles", "keyword": "circle", "emoji": "o"},
    {"type": "shape", "topic": "Squares", "keyword": "square", "emoji": "blue_square"},
    {"type": "shape", "topic": "Triangles", "keyword": "triangle", "emoji": "small_red_triangle"},
    {"type": "shape", "topic": "Stars", "keyword": "star", "emoji": "star"},
    # Sizes
    {"type": "size", "topic": "Big and Small", "keyword": "big small", "emoji": "straight_ruler"},
    # Animals
    {"type": "animal", "topic": "Farm Animals", "keyword": "farm animals", "emoji": "cow"},
    {"type": "animal", "topic": "Wild Animals", "keyword": "wild animals", "emoji": "lion"},
    # Opposites
    {"type": "opposite", "topic": "Up and Down", "keyword": "up down", "emoji": "arrow_up_down"},
    {"type": "opposite", "topic": "Hot and Cold", "keyword": "hot cold", "emoji": "thermometer"},
]

# Running in CI?
CI_MODE = os.getenv('CI', '').lower() == 'true' or os.getenv('GITHUB_ACTIONS', '').lower() == 'true'

# ===================================================================
# STEP 1: GENERATE EDUCATIONAL TOPIC
# ===================================================================

def generate_educational_content(topic_info):
    """Generate educational content with rotation through all 4 kids"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Generate a simple educational video script for toddlers ages 2-5.

TOPIC: Learn {topic_info['topic']}

FORMAT: 15 scenes total, kids take turns:
- Liam (5 years): Scenes 1-4
- Noah (3 years): Scenes 5-7
- Oliver (2 years): Scenes 8-11
- Emma (7 months baby): Scenes 12-14
- All four together: Scene 15 (celebration)

RULES:
- Each scene = ONE kid + ONE simple object
- Objects must be related to topic: {topic_info['keyword']}
- White/simple background
- No complex actions, just showing/holding objects
- Each scene text should be: "[Kid name] [verb] [object]!"
  Examples: "Liam finds red apple!", "Noah sees blue ball!"

OUTPUT JSON:
{{
  "title": "Learn [Topic] with Liam, Noah, Oliver & Emma!",
  "topic": "{topic_info['topic']}",
  "emoji": "{topic_info['emoji']}",
  "scenes": [
    {{"kid": "liam", "object": "...", "description": "Liam finds/sees/holds [object]!"}},
    ... 15 total scenes ...
  ],
  "celebration": "All four kids celebrate learning {topic_info['topic']}!"
}}

Make it SIMPLE. Each scene = kid + object. That's it."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text

    # Extract JSON
    if "```json" in response_text:
        json_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_text = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_text = response_text.strip()

    content = json.loads(json_text)

    print(f"\n[OK] Generated educational content: {content['title']}")
    print(f"  Topic: {content['topic']}")
    print(f"  Scenes: {len(content['scenes'])}")

    return content

# ===================================================================
# STEP 2: CREATE KREA PROMPTS (SIMPLE)
# ===================================================================

def create_krea_prompts(content):
    """Create simple Krea prompts: one kid + one object + white background"""

    prompts = []

    for i, scene in enumerate(content['scenes'], start=1):
        kid_name = scene['kid']
        obj = scene['object']

        # Handle scene 15 (all kids together) - special case
        if kid_name == 'all':
            all_descs = ", ".join([KIDS[k]['full_desc'] for k in ['liam', 'noah', 'oliver', 'emma']])
            all_triggers = " ".join([KIDS[k]['trigger'] for k in ['liam', 'noah', 'oliver', 'emma']])
            all_together_prompt = f"{all_triggers} {all_descs}, four kids together celebrating, {content['topic'].lower()} theme, colorful background, bright happy, animated illustration style, cartoon children's book art, simple clean, digital art"
            prompts.append({
                "scene_number": i,
                "kid": "all",
                "object": obj,
                "prompt": all_together_prompt,
                "lora_ids": [KIDS[k]['lora_id'] for k in ['liam', 'noah', 'oliver', 'emma']]
            })
            continue

        # Regular kid scene
        kid_info = KIDS[kid_name]

        # Prompt uses full character description from LoRA training
        prompt = f"{kid_info['trigger']} {kid_info['full_desc']}, with {obj}, white background, bright colorful, animated illustration style, cartoon children's book art, simple clean, centered, digital art"

        prompts.append({
            "scene_number": i,
            "kid": kid_name,
            "object": obj,
            "prompt": prompt,
            "lora_id": kid_info['lora_id']
        })

    print(f"\n[OK] Created {len(prompts)} Krea prompts")

    return prompts

# ===================================================================
# STEP 3: GENERATE IMAGES WITH KREA
# ===================================================================

def generate_krea_image(prompt_info):
    """Generate single image with Krea API"""
    import requests

    # Prepare LoRAs
    if "lora_ids" in prompt_info:  # All together scene
        loras = [{"id": lora_id, "strength": 0.85} for lora_id in prompt_info['lora_ids']]
    else:  # Single kid
        loras = [{"id": prompt_info['lora_id'], "strength": 0.85}]

    payload = {
        "prompt": prompt_info['prompt'],
        "width": 1024,
        "height": 1024,
        "steps": 28,
        "styles": loras
    }

    headers = {
        "Authorization": f"Bearer {KREA_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"  Generating scene {prompt_info['scene_number']} ({prompt_info['kid']})...")

    response = requests.post(
        "https://api.krea.ai/generate/image/bfl/flux-1-dev",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        job_id = response.json()["job_id"]
        print(f"    Job: {job_id}")

        # Poll for completion
        for attempt in range(60):  # Up to 2 minutes
            time.sleep(2)

            poll_response = requests.get(
                f"https://api.krea.ai/jobs/{job_id}",
                headers={"Authorization": f"Bearer {KREA_API_KEY}"}
            )

            if poll_response.status_code != 200:
                continue

            job_data = poll_response.json()
            status = job_data.get("status")

            if status == "completed":
                result = job_data.get("result", {})

                # Handle urls array or single url
                if "urls" in result and isinstance(result["urls"], list) and len(result["urls"]) > 0:
                    image_url = result["urls"][0]
                elif "url" in result:
                    image_url = result["url"]
                else:
                    print(f"    [ERROR] No URL in response")
                    return None

                # Download image
                img_response = requests.get(image_url)
                print(f"    [OK] Downloaded")
                return img_response.content
            elif status == "failed":
                print(f"    [ERROR] Job failed")
                return None

        print(f"    [ERROR] Timeout waiting for image")
        return None
    else:
        print(f"[ERROR] Krea API failed: {response.status_code}")
        if response.text:
            print(f"    Response: {response.text[:200]}")
        return None

def generate_all_images(prompts, output_folder):
    """Generate all 15 images"""

    print("\n" + "="*70)
    print("STEP 3: GENERATING IMAGES WITH KREA")
    print("="*70)

    image_folder = output_folder / "images"
    image_folder.mkdir(exist_ok=True)

    generated_count = 0
    for prompt_info in prompts:
        image_data = generate_krea_image(prompt_info)

        if image_data:
            image_path = image_folder / f"scene_{prompt_info['scene_number']:02d}.jpg"
            with open(image_path, 'wb') as f:
                f.write(image_data)
            print(f"    [OK] Saved: {image_path.name}")
            generated_count += 1

        time.sleep(2)  # Rate limit

    if generated_count == 0:
        raise RuntimeError("Krea API failed to generate ANY images. Check your Krea API balance and key.")

    print(f"\n[OK] Generated {generated_count}/{len(prompts)} images")
    return image_folder

# ===================================================================
# STEP 3B: ANIMATE IMAGES (HAILUO PRIMARY, KEN BURNS FALLBACK)
# ===================================================================

def upload_image_to_krea(image_path):
    """Upload image to Krea assets to get a URL for animation"""
    import requests
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (image_path.name, f, 'image/png')}
            response = requests.post(
                "https://api.krea.ai/assets",
                headers={"Authorization": f"Bearer {KREA_API_KEY}"},
                files=files, data={'description': 'Scene image'}
            )
        if response.status_code != 200:
            return None
        return response.json().get("image_url")
    except Exception:
        return None


def animate_image_hailuo(image_url, movement_prompt):
    """Animate image using Krea Hailuo video API. Returns video URL or None."""
    import requests
    response = requests.post(
        "https://api.krea.ai/generate/video/minimax/hailuo-2.3",
        headers={
            "Authorization": f"Bearer {KREA_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "prompt": movement_prompt,
            "start_image": image_url,
            "duration": SCENE_DURATION,
            "resolution": "768p",
            "expand_prompt": False
        }
    )
    if response.status_code != 200:
        print(f"    [WARN] Hailuo API: {response.status_code}")
        return None

    job_id = response.json()["job_id"]
    print(f"      Job: {job_id}")

    for attempt in range(180):
        time.sleep(2)
        poll = requests.get(
            f"https://api.krea.ai/jobs/{job_id}",
            headers={"Authorization": f"Bearer {KREA_API_KEY}"}
        )
        if poll.status_code != 200:
            continue
        job_data = poll.json()
        status = job_data.get("status")
        if status == "completed":
            result = job_data.get("result", {})
            if "urls" in result and result["urls"]:
                return result["urls"][0]
            elif "url" in result:
                return result["url"]
            return None
        elif status == "failed":
            return None
        if attempt % 30 == 0 and attempt > 0:
            print(f"      Still animating... ({attempt * 2}s)")
    return None


# Ken Burns fallback patterns
KENBURNS_PATTERNS = [
    "scale=8000:8000,zoompan=z='min(zoom+0.0015,1.4)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={dur}:s={w}x{h}:fps={fps}",
    "scale=8000:8000,zoompan=z='if(eq(on,1),1.4,max(zoom-0.0015,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={dur}:s={w}x{h}:fps={fps}",
    "scale=8000:8000,zoompan=z='1.3':x='if(eq(on,1),0,min(x+2,iw-iw/zoom))':y='ih/2-(ih/zoom/2)':d={dur}:s={w}x{h}:fps={fps}",
    "scale=8000:8000,zoompan=z='1.3':x='if(eq(on,1),iw-iw/zoom,max(x-2,0))':y='ih/2-(ih/zoom/2)':d={dur}:s={w}x{h}:fps={fps}",
    "scale=8000:8000,zoompan=z='min(zoom+0.0015,1.4)':x='iw/4-(iw/zoom/2)':y='ih/4-(ih/zoom/2)':d={dur}:s={w}x{h}:fps={fps}",
    "scale=8000:8000,zoompan=z='min(zoom+0.0015,1.4)':x='3*iw/4-(iw/zoom/2)':y='3*ih/4-(ih/zoom/2)':d={dur}:s={w}x{h}:fps={fps}",
]


def kenburns_fallback(image_path, video_out, scene_num):
    """Apply Ken Burns zoom/pan effect as fallback animation."""
    pattern = KENBURNS_PATTERNS[scene_num % len(KENBURNS_PATTERNS)]
    dur_frames = SCENE_DURATION * VIDEO_FPS
    vf = pattern.format(dur=dur_frames, w=VIDEO_WIDTH, h=VIDEO_HEIGHT, fps=VIDEO_FPS)
    result = subprocess.run([
        'ffmpeg', '-y', '-i', str(image_path),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-pix_fmt', 'yuv420p', str(video_out)
    ], capture_output=True, text=True)
    return result.returncode == 0


def animate_all_scenes(prompts, image_folder, output_folder):
    """Animate scenes: try Hailuo first, fall back to Ken Burns if unavailable."""
    import requests

    print("\n" + "="*70)
    print("STEP 3B: ANIMATING IMAGES")
    print("="*70)

    # Test if Hailuo is available with a quick probe
    use_hailuo = True
    try:
        probe = requests.post(
            "https://api.krea.ai/generate/video/minimax/hailuo-2.3",
            headers={"Authorization": f"Bearer {KREA_API_KEY}", "Content-Type": "application/json"},
            json={"prompt": "test", "start_image": "https://example.com/test.png", "duration": 1}
        )
        if probe.status_code == 402:
            use_hailuo = False
            print("  Hailuo API unavailable (billing), using Ken Burns fallback")
    except Exception:
        use_hailuo = False

    if use_hailuo:
        print("  Using Krea Hailuo for animation")
    else:
        print("  Using ffmpeg Ken Burns for animation")

    animated = 0
    for prompt_info in prompts:
        scene_num = prompt_info['scene_number']
        image_path = image_folder / f"scene_{scene_num:02d}.jpg"
        if not image_path.exists():
            image_path = image_folder / f"scene_{scene_num:02d}.png"
        if not image_path.exists():
            print(f"  Scene {scene_num:02d}: no image, skipping")
            continue

        video_out = output_folder / f"scene_{scene_num:02d}.mp4"
        if video_out.exists():
            print(f"  Scene {scene_num:02d}: already exists, skipping")
            animated += 1
            continue

        if use_hailuo:
            # Upload image to get Krea-hosted URL
            print(f"  Scene {scene_num:02d} ({prompt_info['kid']}): uploading...")
            image_url = upload_image_to_krea(image_path)
            if not image_url:
                print(f"    [WARN] Upload failed, using Ken Burns")
                if kenburns_fallback(image_path, video_out, scene_num):
                    animated += 1
                    print(f"    [OK] Ken Burns applied")
                continue

            movement = prompt_info.get('object', 'gentle subtle movement')
            print(f"  Scene {scene_num:02d}: animating with Hailuo...")
            video_url = animate_image_hailuo(image_url, movement)
            if video_url:
                vid_response = requests.get(video_url)
                if vid_response.status_code == 200:
                    with open(video_out, 'wb') as f:
                        f.write(vid_response.content)
                    animated += 1
                    print(f"    [OK] Hailuo video saved")
                    time.sleep(2)
                    continue

            # Hailuo failed for this scene, Ken Burns fallback
            print(f"    [WARN] Hailuo failed, using Ken Burns")
            if kenburns_fallback(image_path, video_out, scene_num):
                animated += 1
                print(f"    [OK] Ken Burns applied")
        else:
            # Ken Burns only
            if kenburns_fallback(image_path, video_out, scene_num):
                animated += 1
                print(f"  Scene {scene_num:02d}: [OK] Ken Burns applied")
            else:
                print(f"  Scene {scene_num:02d}: [ERROR] Ken Burns failed")

    print(f"\n[OK] Animated {animated}/{len(prompts)} scenes")


# ===================================================================
# STEP 4: TRANSLATE TO SPANISH
# ===================================================================

def translate_to_spanish(content):
    """Translate educational content to Spanish using Claude"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Translate this children's educational video content to neutral Latin American Spanish.

ENGLISH CONTENT:
{json.dumps(content, indent=2, ensure_ascii=False)}

RULES:
- Use neutral Latin American Spanish (Mexico/Colombia style)
- Keep kid names unchanged (Liam, Noah, Oliver, Emma)
- Keep it simple and child-friendly (ages 2-5)
- Translate title, topic, all scene descriptions, and celebration text
- Keep "kid" field values unchanged (liam, noah, oliver, emma, all)
- Translate "object" field to Spanish

Return ONLY valid JSON with the same structure:
{{
    "title": "Spanish title",
    "topic": "Spanish topic",
    "emoji": "{content.get('emoji', '')}",
    "language": "ES",
    "scenes": [
        {{"kid": "liam", "object": "Spanish object", "description": "Spanish description!"}},
        ... all {len(content.get('scenes', []))} scenes ...
    ],
    "celebration": "Spanish celebration text!"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text
    if "```json" in response_text:
        json_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_text = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_text = response_text.strip()

    content_es = json.loads(json_text)
    content_es["language"] = "ES"

    print(f"\n[OK] Translated to Spanish: {content_es['title']}")
    return content_es

# ===================================================================
# STEP 5: GENERATE PER-SCENE TTS AUDIO
# ===================================================================

async def _generate_all_tts(texts_and_paths, voice):
    """Generate TTS for all scenes in one async batch"""
    import edge_tts
    for text, path in texts_and_paths:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(path))


def generate_all_scene_audio(content, output_folder, lang="en"):
    """Generate per-scene TTS audio files"""
    voice = ENGLISH_VOICE if lang == "en" else SPANISH_VOICE
    audio_folder = output_folder / f"audio_{lang}"
    audio_folder.mkdir(exist_ok=True)

    texts_and_paths = []
    for i, scene in enumerate(content['scenes'], start=1):
        kid_key = scene.get('kid', '')
        kid_name = KIDS.get(kid_key, {}).get('name', kid_key.capitalize())
        desc = scene.get('description', f'Scene {i}')

        if kid_key == 'all':
            if lang == "en":
                text = f"Everyone together! {desc}"
            else:
                text = f"Todos juntos! {desc}"
        elif lang == "en":
            text = f"{kid_name}'s turn! {desc}"
        else:
            text = f"Turno de {kid_name}! {desc}"

        audio_path = audio_folder / f"scene_{i:02d}.mp3"
        texts_and_paths.append((text, audio_path))

    # Windows asyncio fix
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(_generate_all_tts(texts_and_paths, voice))

    for i, (_, path) in enumerate(texts_and_paths, start=1):
        print(f"    [OK] {lang.upper()} scene {i:02d}: {path.name}")

    # Save full script text for reference
    script_lines = [t for t, _ in texts_and_paths]
    with open(output_folder / f"voiceover_script_{lang}.txt", 'w', encoding='utf-8') as f:
        f.write("\n".join(script_lines))

    return audio_folder

# ===================================================================
# STEP 6: CREATE SHORTS CONFIG
# ===================================================================

def create_shorts_config(content):
    """Create 4 Shorts - one featuring each kid's section (bilingual)"""

    shorts = []

    shorts.append({
        "kid": "Liam",
        "title": f"Liam Learns {content['topic']}! {content['emoji']}",
        "scenes": [1, 2, 3, 4],
        "duration_bilingual": 48
    })

    shorts.append({
        "kid": "Noah",
        "title": f"Noah Learns {content['topic']}! {content['emoji']}",
        "scenes": [5, 6, 7],
        "duration_bilingual": 36
    })

    shorts.append({
        "kid": "Oliver",
        "title": f"Oliver Learns {content['topic']}! {content['emoji']}",
        "scenes": [8, 9, 10, 11],
        "duration_bilingual": 48
    })

    shorts.append({
        "kid": "Emma",
        "title": f"Emma Sees {content['topic']}! {content['emoji']}",
        "scenes": [12, 13, 14],
        "duration_bilingual": 36
    })

    print(f"\n[OK] Created 4 bilingual Shorts config")

    return shorts

# ===================================================================
# STEP 7: CREATE SCENE VIDEOS FROM IMAGES
# ===================================================================

def ensure_scene_videos(image_folder, output_folder, num_scenes=15):
    """Create 1920x1080 scene videos from images (or use existing animated ones)"""
    video_folder = output_folder / "scene_videos"
    video_folder.mkdir(exist_ok=True)

    vf = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
        f":force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:white"
    )

    for i in range(1, num_scenes + 1):
        video_out = video_folder / f"scene_{i:02d}.mp4"

        # Check if animated version already exists in output folder
        animated = output_folder / f"scene_{i:02d}.mp4"
        if animated.exists():
            subprocess.run([
                'ffmpeg', '-y',
                '-i', str(animated),
                '-t', str(SCENE_DURATION),
                '-vf', vf,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-r', str(VIDEO_FPS),
                '-an', str(video_out)
            ], check=True, capture_output=True)
            print(f"    [OK] Scene {i:02d}: re-encoded animated video")
            continue

        # Create from static image
        image = image_folder / f"scene_{i:02d}.jpg"
        if not image.exists():
            image = image_folder / f"scene_{i:02d}.png"

        if not image.exists():
            print(f"    [WARN] Scene {i:02d}: no image found, skipping")
            continue

        subprocess.run([
            'ffmpeg', '-y',
            '-loop', '1', '-i', str(image),
            '-t', str(SCENE_DURATION),
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-pix_fmt', 'yuv420p', '-r', str(VIDEO_FPS),
            str(video_out)
        ], check=True, capture_output=True)
        print(f"    [OK] Scene {i:02d}: created from image")

    return video_folder

# ===================================================================
# FFMPEG HELPERS
# ===================================================================

def _ffmpeg_encode_clip(video_in, audio_in, video_out, vfilters=None):
    """Encode a scene clip with optional video filter and audio"""
    cmd = ['ffmpeg', '-y']

    # Video input (handle static images)
    is_image = str(video_in).lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    if is_image:
        cmd += ['-loop', '1']
    cmd += ['-i', str(video_in)]

    # Audio input (real file or silence)
    if audio_in and Path(str(audio_in)).exists():
        cmd += ['-i', str(audio_in)]
    else:
        cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo']

    # Video filter
    if vfilters:
        cmd += ['-vf', vfilters]

    cmd += [
        '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2',
        '-t', str(SCENE_DURATION),
        '-pix_fmt', 'yuv420p', '-r', str(VIDEO_FPS),
        str(video_out)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg encode failed: {result.stderr[:500]}")


def _ffmpeg_concat(clip_paths, output_path):
    """Concatenate clips using ffmpeg concat demuxer"""
    concat_file = output_path.parent / f"concat_{output_path.stem}.txt"
    with open(concat_file, 'w') as f:
        for p in clip_paths:
            # Use forward-slash paths for cross-platform ffmpeg compatibility
            f.write(f"file '{p.resolve().as_posix()}'\n")

    result = subprocess.run([
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        str(output_path)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr[:500]}")

# ===================================================================
# STEP 8: ASSEMBLE BILINGUAL MAIN VIDEO
# ===================================================================

def assemble_bilingual_video(scene_video_folder, en_audio_folder, es_audio_folder,
                             output_folder, num_scenes=15):
    """Assemble bilingual video: EN scene -> hflipped ES scene, all 15 scenes"""

    clips_folder = output_folder / "bilingual_clips"
    clips_folder.mkdir(exist_ok=True)

    clip_paths = []

    for i in range(1, num_scenes + 1):
        scene_video = scene_video_folder / f"scene_{i:02d}.mp4"
        en_audio = en_audio_folder / f"scene_{i:02d}.mp3"
        es_audio = es_audio_folder / f"scene_{i:02d}.mp3"

        if not scene_video.exists():
            print(f"    [WARN] Scene {i:02d}: no video, skipping")
            continue

        # EN clip: original video + English audio
        en_clip = clips_folder / f"scene_{i:02d}_en.mp4"
        _ffmpeg_encode_clip(scene_video, en_audio, en_clip)
        clip_paths.append(en_clip)

        # ES clip: hflipped video + Spanish audio
        es_clip = clips_folder / f"scene_{i:02d}_es.mp4"
        _ffmpeg_encode_clip(scene_video, es_audio, es_clip, vfilters='hflip')
        clip_paths.append(es_clip)

        print(f"    [OK] Scene {i:02d}: EN + ES (hflipped)")

    # Concat all clips into final bilingual video
    final_video = output_folder / "final_bilingual.mp4"
    _ffmpeg_concat(clip_paths, final_video)

    total_duration = num_scenes * SCENE_DURATION * 2
    print(f"\n[OK] Bilingual video: {final_video.name} (~{total_duration}s)")
    return final_video

# ===================================================================
# STEP 9: ASSEMBLE BILINGUAL SHORTS
# ===================================================================

def assemble_bilingual_shorts(scene_video_folder, en_audio_folder, es_audio_folder,
                               shorts_config, output_folder):
    """Create bilingual vertical shorts (1080x1920) for each kid"""

    shorts_folder = output_folder / "shorts"
    shorts_folder.mkdir(exist_ok=True)

    # Vertical crop+pad filter: 1920x1080 -> crop center square -> pad to 1080x1920
    vert_vf = (
        f"crop=ih:ih:(iw-ih)/2:0,"
        f"scale={SHORTS_WIDTH}:{SHORTS_WIDTH},"
        f"pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:0:(oh-ih)/2:white"
    )
    vert_vf_flip = (
        f"hflip,"
        f"crop=ih:ih:(iw-ih)/2:0,"
        f"scale={SHORTS_WIDTH}:{SHORTS_WIDTH},"
        f"pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:0:(oh-ih)/2:white"
    )

    for short in shorts_config:
        kid = short['kid'].lower()
        scenes = short['scenes']

        temp_folder = shorts_folder / f"temp_{kid}"
        temp_folder.mkdir(exist_ok=True)

        clip_paths = []

        for scene_num in scenes:
            scene_video = scene_video_folder / f"scene_{scene_num:02d}.mp4"
            en_audio = en_audio_folder / f"scene_{scene_num:02d}.mp3"
            es_audio = es_audio_folder / f"scene_{scene_num:02d}.mp3"

            if not scene_video.exists():
                continue

            # EN vertical clip
            en_clip = temp_folder / f"s{scene_num:02d}_en.mp4"
            _ffmpeg_encode_clip(scene_video, en_audio, en_clip, vfilters=vert_vf)
            clip_paths.append(en_clip)

            # ES vertical clip (hflipped)
            es_clip = temp_folder / f"s{scene_num:02d}_es.mp4"
            _ffmpeg_encode_clip(scene_video, es_audio, es_clip, vfilters=vert_vf_flip)
            clip_paths.append(es_clip)

        # Concat into final short
        short_output = shorts_folder / f"short_{kid}_bilingual.mp4"
        _ffmpeg_concat(clip_paths, short_output)

        duration = len(scenes) * SCENE_DURATION * 2
        print(f"    [OK] Short ({short['kid']}): {short_output.name} (~{duration}s)")

    return shorts_folder

# ===================================================================
# KDP BOOK FROM VIDEO CONTENT (separate EN & ES)
# ===================================================================

# KDP specs (6" x 9" trim with 0.125" bleed)
try:
    from reportlab.lib.units import inch as _inch
    _KDP = {
        "trim_w": 6.0 * _inch, "trim_h": 9.0 * _inch,
        "bleed": 0.125 * _inch,
        "int_w": 6.25 * _inch, "int_h": 9.25 * _inch,
        "margin": 0.375 * _inch,
        "paper": 0.002252,
    }
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False

YOUTUBE_CHANNEL = "https://www.youtube.com/@AesopsStoryhouse"
FAMILY_BLURB = """About Aesop's Storyhouse

This is a family-run channel creating magical educational content
for children ages 2-5. Every story is inspired by our real family
experiences with Emma (7 months), Oliver (2 years), Noah (3 years),
and Liam (5 years).

Watch more magical adventures: """ + YOUTUBE_CHANNEL


def generate_kdp_from_video(content, image_folder, output_folder, lang="EN"):
    """Generate KDP-ready book PDFs reusing video pipeline content + images."""

    if not _HAS_REPORTLAB:
        raise ImportError("reportlab not installed. Run: pip install reportlab Pillow")

    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from textwrap import wrap
    from PIL import Image

    # Convert video content format to book story format
    story = {
        "title": content.get("title", "Learn with Aesop's Storyhouse"),
        "scenes": []
    }
    for i, scene in enumerate(content.get("scenes", []), 1):
        kid_name = KIDS.get(scene.get("kid", ""), {}).get("name", scene.get("kid", ""))
        text = scene.get("description", f"{kid_name} learns something new!")
        story["scenes"].append({"number": i, "text": text})

    # Pad to 15 if needed
    while len(story["scenes"]) < 15:
        story["scenes"].append({"number": len(story["scenes"]) + 1, "text": "The magical adventure continues with wonder and joy."})

    # Collect scene images
    scene_images = []
    for i in range(1, 16):
        p = Path(image_folder) / f"scene_{i:02d}.jpg"
        if not p.exists():
            p = Path(image_folder) / f"scene_{i:02d}.png"
        scene_images.append(p)

    # KDP output folder
    kdp_out = Path(output_folder) / "kdp" / lang
    kdp_out.mkdir(parents=True, exist_ok=True)

    safe_title = "".join(c for c in story["title"] if c.isalnum() or c in " -_").strip()[:30]

    # -- Interior PDF --
    interior_path = kdp_out / f"{safe_title}_Interior.pdf"
    c = canvas.Canvas(str(interior_path), pagesize=(_KDP["int_w"], _KDP["int_h"]))

    # Title page
    c.setFont("Helvetica-Bold", 36)
    y = _KDP["int_h"] / 2 + 60
    for word in story["title"].split():
        w = c.stringWidth(word, "Helvetica-Bold", 36)
        c.drawString((_KDP["int_w"] - w) / 2, y, word)
        y -= 45
    c.setFont("Helvetica", 18)
    t = "Aesop's Storyhouse"
    c.drawString((_KDP["int_w"] - c.stringWidth(t, "Helvetica", 18)) / 2, 100, t)
    c.setFont("Helvetica", 12)
    age_label = "Edades 2-5" if lang == "ES" else "Ages 2-5"
    c.drawString((_KDP["int_w"] - c.stringWidth(age_label, "Helvetica", 12)) / 2, 75, age_label)
    c.showPage()

    # Copyright page
    c.setFont("Helvetica", 10)
    y = _KDP["int_h"] - 100
    if lang == "ES":
        copyright_text = f"Copyright \u00a9 2026 Aesop's Storyhouse\nTodos los derechos reservados.\n\nDedicado a Emma, Oliver, Noah y Liam.\n\nVisitanos: {YOUTUBE_CHANNEL}"
    else:
        copyright_text = f"Copyright \u00a9 2026 Aesop's Storyhouse\nAll rights reserved.\n\nDedicated to Emma, Oliver, Noah, and Liam.\n\nVisit us: {YOUTUBE_CHANNEL}"
    for line in copyright_text.split("\n"):
        if line.strip():
            w = c.stringWidth(line, "Helvetica", 10)
            c.drawString((_KDP["int_w"] - w) / 2, y, line)
        y -= 14
    c.showPage()

    # 15 scenes: image page + text page each
    for i, scene in enumerate(story["scenes"][:15], 1):
        img_path = scene_images[i - 1] if i - 1 < len(scene_images) else None
        # Image page
        if img_path and img_path.exists():
            c.drawImage(ImageReader(str(img_path)), 0, _KDP["bleed"], _KDP["int_w"], _KDP["trim_h"], preserveAspectRatio=True, anchor="c")
        else:
            c.setFillColorRGB(0.9, 0.9, 0.95)
            c.rect(0, 0, _KDP["int_w"], _KDP["int_h"], fill=1)
            c.setFillColorRGB(0.5, 0.5, 0.6)
            c.setFont("Helvetica", 24)
            t = f"Scene {i}"
            c.drawString((_KDP["int_w"] - c.stringWidth(t, "Helvetica", 24)) / 2, _KDP["int_h"] / 2, t)
        c.showPage()

        # Text page
        c.setFillColorRGB(0.98, 0.98, 1.0)
        c.rect(0, 0, _KDP["int_w"], _KDP["int_h"], fill=1)
        c.setFillColorRGB(0.3, 0.4, 0.7)
        c.setFont("Helvetica-Bold", 16)
        sn = f"Scene {i}"
        c.drawString((_KDP["int_w"] - c.stringWidth(sn, "Helvetica-Bold", 16)) / 2, _KDP["int_h"] - 60, sn)
        c.setStrokeColorRGB(0.7, 0.7, 0.9)
        c.setLineWidth(1.5)
        lm = _KDP["int_w"] * 0.15
        c.line(lm, _KDP["int_h"] - 78, _KDP["int_w"] - lm, _KDP["int_h"] - 78)
        c.setFillColorRGB(0.15, 0.15, 0.25)
        c.setFont("Helvetica", 15)
        y_t = _KDP["int_h"] - 120
        for line in wrap(scene.get("text", ""), 38):
            if y_t > 60:
                lw = c.stringWidth(line, "Helvetica", 15)
                c.drawString((_KDP["int_w"] - lw) / 2, y_t, line)
                y_t -= 20
        c.showPage()

    # About page
    c.setFillColorRGB(0.95, 0.97, 1.0)
    c.rect(0, 0, _KDP["int_w"], _KDP["int_h"], fill=1)
    c.setFillColorRGB(0.35, 0.45, 0.75)
    c.rect(_KDP["margin"], _KDP["int_h"] - 80, _KDP["int_w"] - _KDP["margin"] * 2, 50, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 16)
    about_title = "Sobre Aesop's Storyhouse" if lang == "ES" else "About Aesop's Storyhouse"
    c.drawString(_KDP["margin"] + 15, _KDP["int_h"] - 55, about_title)
    c.setFillColorRGB(0.2, 0.2, 0.3)
    c.setFont("Helvetica", 10)
    y = _KDP["int_h"] - 100
    blurb = FAMILY_BLURB
    for line in blurb.split("\n"):
        if line.strip():
            for wl in wrap(line, 45):
                if y > _KDP["margin"] + 20:
                    c.drawString(_KDP["margin"] + 15, y, wl)
                    y -= 13
    c.save()
    print(f"    [OK] Interior ({lang}): {interior_path.name}")

    # -- Cover PDF --
    pages = 33
    spine_w = pages * _KDP["paper"] * _inch
    cover_w = _KDP["bleed"] * 2 + _KDP["trim_w"] * 2 + spine_w
    cover_h = _KDP["bleed"] * 2 + _KDP["trim_h"]
    cover_path = kdp_out / f"{safe_title}_Cover.pdf"
    c = canvas.Canvas(str(cover_path), pagesize=(cover_w, cover_h))

    # Back cover
    bx = _KDP["bleed"]
    bw = _KDP["trim_w"]
    c.setFillColorRGB(0.4, 0.5, 0.8)
    c.rect(bx, _KDP["bleed"], bw, _KDP["trim_h"], fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 14)
    back_label = "Una Historia Sobre" if lang == "ES" else "A Magical Story About"
    c.drawString(bx + 30, cover_h - 40, back_label)
    c.drawString(bx + 30, cover_h - 58, story["title"])
    c.setFont("Helvetica", 10)
    y = cover_h - 90
    summary = " ".join(s.get("text", "") for s in story["scenes"][:3])[:250]
    for line in wrap(summary, 35):
        if y > 180:
            c.drawString(bx + 30, y, line)
            y -= 12
    c.setFont("Helvetica-Bold", 9)
    watch_label = "Ve Mas:" if lang == "ES" else "Watch More:"
    c.drawString(bx + 30, 75, watch_label)
    c.setFont("Helvetica", 8)
    c.drawString(bx + 30, 63, "youtube.com/@AesopsStoryhouse")

    # Spine
    sx = bx + bw
    if pages >= 79:
        c.setFillColorRGB(0.25, 0.35, 0.7)
        c.rect(sx, _KDP["bleed"], spine_w, _KDP["trim_h"], fill=1)

    # Front cover
    fx = sx + spine_w
    fw = _KDP["trim_w"]
    c.setFillColorRGB(0.25, 0.3, 0.65)
    c.rect(fx, _KDP["bleed"], fw, _KDP["trim_h"], fill=1)

    # Title
    c.setFont("Helvetica-Bold", 17)
    title_lines = []
    cur = []
    for word in story["title"].split():
        test = " ".join(cur + [word])
        if c.stringWidth(test, "Helvetica-Bold", 17) < fw - 15:
            cur.append(word)
        else:
            if cur:
                title_lines.append(" ".join(cur))
            cur = [word]
    if cur:
        title_lines.append(" ".join(cur))
    ty = cover_h - 50
    c.setFillColorRGB(1, 1, 1)
    for tl in title_lines:
        tw = c.stringWidth(tl, "Helvetica-Bold", 17)
        c.drawString(fx + (fw - tw) / 2, ty, tl)
        ty -= 20

    # Cover image
    cover_img = scene_images[0] if scene_images and scene_images[0].exists() else None
    img_margin = 20
    frame_x = fx + img_margin
    frame_y = 140
    frame_w = fw - img_margin * 2
    frame_h = min(ty - frame_y - 15, 380)
    if frame_h < 280:
        frame_h = 280
    frame_y = ty - frame_h - 15

    c.setFillColorRGB(1, 1, 1)
    c.roundRect(frame_x - 5, frame_y - 5, frame_w + 10, frame_h + 10, 7, fill=1)
    if cover_img:
        c.drawImage(ImageReader(str(cover_img)), frame_x, frame_y, frame_w, frame_h, preserveAspectRatio=True, anchor="c")

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 11)
    at = "Aesop's Storyhouse"
    c.drawString(fx + (fw - c.stringWidth(at, "Helvetica", 11)) / 2, frame_y - 20, at)

    c.setFillColorRGB(0.95, 0.6, 0.2)
    badge_w, badge_h = 70, 18
    badge_x = fx + (fw - badge_w) / 2
    badge_y = frame_y - 42
    c.roundRect(badge_x, badge_y, badge_w, badge_h, 9, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 10)
    ag = "Edades 2-5" if lang == "ES" else "Ages 2-5"
    c.drawString(badge_x + (badge_w - c.stringWidth(ag, "Helvetica-Bold", 10)) / 2, badge_y + 4, ag)
    c.save()
    print(f"    [OK] Cover ({lang}): {cover_path.name}")

    # Save story metadata
    with open(kdp_out / "story_metadata.json", "w", encoding="utf-8") as f:
        json.dump(story, f, indent=2, ensure_ascii=False)

    return kdp_out


# ===================================================================
# STEP 12: SEO METADATA GENERATION
# ===================================================================

def generate_seo_metadata(topic_info, content, output_folder):
    """Generate SEO-optimized metadata for YouTube using seo_engine.py"""

    pipeline_dir = Path(__file__).parent
    sys.path.insert(0, str(pipeline_dir))

    try:
        from seo_engine import run_seo_pipeline
    except ImportError:
        print("    [WARN] seo_engine.py not found -- using fallback metadata")
        return _fallback_seo_metadata(topic_info, content)

    kid_order = ['Liam', 'Noah', 'Oliver', 'Emma']
    seo_data = run_seo_pipeline(topic_info, kid_order, youtube_service=None)

    # Save to output folder
    seo_path = output_folder / "seo_metadata.json"
    with open(seo_path, 'w', encoding='utf-8') as f:
        json.dump(seo_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n[OK] SEO metadata saved: {seo_path.name}")
    return seo_data


def _fallback_seo_metadata(topic_info, content):
    """Minimal SEO metadata when seo_engine.py is unavailable"""
    topic = topic_info['topic']
    keyword = topic_info['keyword']
    emoji = topic_info.get('emoji', '')

    return {
        "metadata_en": {
            "youtube_titles": [
                f"Learn {topic} with Liam, Noah, Oliver & Emma! {emoji} Bilingual EN/ES"
            ],
            "youtube_description": (
                f"Join Liam, Noah, Oliver, and baby Emma as they learn about {keyword}! "
                f"This bilingual video teaches in English and Spanish.\n\n"
                f"Subscribe: https://www.youtube.com/@AesopsStoryhouse"
            ),
            "youtube_tags": [
                "educational video for kids", "bilingual kids video", "english spanish kids",
                f"learn {keyword}", f"{keyword} for toddlers", f"{keyword} for kids",
                "toddler learning", "preschool learning", "aesops storyhouse",
            ],
            "youtube_shorts_titles": {
                "Liam": f"Liam Learns {topic}! {emoji}",
                "Noah": f"Noah Learns {topic}! {emoji}",
                "Oliver": f"Oliver Learns {topic}! {emoji}",
                "Emma": f"Baby Emma Sees {topic}! {emoji}",
            },
        },
        "metadata_es": {},
    }


# ===================================================================
# STEP 13: YOUTUBE UPLOAD
# ===================================================================

def upload_to_youtube(output_folder, seo_data, shorts_config, content=None):
    """Upload bilingual main video + 4 shorts to YouTube via Data API."""

    pipeline_dir = Path(__file__).parent
    sys.path.insert(0, str(pipeline_dir))

    try:
        from retry_upload import (
            get_youtube_service, upload_to_youtube as api_upload,
            find_playlist, add_to_playlist, PLAYLIST_MAP
        )
    except ImportError as e:
        print(f"    [SKIP] YouTube API libraries not available: {e}")
        return {}

    seo_en = seo_data.get('metadata_en', {})

    # Build upload queue: 1 bilingual main + 4 bilingual shorts
    uploads = []

    # Main bilingual video
    main_video = output_folder / "final_bilingual.mp4"
    if main_video.exists():
        title = seo_en.get('youtube_titles', ['Bilingual Video'])[0]
        uploads.append({
            'path': main_video,
            'title': title,
            'desc': seo_en.get('youtube_description', ''),
            'tags': seo_en.get('youtube_tags', []),
            'is_short': False,
            'thumb': None,
            'label': 'Main (Bilingual)',
        })

    # Bilingual shorts
    shorts_folder = output_folder / "shorts"
    if shorts_folder.exists():
        shorts_titles = seo_en.get('youtube_shorts_titles', {})
        for short_cfg in shorts_config:
            kid = short_cfg['kid']
            short_path = shorts_folder / f"short_{kid.lower()}_bilingual.mp4"
            if short_path.exists():
                short_title = shorts_titles.get(kid, f"{kid} Learns!")
                uploads.append({
                    'path': short_path,
                    'title': short_title,
                    'desc': seo_en.get('youtube_description', ''),
                    'tags': seo_en.get('youtube_tags', []),
                    'is_short': True,
                    'thumb': None,
                    'label': f'Short ({kid})',
                })

    if not uploads:
        print("    [SKIP] No videos found to upload")
        return {}

    print(f"\nFound {len(uploads)} videos to upload:")
    for u in uploads:
        size_mb = u['path'].stat().st_size / (1024 * 1024)
        print(f"  [{u['label']}] {u['path'].name} ({size_mb:.1f} MB)")

    # Authenticate via OAuth2
    print("\nAuthenticating with YouTube Data API...")
    youtube = get_youtube_service()
    if not youtube:
        print("    [FAIL] YouTube OAuth not set up.")
        return {}
    print("    [OK] Authenticated\n")

    # Upload each video
    results = {}
    for i, upload in enumerate(uploads, 1):
        print(f"\n[{i}/{len(uploads)}] Uploading: {upload['label']}")
        url = api_upload(
            youtube,
            video_path=upload['path'],
            title=upload['title'],
            description=upload['desc'],
            is_short=upload['is_short'],
            thumbnail_path=upload['thumb'],
            tags=upload['tags'],
        )
        results[upload['label']] = url

    # Playlist assignment
    topic_type = ''
    if content:
        topic_type = content.get('topic_type', '')
    if not topic_type:
        topic_type = seo_data.get('keyword_data', {}).get('topic', '').lower()
        for key in PLAYLIST_MAP:
            if key in topic_type:
                topic_type = key
                break

    if topic_type and topic_type in PLAYLIST_MAP:
        print(f"\nAdding to playlists ({topic_type})...")
        playlist_names = PLAYLIST_MAP[topic_type]
        en_pl_id = find_playlist(youtube, playlist_names['en'])
        if en_pl_id:
            added = 0
            for key, url in results.items():
                if url and 'youtube.com' in str(url):
                    if add_to_playlist(youtube, en_pl_id, url):
                        added += 1
            print(f"    EN playlist: {added} videos added")

    # Save upload results
    links_file = output_folder / "youtube_upload_results.json"
    with open(links_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    successful = sum(1 for v in results.values() if v and 'youtube.com' in str(v))
    print(f"\n[OK] YouTube upload: {successful}/{len(uploads)} videos uploaded")

    return results


# ===================================================================
# STEP 14: TIKTOK + INSTAGRAM UPLOAD (local only)
# ===================================================================

def upload_to_tiktok(output_folder, seo_data, shorts_config):
    """Upload shorts to TikTok -- local only, skipped in CI"""
    if CI_MODE:
        print("    [SKIP] TikTok upload not available in CI")
        return []

    tiktok_cookies = Path(__file__).parent / "tiktok_cookies.txt"
    if not tiktok_cookies.exists():
        print("    [SKIP] No tiktok_cookies.txt found")
        return []

    try:
        from tiktok_uploader.upload import upload_videos
    except ImportError:
        print("    [SKIP] tiktok-uploader not installed")
        return []

    # (TikTok upload logic unchanged from original -- only runs locally)
    print("    [SKIP] TikTok upload requires local browser session")
    return []


def upload_to_instagram(output_folder, seo_data, shorts_config):
    """Upload shorts as Instagram Reels -- local only, skipped in CI"""
    if CI_MODE:
        print("    [SKIP] Instagram upload not available in CI")
        return []

    ig_profile = Path(__file__).parent / "ig_browser_profile"
    if not ig_profile.exists():
        print("    [SKIP] No Instagram login. Run: python ig_upload.py --login")
        return []

    print("    [SKIP] Instagram upload requires local browser session")
    return []


# ===================================================================
# MAIN PRODUCTION FUNCTION
# ===================================================================

def run_daily_production(args=None):
    """Run bilingual daily production pipeline"""

    print("\n" + "="*70)
    print("BILINGUAL EDUCATIONAL PIPELINE - AESOP'S STORYHOUSE")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'CI (GitHub Actions)' if CI_MODE else 'Local'}")
    print("Format: All 4 kids rotate through educational topics")
    print("Output: 1 bilingual video (EN+ES) + 4 bilingual Shorts + KDP books")
    print("="*70)

    # Create output folder (relative path works in both local and CI)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_folder = Path("videos")
    base_folder.mkdir(exist_ok=True)

    # Pick topic: from CLI args or random
    if args and args.topic:
        # Find matching topic from EDUCATIONAL_TOPICS or auto-detect type
        topic = None
        for t in EDUCATIONAL_TOPICS:
            if t['topic'].lower() == args.topic.lower():
                topic = t
                break
        if not topic:
            # Auto-detect topic type from the input string
            topic_lower = args.topic.lower()
            if args.topic_type:
                detected_type = args.topic_type
            elif any(c in topic_lower for c in ['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'color', 'colour']):
                detected_type = 'color'
            elif any(n in topic_lower for n in ['count', 'number', 'digit', '1', '2', '3', '4', '5']):
                detected_type = 'number'
            elif any(s in topic_lower for s in ['circle', 'square', 'triangle', 'star', 'shape', 'rectangle', 'oval']):
                detected_type = 'shape'
            elif any(a in topic_lower for a in ['animal', 'farm', 'wild', 'dog', 'cat', 'lion', 'elephant', 'bird']):
                detected_type = 'animal'
            elif any(o in topic_lower for o in ['big', 'small', 'up', 'down', 'hot', 'cold', 'opposite', 'fast', 'slow']):
                detected_type = 'opposite'
            else:
                detected_type = 'color'
            topic = {
                "type": detected_type,
                "topic": args.topic,
                "keyword": args.topic.lower(),
                "emoji": "star"
            }
    else:
        topic = random.choice(EDUCATIONAL_TOPICS)

    topic_slug = topic['topic'].lower().replace(' ', '_')
    output_folder = base_folder / f"{timestamp}_{topic_slug}"
    output_folder.mkdir(exist_ok=True)

    print(f"\nOutput folder: {output_folder}")
    print(f"Topic: {topic['topic']} ({topic['emoji']})")

    # -- Step 1: Generate educational content --
    print("\n" + "="*70)
    print("STEP 1: GENERATING EDUCATIONAL CONTENT")
    print("="*70)

    content = generate_educational_content(topic)

    with open(output_folder / "content.json", 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    # Save scenes.json
    scenes_data = {"scenes": []}
    for scene in content['scenes']:
        scenes_data["scenes"].append({
            "action": scene.get("description", ""),
            "kid": scene.get("kid", ""),
            "object": scene.get("object", "")
        })
    with open(output_folder / "scenes.json", 'w', encoding='utf-8') as f:
        json.dump(scenes_data, f, indent=2, ensure_ascii=False)

    # -- Step 2: Create Krea prompts --
    print("\n" + "="*70)
    print("STEP 2: CREATING KREA PROMPTS")
    print("="*70)

    prompts = create_krea_prompts(content)

    with open(output_folder / "prompts.json", 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)

    # -- Step 3: Generate images --
    image_folder = generate_all_images(prompts, output_folder)

    # -- Step 3B: Animate images with Krea Hailuo --
    try:
        animate_all_scenes(prompts, image_folder, output_folder)
    except Exception as e:
        print(f"\n[WARN] Animation failed (will use static images): {e}")
        import traceback
        traceback.print_exc()

    # -- Step 4: Translate to Spanish --
    print("\n" + "="*70)
    print("STEP 4: TRANSLATING TO SPANISH")
    print("="*70)

    content_es = translate_to_spanish(content)

    with open(output_folder / "content_es.json", 'w', encoding='utf-8') as f:
        json.dump(content_es, f, indent=2, ensure_ascii=False)

    # -- Step 5: Generate per-scene TTS audio --
    print("\n" + "="*70)
    print("STEP 5: GENERATING TTS AUDIO")
    print("="*70)

    print("\n  English:")
    en_audio_folder = generate_all_scene_audio(content, output_folder, lang="en")

    print("\n  Spanish:")
    es_audio_folder = generate_all_scene_audio(content_es, output_folder, lang="es")

    # -- Step 6: Create shorts config --
    print("\n" + "="*70)
    print("STEP 6: CREATING SHORTS CONFIGURATION")
    print("="*70)

    shorts = create_shorts_config(content)

    with open(output_folder / "shorts_config.json", 'w', encoding='utf-8') as f:
        json.dump(shorts, f, indent=2, ensure_ascii=False)

    # -- Step 7: Create scene videos --
    print("\n" + "="*70)
    print("STEP 7: CREATING SCENE VIDEOS")
    print("="*70)

    scene_video_folder = ensure_scene_videos(image_folder, output_folder)

    # -- Step 8: Assemble bilingual main video --
    print("\n" + "="*70)
    print("STEP 8: ASSEMBLING BILINGUAL MAIN VIDEO")
    print("="*70)

    final_video = None
    try:
        final_video = assemble_bilingual_video(
            scene_video_folder, en_audio_folder, es_audio_folder, output_folder
        )
    except Exception as e:
        print(f"\n[WARN] Bilingual video assembly failed: {e}")
        import traceback
        traceback.print_exc()

    # -- Step 9: Assemble bilingual shorts --
    print("\n" + "="*70)
    print("STEP 9: ASSEMBLING BILINGUAL SHORTS")
    print("="*70)

    shorts_folder = None
    try:
        shorts_folder = assemble_bilingual_shorts(
            scene_video_folder, en_audio_folder, es_audio_folder, shorts, output_folder
        )
    except Exception as e:
        print(f"\n[WARN] Shorts assembly failed: {e}")
        import traceback
        traceback.print_exc()

    # -- Step 10: Generate KDP books (EN + ES) --
    skip_kdp = args and args.skip_kdp
    if not skip_kdp:
        print("\n" + "="*70)
        print("STEP 10: GENERATING KDP BOOKS")
        print("="*70)

        print("  English:")
        try:
            kdp_en = generate_kdp_from_video(content, image_folder, output_folder, lang="EN")
            print(f"    [OK] EN KDP: {kdp_en}")
        except Exception as e:
            print(f"    [WARN] EN KDP failed: {e}")

        print("  Spanish:")
        try:
            kdp_es = generate_kdp_from_video(content_es, image_folder, output_folder, lang="ES")
            print(f"    [OK] ES KDP: {kdp_es}")
        except Exception as e:
            print(f"    [WARN] ES KDP failed: {e}")
    else:
        print("\n[SKIP] KDP generation (--skip-kdp)")

    # -- Step 11: Queue KDP uploads (local only) --
    if not CI_MODE and not skip_kdp:
        print("\n" + "="*70)
        print("STEP 11: QUEUING KDP UPLOADS")
        print("="*70)
        try:
            from production_pipeline_local import queue_kdp_uploads_local
            queue_kdp_uploads_local(content, content_es, output_folder, topic)
        except (ImportError, Exception) as e:
            print(f"    [SKIP] KDP upload queue: {e}")
    elif CI_MODE:
        print("\n[SKIP] KDP Amazon upload (not available in CI)")

    # -- Step 12: SEO metadata --
    print("\n" + "="*70)
    print("STEP 12: GENERATING SEO METADATA")
    print("="*70)

    seo_data = {}
    try:
        seo_data = generate_seo_metadata(topic, content, output_folder)
    except Exception as e:
        print(f"\n[WARN] SEO generation failed: {e}")
        import traceback
        traceback.print_exc()
        seo_data = _fallback_seo_metadata(topic, content)

    # -- Step 13: Upload to YouTube --
    skip_youtube = args and args.skip_youtube
    if not skip_youtube:
        print("\n" + "="*70)
        print("STEP 13: UPLOADING TO YOUTUBE")
        print("="*70)

        yt_results = {}
        try:
            yt_results = upload_to_youtube(output_folder, seo_data, shorts, content=content)
        except Exception as e:
            print(f"\n[WARN] YouTube upload failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n[SKIP] YouTube upload (--skip-youtube)")
        yt_results = {}

    # -- Step 14: TikTok + Instagram (local only) --
    skip_tiktok = args and args.skip_tiktok
    skip_instagram = args and args.skip_instagram
    if not skip_tiktok:
        print("\n" + "="*70)
        print("STEP 14A: UPLOADING TO TIKTOK")
        print("="*70)
        upload_to_tiktok(output_folder, seo_data, shorts)

    if not skip_instagram:
        print("\n" + "="*70)
        print("STEP 14B: UPLOADING TO INSTAGRAM")
        print("="*70)
        upload_to_instagram(output_folder, seo_data, shorts)

    # -- Write results summary (for CI artifact) --
    results_summary = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic['topic'],
        "topic_type": topic['type'],
        "output_folder": str(output_folder),
        "videos": {
            "main": str(final_video) if final_video else None,
            "shorts": str(shorts_folder) if shorts_folder else None,
        },
        "kdp": {
            "en": str(output_folder / "kdp" / "EN") if not skip_kdp else None,
            "es": str(output_folder / "kdp" / "ES") if not skip_kdp else None,
        },
        "youtube": yt_results if not skip_youtube else {},
        "status": "completed",
    }

    with open(output_folder / "results.json", 'w', encoding='utf-8') as f:
        json.dump(results_summary, f, indent=2, ensure_ascii=False)

    # Also write to results/latest.json for the website
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    with open(results_dir / "latest.json", 'w', encoding='utf-8') as f:
        json.dump(results_summary, f, indent=2, ensure_ascii=False)

    # -- Summary --
    print("\n" + "="*70)
    print("PRODUCTION COMPLETE!")
    print("="*70)
    print(f"\nFolder: {output_folder}")
    print(f"Topic: {topic['topic']}")
    if final_video:
        print(f"  - Bilingual video: {final_video.name}")
    if shorts_folder:
        print(f"  - Bilingual shorts: 4 shorts")
    if not skip_kdp:
        print(f"  - KDP books: EN + ES")
    if not skip_youtube and yt_results:
        yt_success = sum(1 for v in yt_results.values() if v and 'youtube.com' in str(v))
        print(f"  - YouTube: {yt_success}/{len(yt_results)} uploaded")
    print("="*70)

    return output_folder

# ===================================================================
# CLI ENTRY POINT
# ===================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Aesop's Storyhouse Bilingual Production Pipeline"
    )
    parser.add_argument('--topic', type=str, default=None,
                        help='Topic to produce (e.g. "Red Color", "Farm Animals")')
    parser.add_argument('--topic-type', type=str, default=None,
                        choices=['color', 'number', 'shape', 'animal', 'size', 'opposite'],
                        help='Topic type (used for custom topics)')
    parser.add_argument('--skip-youtube', action='store_true',
                        help='Skip YouTube upload')
    parser.add_argument('--skip-kdp', action='store_true',
                        help='Skip KDP PDF generation')
    parser.add_argument('--skip-tiktok', action='store_true',
                        help='Skip TikTok upload')
    parser.add_argument('--skip-instagram', action='store_true',
                        help='Skip Instagram upload')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        output_folder = run_daily_production(args)
        print(f"\n[SUCCESS] Production completed: {output_folder}")
    except Exception as e:
        print(f"\n[ERROR] Production failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

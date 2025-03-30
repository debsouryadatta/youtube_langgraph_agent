import fal_client as fal


def generate_thumbnail(state):
    print("Generating thumbnail...")
    prompt_text = f"""Create a visually striking YouTube Shorts thumbnail for '{state["title"]}'.
    {state["description"]}
    
    Style requirements:
    - Vertical format optimized for mobile
    - High contrast and vibrant colors
    - Cinematic lighting with dramatic shadows
    - Modern, trending aesthetic
    - Clean composition with clear focal point
    - Professional quality finish"""
    
    result = fal.run(
        "fal-ai/fast-sdxl",
        arguments={
            "prompt": prompt_text,
            "negative_prompt": "text, watermark, blurry, low quality, distorted, amateur, poorly lit",
            "image_size": {"width": 1080, "height": 1920}
        }
    )
    return {"thumbnail_url": result["images"][0]["url"]}

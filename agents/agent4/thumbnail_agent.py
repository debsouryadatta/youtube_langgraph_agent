import fal_client as fal


def generate_thumbnail(state):
    print("Generating thumbnail...")
    # prompt_text = f"""Design a cutting-edge YouTube Shorts thumbnail for '{state["title"]}' that captivates tech enthusiasts.
    # {state["description"]}
    
    # Tech-focused style requirements:
    # - Vertical format optimized for mobile devices
    # - Futuristic color scheme with neon accents
    # - Dynamic lighting effects simulating digital interfaces
    # - Sleek, minimalist design with a high-tech aesthetic
    # - Incorporate subtle tech-related iconography or symbols
    # - Sharp, crisp imagery suggesting cutting-edge technology
    # - One central, eye-catching tech element as the focal point
    # - Professional, polished finish appealing to tech-savvy audience"""
    
    # result = fal.run(
    #     "fal-ai/fast-sdxl",
    #     arguments={
    #         "prompt": prompt_text,
    #         "negative_prompt": "text, watermark, blurry, low quality, distorted, amateur, poorly lit",
    #         "image_size": {"width": 1080, "height": 1920}
    #     }
    # )
    # return {"thumbnail_url": result["images"][0]["url"]}
    return {"thumbnail_url": "https://avatars.githubusercontent.com/u/91617309?v=4"}

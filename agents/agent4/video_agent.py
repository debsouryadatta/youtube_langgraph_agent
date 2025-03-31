import os
import numpy as np
from datetime import datetime
from moviepy.editor import (
    AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip,
    concatenate_audioclips, CompositeAudioClip
)
import matplotlib.font_manager as fm
import re

def timestamp_to_seconds(timestamp: str) -> float:
    """Convert a timestamp string (HH:MM:SS or MM:SS) to seconds."""
    parts = timestamp.split(":")
    if len(parts) == 2:  # MM:SS format
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    elif len(parts) == 3:  # HH:MM:SS format
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    else:
        try:
            return float(timestamp)  # Try direct conversion if it's already a number
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

def split_text_into_words(text):
    """Split text into words while preserving punctuation and filtering out single-letter words."""
    # This pattern keeps punctuation attached to words
    words = re.findall(r'\b[\w\']+\b|[.,!?;:…]', text)
    
    # Filter out empty strings and single-letter words (except 'I' and 'a')
    return [word for word in words if word.strip() and (len(word) > 1 or word.lower() in ['i', 'a'])]

def create_word_by_word_clips(text, start_time, duration, fontsize, font_path, shorts_width):
    """Create a sequence of clips with groups of words appearing and disappearing in sync with audio."""
    words = split_text_into_words(text)
    
    # Handle empty text case
    if len(words) == 0:
        return []
    
    # Group words into groups of 4 (or fewer for the last group if needed)
    word_groups = []
    i = 0
    current_group = []
    
    while i < len(words):
        # Check if current word is punctuation
        if words[i] in '.,!?;:…':
            # If we have words in the current group, add the punctuation to the last word
            if current_group:
                current_group[-1] += words[i]
            i += 1
            continue
        
        # Add the current word to the group
        current_group.append(words[i])
        i += 1
        
        # If we have 4 words or we've reached the end of the text, finalize the group
        if len(current_group) == 4 or i >= len(words):
            # Check if the next word is punctuation and add it to the last word in the group
            if i < len(words) and words[i] in '.,!?;:…':
                current_group[-1] += words[i]
                i += 1
            
            # Join the words with spaces and add to word_groups
            word_groups.append(" ".join(current_group))
            current_group = []
    
    # Calculate timing for each word group
    # We'll use less of the total duration to create gaps between captions
    # This ensures captions don't overlap and provides better sync with audio
    usable_duration = duration * 0.85  # Use only 85% of the total duration for captions
    
    # If we have no word groups (rare edge case), return empty list
    if not word_groups:
        return []
        
    time_per_group = usable_duration / len(word_groups)
    
    # Add an initial delay to sync better with audio
    # This helps ensure the caption appears slightly after the audio starts
    initial_delay = 0.4  # Increased from 0.2 to 0.4 seconds
    
    # Add a gap between captions to prevent overlap
    gap_between_captions = 0.2  # Increased from 0.1 to 0.2 seconds
    
    word_clips = []
    
    for i, word_group in enumerate(word_groups):
        # Calculate timing for this word group with initial delay and gaps
        # Each subsequent caption starts after the previous one ends plus a gap
        word_start_time = start_time + initial_delay + (i * (time_per_group + gap_between_captions))
        
        # Each word group appears for less than its allocated time to ensure no overlap
        word_duration = time_per_group * 0.9  # 90% of the allocated time
        
        # Create text clip for the word group with increased boldness and better visibility
        text_clip = TextClip(
            word_group, 
            fontsize=fontsize, 
            color='white', 
            font=font_path,
            stroke_width=4,  # Increased stroke width for more boldness
            stroke_color='black',  # Black outline for better contrast
            method='label'
        )
        
        # Set timing and position
        text_clip = (text_clip
                    .set_start(word_start_time)
                    .set_duration(word_duration)
                    .set_position(("center", "center")))  # Position in the center of the screen
        
        word_clips.append(text_clip)
    
    return word_clips

def create_image_overlays(images_manifest, video_duration, shorts_width, shorts_height):
    """Create fullscreen image overlays that appear throughout the video,
    ensuring text overlay areas remain visible."""
    image_clips = []
    
    # Use all segments
    all_segments = images_manifest
    
    if not all_segments:
        return image_clips  # Return empty list if no segments
    
    # Use ALL segments instead of just 90%
    selected_indices = list(range(len(all_segments)))
    
    # Track the end time of the previous image to ensure no gaps
    previous_end_time = 0
    
    for i, idx in enumerate(selected_indices):
        segment = all_segments[idx]
        
        # Skip if URL (file path) is missing or file doesn't exist
        if not segment.get("url") or not os.path.exists(segment["url"]):
            print(f"Warning: Image file not found: {segment.get('url')}")
            continue
        
        # Load the image
        try:
            img_clip = ImageClip(segment["url"])
            
            # Calculate start time and duration
            start_time = timestamp_to_seconds(segment["start"])
            duration = timestamp_to_seconds(segment["duration"])
            
            # Show image for 100% of the segment duration
            img_duration = duration
            
            # Start right at the beginning of the segment
            img_start = start_time
            
            # If there's a gap between this image and the previous one, adjust start time
            if i > 0 and img_start > previous_end_time:
                # There's a gap, so start this image right after the previous one
                img_start = previous_end_time
                # Extend duration to cover the gap
                img_duration += (start_time - previous_end_time)
            
            # Update the end time for the next iteration
            previous_end_time = img_start + img_duration
            
            # Calculate the height to reserve at the center for text overlay
            # Reserve more space in the middle for text
            text_height_reserve = 300  # Increased height to reserve for text in the middle
            
            # Calculate the available height for the image
            available_height = shorts_height - text_height_reserve
            
            # Resize to fit within the available screen area while showing the entire image
            width_scale = shorts_width / img_clip.w
            height_scale = available_height / img_clip.h
            
            # Use the smaller scaling factor to ensure the entire image fits
            scale_factor = min(width_scale, height_scale)
            
            # Resize the image
            img_clip = img_clip.resize(scale_factor)
            
            # Center the image horizontally AND vertically
            x_center = (shorts_width - img_clip.w) / 2
            
            # Position the image to leave space in the middle for text
            # Move image up to leave the middle area clear for text
            y_position = (available_height - img_clip.h) / 4  # Position image in the upper part
            
            # Create a partial background for the image area if needed
            if img_clip.w < shorts_width or img_clip.h < available_height:
                # Create background only for the image area
                img_bg = ColorClip(size=(shorts_width, shorts_height), color=(0, 0, 0))
                img_bg = img_bg.set_duration(img_duration)
                img_bg = img_bg.set_position((0, 0))  # Position at the top
                
                # Add image on top of the background
                positioned_img = CompositeVideoClip([
                    img_bg,
                    img_clip.set_position((x_center, y_position))  # Position image higher up
                ])
            else:
                # Image fills the width, no need for additional background
                positioned_img = img_clip.set_position((x_center, y_position))  # Position image higher up
            
            # Set timing
            positioned_img = (positioned_img
                             .set_start(img_start)
                             .set_duration(img_duration))
            
            image_clips.append(positioned_img)
            
        except Exception as e:
            print(f"Error creating image overlay for {segment['url']}: {e}")
    
    # Check if there's still time left after the last image
    if previous_end_time < video_duration:
        # If the last image doesn't extend to the end of the video,
        # extend its duration or repeat the last image
        if image_clips:
            last_clip = image_clips[-1]
            extended_duration = last_clip.duration + (video_duration - previous_end_time)
            image_clips[-1] = last_clip.set_duration(extended_duration)
    
    return image_clips

def create_video_with_overlays(state):
    print("Creating final video with word-by-word highlighting...")
    print("\n\nState from create_video node: ", state)
    state["bg_music_path"] = "assets/bg_music.mp3"
    
    # Validate required keys in state
    if not state.get("audio_path"):
        raise ValueError("audio_path is required in state")
    if not state.get("images_manifest"):
        raise ValueError("images_manifest is required in state")
    if not state.get("script", {}).get("videoScript"):
        raise ValueError("script.videoScript is required in state")
    
    # Define YouTube Shorts dimensions
    shorts_width, shorts_height = 1080, 1920
    
    try:
        # Load audio
        audio = AudioFileClip(state["audio_path"])
        video_duration = audio.duration
        
        # Create a black background for the Shorts format
        background = ColorClip(size=(shorts_width, shorts_height), color=(0, 0, 0))
        background = background.set_duration(video_duration)
        
        # Get fonts
        font_path = "assets/fonts/LilitaOne-Regular.ttf"
        fontsize = 80  # Increased font size for better visibility and boldness
        
        # Create text overlays with word-by-word highlighting
        text_overlays = []
        for seg in state["script"]["videoScript"]:
            if not seg.get("text") or not seg.get("start") or not seg.get("duration"):
                raise ValueError(f"Invalid script segment: {seg}")
            
            start_time = timestamp_to_seconds(seg["start"])
            duration = timestamp_to_seconds(seg["duration"])
            text = seg["text"]
            
            # Create word-by-word clips
            word_clips = create_word_by_word_clips(
                text=text,
                start_time=start_time,
                duration=duration,
                fontsize=fontsize,
                font_path=font_path,
                shorts_width=shorts_width
            )
            
            # Position each clip in the center of the screen
            # No need to reposition as we're already setting position to center in create_word_by_word_clips
            text_overlays.extend(word_clips)
        
        # Create image overlays using the local image paths from images_manifest
        image_overlays = create_image_overlays(
            state["images_manifest"], 
            video_duration,
            shorts_width,
            shorts_height
        )
        
        # Add background music if provided
        final_audio = audio
        if "bg_music_path" in state and state["bg_music_path"] and os.path.exists(state["bg_music_path"]):
            try:
                # Load background music
                bg_music = AudioFileClip(state["bg_music_path"])
                
                # Set the volume to be low (10% of original)
                bg_music = bg_music.volumex(0.1)
                
                # Loop the music if it's shorter than the video
                if bg_music.duration < video_duration:
                    # Calculate how many times we need to loop
                    loop_count = int(np.ceil(video_duration / bg_music.duration))
                    # Create a list of music clips
                    music_clips = [bg_music] * loop_count
                    # Concatenate the clips
                    bg_music = concatenate_audioclips(music_clips)
                
                # Trim to match video duration
                bg_music = bg_music.subclip(0, video_duration)
                
                # Mix background music with original audio
                final_audio = CompositeAudioClip([audio, bg_music])
                
                print(f"Background music added from {state['bg_music_path']}")
            except Exception as e:
                print(f"Warning: Could not add background music: {e}")
        else:
            print("No background music path provided or file not found, continuing without background music")
        
        # Combine all clips - ORDER MATTERS: background first, then images, then text on top
        all_clips = [background] + image_overlays + text_overlays
        
        # Create composite video
        composite = CompositeVideoClip(all_clips, size=(shorts_width, shorts_height))
        
        # Set the duration to match the audio
        composite = composite.set_duration(video_duration)
        
        # Set the final audio
        composite = composite.set_audio(final_audio)
        
        # Create output directory if it doesn't exist
        output_dir = "output/final_videos"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output path with timestamp
        output_path = f"{output_dir}/video_output_{datetime.now().timestamp()}.mp4"
        
        # Write the final video
        composite.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            audio=True,
            threads=4,
            preset='medium'
        )
        
        # Return the path to the final video
        return {"final_video_path": output_path}
        
    except Exception as e:
        raise ValueError(f"Failed to create video: {str(e)}")
        
    finally:
        # Clean up MoviePy clips
        try:
            if 'composite' in locals():
                composite.close()
            if 'audio' in locals():
                audio.close()
            if 'bg_music' in locals():
                bg_music.close()
            
            # Close all image clips
            if 'image_overlays' in locals():
                for clip in image_overlays:
                    clip.close()
            
            # Close all text clips
            if 'text_overlays' in locals():
                for clip in text_overlays:
                    clip.close()
                    
        except Exception as e:
            print(f"Warning: Failed to clean up some MoviePy clips: {e}")

if __name__ == "__main__":
    state = {'topic': 'Tell me a motivational real story', 'script': {'videoScript': [{'start': '00:00', 'duration': '00:05', 'text': 'Are yaar, kya aap life mein kabhi haar manne ka socha hai? Main bahut excited hoon'}, {'start': '00:05', 'duration': '00:04', 'text': 'aapko ek aisi kahani sunne ke liye jo aapki soch badal degi.'}, {'start': '00:08', 'duration': '00:06', 'text': 'Ek gaon mein ek ladki thi. Uske paas kuch nahi tha. Zero. Lekin uske andar ek aag thi,'}, {'start': '00:14', 'duration': '00:06', 'text': 'kuch banne ki. Log us par haste the, kehte the, tu nahi kar payegi.'}, {'start': '00:19', 'duration': '00:06', 'text': 'Dot. Phir kuch aisa hua jo... Usne din raat mehnat ki. Fail hui, giri,'}, {'start': '00:23', 'duration': '00:04', 'text': 'giri, lekin haar nahi maani.'}, {'start': '00:25', 'duration': '00:05', 'text': 'Kya aapko pata hai woh kya bani? Aaj woh ek successful business woman hai.'}, {'start': '00:29', 'duration': '00:05', 'text': 'Kya baat hai. Socho zara, agar woh kar sakti hai toh aap bhi kar sakte ho.'}, {'start': '00:34', 'duration': '00:04', 'text': 'Hai na? Toh comment mein batao, aap aaj kya challenge face kar rahe ho?'}, {'start': '00:38', 'duration': '00:01', 'text': 'Chalo, saath mein jeetenge.'}], 'totalDuration': '00:39'}, 'title': 'NEVER GIVE UP! 💪 Inspiring Motivation Story #shorts', 'description': 'Feeling down? 🥺 This story will change your perspective! 🔥 You CAN do it! What challenges are YOU facing? Comment below! 👇 #motivation #inspiration #success', 'thumbnail_url': 'https://avatars.githubusercontent.com/u/91617309?v=4', 'audio_path': 'output/audios/audio_1743362982.207016.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:05', 'text': 'Are yaar, kya aap life mein kabhi haar manne ka socha hai? Main bahut excited hoon', 'url': 'output/images/segment_1.png', 'source': 'Gemini', 'prompt': "A highly detailed vertical (1080x1920) image depicting a determined young Indian man in his late 20s, dressed in smart casual attire (think a stylish button-down shirt and dark jeans), standing amidst a bustling, modern Indian city street. The background should be slightly blurred, creating depth of field and focusing attention on the subject. He is looking directly at the viewer with a confident, slightly mischievous smile. His eyes sparkle with determination and resilience. The scene is bathed in golden hour lighting, with warm sunlight filtering through the surrounding buildings, casting long shadows and highlighting his face. The overall mood is optimistic and uplifting. The style is photorealistic but with a slightly stylized, vibrant color palette, leaning towards a modern, professional aesthetic. Include subtle bokeh effects in the background light sources. The composition should follow the rule of thirds, placing the man slightly off-center for visual interest. No text or words should be visible in the image. The image should convey a sense of unwavering determination and excitement for life's possibilities. Aim for high resolution and exceptional clarity."}, {'start': '00:05', 'duration': '00:04', 'text': 'aapko ek aisi kahani sunne ke liye jo aapki soch badal degi.', 'url': 'output/images/segment_2.png', 'source': 'Gemini', 'prompt': 'Vertical portrait (1080x1820). A lone, weathered hand meticulously plants a tiny seedling in parched, cracked earth under a scorching sun. The hand is slightly blurred, suggesting purposeful, ongoing action. In the background, a distant, hazy desert landscape stretches towards the horizon, hinting at hardship. Focus should be sharp on the seedling and the immediate surrounding earth. The overall mood is hopeful yet determined. Lighting is dramatic, with strong contrasts emphasizing the struggle and resilience. Use a hyperrealistic, photographic style with vibrant, warm colors for the earth tones, contrasting with a pale, slightly washed-out sky. Emphasize textures: the roughness of the hand, the dryness of the soil, the fragility of the seedling. The composition should lead the eye from the distant landscape, focusing on the hand and the seedling as the central point of hope and transformation. Modern, clean aesthetic. No text.'}, {'start': '00:08', 'duration': '00:06', 'text': 'Ek gaon mein ek ladki thi. Uske paas kuch nahi tha. Zero. Lekin uske andar ek aag thi,', 'url': 'output/images/segment_3.png', 'source': 'Gemini', 'prompt': "Vertical portrait of a young South Asian girl (1080x1920). She is standing in a dusty, rural Indian village. Her clothes are simple and worn, but clean. Her expression is determined and hopeful, with a slight upward tilt to her chin. Her eyes are large and bright, reflecting the golden light of the setting sun. The background shows basic mud homes with thatched roofs, realistically rendered. Dust particles float in the air, illuminated by the warm, dramatic sunlight. Focus sharply on the girl's face and upper body. The overall mood is one of resilience and quiet strength. Use a hyperrealistic painting style with vibrant colors and high dynamic range. Lighting should be warm and dramatic, emphasizing the girl's inner fire. The composition should be tight and intimate, drawing the viewer's attention to her face. Professional, modern aesthetic, avoiding any cliche or overly sentimental elements."}, {'start': '00:14', 'duration': '00:06', 'text': 'kuch banne ki. Log us par haste the, kehte the, tu nahi kar payegi.', 'url': 'output/images/segment_4.png', 'source': 'Gemini', 'prompt': "Vertical portrait, 1080x1920: A young woman in her early 20s, dressed in slightly worn but determined clothes, stands in a dimly lit, cluttered workshop. She's surrounded by disassembled electronics, wires, and tools. Her face is etched with a mix of frustration and unwavering resolve. The background is slightly blurred, focusing attention on her. A single, bright overhead light illuminates her face and the specific project she's working on – a complex circuit board. The color palette should be predominantly cool blues and grays, with a pop of vibrant green from an LED light on the circuit board. The mood is one of quiet struggle and perseverance. The style is realistic, slightly gritty, with a focus on texture and detail. High-quality, vibrant imagery. A subtle glow emanates from her focused eyes. The composition should emphasize her isolation and the difficulty of her task, yet hint at the potential for innovation and success."}, {'start': '00:19', 'duration': '00:06', 'text': 'Dot. Phir kuch aisa hua jo... Usne din raat mehnat ki. Fail hui, giri,', 'url': 'output/images/segment_5.png', 'source': 'Gemini', 'prompt': 'A young woman, around 25, with determined eyes, sits hunched over a laptop in a dimly lit, modern apartment. The laptop screen glows brightly, casting a soft light on her face, highlighting streaks of exhaustion but also unwavering focus. Empty coffee cups and scattered notes surround her workspace, suggesting long hours of work. The scene is viewed from a slightly low angle, emphasizing the height of the vertical 1080x1820 frame and creating a sense of aspiration. Outside the window, the faint glow of city lights hints at the late hour. The overall mood is one of quiet determination and perseverance against adversity. The style should be realistic yet slightly stylized, with vibrant colors and sharp focus. The image should convey a modern, tech-savvy vibe, suitable for a YouTube Shorts audience. High-quality rendering with realistic textures and lighting is crucial. No text or logos should be visible.'}, {'start': '00:23', 'duration': '00:04', 'text': 'giri, lekin haar nahi maani.', 'url': 'output/images/segment_6.png', 'source': 'Gemini', 'prompt': 'A vertical 1080x1820 image depicting a young, determined female rock climber, mid-fall, but still gripping the rock face with one hand. She\'s wearing brightly colored climbing gear (harness, helmet, shoes) against a rugged, sun-drenched mountain backdrop. Dust and chalk powder billow around her, emphasizing the movement and struggle. The composition should be dynamic, capturing the moment of near-failure with a sense of resilience. The lighting is dramatic, with strong highlights and shadows to accentuate her muscular form and the texture of the rock. The overall mood is motivational and inspiring, conveying a sense of "grit" and determination. The style is realistic but with a slightly stylized, vibrant color palette. The climber\'s face should be visible, showing intense focus and unwavering resolve, despite the fall. No text or words should be present in the image.'}, {'start': '00:25', 'duration': '00:05', 'text': 'Kya aapko pata hai woh kya bani? Aaj woh ek successful business woman hai.', 'url': 'output/images/segment_7.png', 'source': 'Gemini', 'prompt': "Vertical portrait, 1080x1920. Image depicting a modern, successful businesswoman in her late 30s, radiating confidence and competence. She stands in a bright, airy, contemporary office space, possibly a co-working environment with large windows overlooking a vibrant city skyline. She's dressed in stylish, professional attire - a tailored blazer and smart trousers, subtle jewelry. The background features blurred figures of other professionals working collaboratively, implying a dynamic and thriving business environment. Focus is sharply on the businesswoman, with soft, diffused natural lighting emphasizing her strong features and warm smile. The overall mood is optimistic, empowering, and aspirational. Style is photorealistic with a touch of artistic flair, using a slightly desaturated color palette with pops of vibrant accent colors (e.g., a colorful piece of abstract art on the wall). Composition follows the rule of thirds, placing the businesswoman slightly off-center to create visual interest. High resolution, sharp details, and vibrant colors are essential. No text or logos should appear in the image."}, {'start': '00:29', 'duration': '00:05', 'text': 'Kya baat hai. Socho zara, agar woh kar sakti hai toh aap bhi kar sakte ho.', 'url': 'output/images/segment_8.png', 'source': 'Gemini', 'prompt': "Vertical portrait (1080x1920). A vibrant, uplifting scene depicting a young woman, perhaps in her late 20s or early 30s, triumphantly reaching the summit of a mountain. She's dressed in modern athletic gear, radiating confidence and joy. The background showcases a breathtaking panoramic vista of rolling hills bathed in the warm, golden light of a rising or setting sun. Capture the feeling of accomplishment. Soft, diffused lighting with strong backlighting to create a halo effect around her silhouette. Focus on her determined expression and the expansive landscape behind her. Modern, slightly stylized rendering with vivid colors and sharp details. The composition emphasizes the verticality of the scene and her upward trajectory, symbolizing achievement and aspiration. A single, unfurled flag (perhaps a small, personal one) is subtly visible in her hand, further emphasizing her victory. No text or logos."}, {'start': '00:34', 'duration': '00:04', 'text': 'Hai na? Toh comment mein batao, aap aaj kya challenge face kar rahe ho?', 'url': 'output/images/segment_9.png', 'source': 'Gemini', 'prompt': "Vertical portrait, 1080x1820. A young South Asian woman, early 20s, with a determined expression, stands confidently amidst a chaotic cityscape at sunrise. She's wearing modern business attire - a blazer over a simple top. The city behind her is partially blurred, emphasizing her focus. In the foreground, subtle, stylized geometric shapes (circles, lines, triangles) representing challenges are faintly visible and semi-transparent, almost like digital overlays. The overall color palette is warm and vibrant, with oranges and pinks from the sunrise contrasting with the cool blues and grays of the cityscape. Lighting is soft and diffused, highlighting her face and creating a hopeful mood. Style: Modern, clean, professional. Composition: Rule of thirds, with the woman positioned slightly to the left. High quality, sharp focus, vibrant colors, avoiding any text. The image should evoke a sense of overcoming obstacles and facing the day with courage."}, {'start': '00:38', 'duration': '00:01', 'text': 'Chalo, saath mein jeetenge.', 'url': 'output/images/segment_10.png', 'source': 'Gemini', 'prompt': 'A 1080x1920 vertical portrait image depicting a diverse group of young adults (ages 20-30) huddled together, their faces illuminated by the warm glow of a laptop screen. They are in a modern, minimalist co-working space with large windows overlooking a bustling city at twilight. The overall mood is optimistic and determined. One individual, slightly in front, is looking directly at the viewer with a confident, encouraging smile. The others are focused on the screen, showcasing a collaborative effort. Soft, ambient lighting enhances the sense of unity and purpose. The style is realistic with a slight touch of stylized rendering, emphasizing clean lines and vibrant color palettes. The composition should be tight and intimate, capturing the feeling of camaraderie and shared ambition. High-quality image with sharp focus on the faces and subtle background blur.'}]}
    result = create_video_with_overlays(state)
    print(result)
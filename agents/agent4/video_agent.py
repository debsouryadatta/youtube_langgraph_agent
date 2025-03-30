import os
import numpy as np
from datetime import datetime
from moviepy.editor import (
    AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip,
    concatenate_audioclips, CompositeAudioClip
)
import matplotlib.font_manager as fm
import re
import random

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

def get_system_font(bold=False) -> str:
    """Return a suitable system font path for text overlays.
    
    Args:
        bold (bool): Whether to return a bold font variant if available
    """
    # First try to find bold fonts if requested
    if bold:
        bold_font_candidates = [
            'Arial-Bold.ttf',
            'Helvetica-Bold.ttf',
            '/System/Library/Fonts/Helvetica-Bold.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/System/Library/Fonts/SF-Pro-Text-Bold.otf'
        ]
        for font in bold_font_candidates:
            if os.path.exists(font):
                return font
    
    # Regular font alternatives
    font_candidates = [
        'Arial.ttf',
        'Helvetica.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/SF-Pro-Text-Regular.otf'
    ]
    
    # Try to find specifically bold fonts in system fonts
    system_fonts = fm.findSystemFonts()
    if bold:
        for font in system_fonts:
            font_lower = font.lower()
            if 'bold' in font_lower and ('arial' in font_lower or 'helvetica' in font_lower or 'sf-pro' in font_lower):
                return font
    
    # Check for exact matches in font candidates
    for font in font_candidates:
        if os.path.exists(font):
            return font
    
    # Fall back to any system font
    if system_fonts:
        return system_fonts[0]
    
    raise ValueError("No suitable font found on the system")

def split_text_into_words(text):
    """Split text into words while preserving punctuation."""
    # This pattern keeps punctuation attached to words
    words = re.findall(r'\b[\w\']+\b|[.,!?;:…]', text)
    # Filter out empty strings
    return [word for word in words if word.strip()]

def create_word_by_word_clips(text, start_time, duration, fontsize, font_path, shorts_width):
    """Create a sequence of clips with pairs of words appearing and disappearing in sync with audio."""
    words = split_text_into_words(text)
    
    # Handle empty text case
    if len(words) == 0:
        return []
    
    # Group words into pairs (or single word for the last one if odd number)
    word_pairs = []
    for i in range(0, len(words), 2):
        if i + 1 < len(words):
            # Add a pair of words
            word_pairs.append(words[i] + " " + words[i+1])
        else:
            # Add the last word if we have an odd number
            word_pairs.append(words[i])
    
    # Calculate timing for each word pair
    # We'll use less of the total duration to create gaps between captions
    # This ensures captions don't overlap and provides better sync with audio
    usable_duration = duration * 0.85  # Use only 85% of the total duration for captions
    time_per_pair = usable_duration / len(word_pairs)
    
    # Add an initial delay to sync better with audio
    # This helps ensure the caption appears slightly after the audio starts
    initial_delay = 0.4  # Increased from 0.2 to 0.4 seconds
    
    # Add a gap between captions to prevent overlap
    gap_between_captions = 0.2  # Increased from 0.1 to 0.2 seconds
    
    word_clips = []
    
    for i, word_pair in enumerate(word_pairs):
        # Calculate timing for this word pair with initial delay and gaps
        # Each subsequent caption starts after the previous one ends plus a gap
        word_start_time = start_time + initial_delay + (i * (time_per_pair + gap_between_captions))
        
        # Each word pair appears for less than its allocated time to ensure no overlap
        word_duration = time_per_pair * 0.9  # 90% of the allocated time
        
        # Create text clip for the word pair
        text_clip = TextClip(
            word_pair, 
            fontsize=fontsize, 
            color='white', 
            font=font_path,
            stroke_width=2,  # Add stroke for better visibility
            stroke_color='black',  # Black outline for better contrast
            method='label'
        )
        
        # Set timing and position
        text_clip = (text_clip
                    .set_start(word_start_time)
                    .set_duration(word_duration)
                    .set_position(("center", "center")))
        
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
            
            # Calculate the height to reserve at the bottom for text overlay
            text_height_reserve = 220  # Height to reserve for text at bottom
            
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
            # Calculate vertical position to center in the available space
            y_center = (available_height - img_clip.h) / 2
            
            # Create a partial background for the image area if needed
            if img_clip.w < shorts_width or img_clip.h < available_height:
                # Create background only for the image area
                img_bg = ColorClip(size=(shorts_width, available_height), color=(0, 0, 0))
                img_bg = img_bg.set_duration(img_duration)
                img_bg = img_bg.set_position((0, 0))  # Position at the top
                
                # Add image on top of the background
                positioned_img = CompositeVideoClip([
                    img_bg,
                    img_clip.set_position((x_center, y_center))  # Position in center
                ])
            else:
                # Image fills the width, no need for additional background
                positioned_img = img_clip.set_position((x_center, y_center))  # Position in center
            
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
    print("State from create_video node: ", state)
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
        font_path = get_system_font(bold=True)
        fontsize = 70  # Increased font size for better visibility
        
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
            
            # Position each clip at the bottom of the screen
            bottom_margin = 150  # Margin from the bottom in pixels
            
            # Add all word clips to overlays
            for clip in word_clips:
                # Position at the bottom of the screen
                positioned_clip = clip.set_position(("center", shorts_height - bottom_margin))
                text_overlays.append(positioned_clip)
        
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
    state = {'topic': 'India versus Pakistan 2025 Champions Trophy, Match review', 'script': {'videoScript': [{'start': '00:00', 'duration': '00:01', 'text': 'Whoa, tech fam!'}, {'start': '00:02', 'duration': '00:05', 'text': "Is your strategy optimized or running legacy code like Pakistan's cricket team in the 2025 CT?"}, {'start': '00:09', 'duration': '00:01', 'text': "India's win wasn't just skill."}, {'start': '00:11', 'duration': '00:06', 'text': 'It felt like pure algorithmic efficiency, executing the game plan flawlessly. Kohli Sentry?'}, {'start': '00:18', 'duration': '00:05', 'text': 'Peak performance unlocked, like hitting 100% CPU usage for the winning process.'}, {'start': '00:24', 'duration': '00:05', 'text': "This tech is mind-blowing. Pakistan's outdated approach, according to experts?"}, {'start': '00:30', 'duration': '00:05', 'text': 'Seriously. Like running Windows XP. You gotta adapt or get debugged, right?'}, {'start': '00:36', 'duration': '00:05', 'text': "I'm stoked about how tech drives performance. What software or gadget helps you stay ahead?"}, {'start': '00:43', 'duration': '00:01', 'text': 'Drop your optimization secrets below.'}], 'totalDuration': '00:45'}, 'title': "AI Cricket Strategy: India's Tech Domination!", 'description': "India's cricket win = algorithmic perfection! 🤯 Pakistan's outdated? What tech helps YOU win? Share below! 👇 #CricketTech #AI #Algorithm #TechTips", 'thumbnail_url': 'https://avatars.githubusercontent.com/u/91617309?v=4', 'audio_path': 'output/audios/audio_1743276103.500623.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:01', 'text': 'Whoa, tech fam!', 'url': 'output/images/segment_1.png', 'source': 'Gemini', 'prompt': 'A hyper-realistic, vibrant, and dynamic portrait (9:16 aspect ratio) image depicting a futuristic cricket stadium overflowing with cheering fans. The stadium is rendered in a sleek, modern architectural style, bathed in the golden light of a setting sun. Two silhouetted cricket players, one in green representing Pakistan, the other in blue representing India, stand poised on the pitch, facing each other in a competitive stance. Energetic particle effects, resembling digital dust motes, swirl around them, symbolizing the intensity of the match. The mood is electric and anticipatory. The background features a blurred kaleidoscope of national colors (green, white, saffron, blue) in the crowd. Use dramatic lighting with strong contrasts and lens flares to emphasize the energy. Aim for a professional, tech-forward aesthetic, reminiscent of a high-budget sports broadcast. Generate a high-resolution image with exceptional detail and clarity.'}, {'start': '00:02', 'duration': '00:05', 'text': "Is your strategy optimized or running legacy code like Pakistan's cricket team in the 2025 CT?", 'url': 'output/images/segment_2.png', 'source': 'Gemini', 'prompt': 'A vertical (9:16) digital illustration depicting a stylized, abstract cricket stadium bathed in dramatic, dynamic lighting. On the left, a sleek, futuristic cricket bat and ball, rendered in polished chrome and glowing neon green, symbolizing optimized strategy. On the right, a cracked, weathered cricket bat and tattered ball, covered in pixelated glitches and static, representing legacy code and outdated tactics. Both are juxtaposed against a blurred background hinting at the vibrant colors of an India vs Pakistan cricket match, evoking both excitement and tension. The overall mood should be energetic and slightly humorous, employing a modern, graphic design style with sharp lines, bold color contrasts (greens, blues, oranges, and grays), and subtle digital distortions. Focus on creating a high-quality, vibrant image with clearly defined subjects and a sense of depth. The lighting should be dynamic, using spotlights and shadows to emphasize the contrast between the modern and outdated elements. A professional and tech-forward aesthetic is crucial.'}, {'start': '00:09', 'duration': '00:01', 'text': "India's win wasn't just skill.", 'url': 'output/images/segment_3.png', 'source': 'Gemini', 'prompt': 'Vertical (9:16) dynamic action shot. A jubilant Indian cricket team celebrating a crucial wicket against Pakistan in a packed, modern stadium bathed in the vibrant hues of the late afternoon sun. Focus on Virat Kohli leaping in the air, arms raised in victory, with other teammates mirroring his excitement in the blurred background. The Pakistani batsman is shown walking dejectedly off the pitch, head bowed, adding a touch of dramatic contrast. Employ shallow depth of field to emphasize Kohli and the immediate action. Stadium lights are beginning to illuminate, creating a sense of heightened tension and excitement. The overall mood is electric, capturing the passion and rivalry of the India-Pakistan cricket match. Render in a hyperrealistic style with sharp focus and vivid colors, maintaining a clean, professional, almost cinematic aesthetic.'}, {'start': '00:11', 'duration': '00:06', 'text': 'It felt like pure algorithmic efficiency, executing the game plan flawlessly. Kohli Sentry?', 'url': 'output/images/segment_4.png', 'source': 'Gemini', 'prompt': "A hyperrealistic, vertical (9:16 aspect ratio) digital painting depicting Virat Kohli in a futuristic cricket stadium bathed in the vibrant, energized glow of floodlights. Kohli is in mid-action, executing a powerful cover drive, his face reflecting intense focus and determination. The stadium behind him is a blurred spectacle of cheering Indian fans, rendered in bokeh-style lighting for depth. He is wearing the modern Indian cricket jersey, subtly stylized with digital circuit patterns integrated into the fabric. The scene should evoke a sense of algorithmic precision and flawless execution. The overall mood is triumphant and electric, with dynamic lighting emphasizing Kohli's athletic form. Render the image in a highly detailed, photorealistic style, using a modern, professional aesthetic suitable for tech content. The composition should emphasize Kohli as the central figure, conveying power and control. The background should imply a futuristic, technologically advanced stadium environment without being overly distracting."}, {'start': '00:18', 'duration': '00:05', 'text': 'Peak performance unlocked, like hitting 100% CPU usage for the winning process.', 'url': 'output/images/segment_5.png', 'source': 'Gemini', 'prompt': 'Vertical (9:16) cinematic still. Depict a stylized, abstract representation of peak performance in the context of a cricket match between India and Pakistan. Imagine a hyper-realistic, glowing, translucent cricket ball leaving an explosive trail of vibrant energy, almost like code or digital data streams, arcing across a stylized, futuristic cricket stadium blurred in the background. The ball should appear to be at the apex of its trajectory, bathed in a soft, ethereal light. The stadium should be rendered with dynamic bokeh and hints of both Indian and Pakistani flag colors subtly integrated into the lighting and architectural details. The overall mood is one of intense focus and electrifying energy. Style: Modern, clean, and high-tech. Lighting: Dramatic rim lighting on the ball and energy trail, with soft, diffused ambient lighting in the stadium. Composition: Rule of thirds, with the ball positioned slightly off-center to create a sense of movement and anticipation. Emphasize vibrant, saturated colors contrasting with darker, shadowed areas for maximum visual impact. Aim for a hyperrealistic, almost painterly quality, with a focus on detail and clarity. The overall feeling should be one of technological prowess and sporting excellence combined.'}, {'start': '00:24', 'duration': '00:05', 'text': "This tech is mind-blowing. Pakistan's outdated approach, according to experts?", 'url': 'output/images/segment_6.png', 'source': 'Gemini', 'prompt': "Vertical (9:16) image depicting a futuristic cricket stadium, partially obscured by holographic projections showcasing data visualizations of cricket statistics. One side of the stadium is bathed in the vibrant saffron of the Indian flag, while the other is illuminated in the deep green of the Pakistani flag, creating a dynamic contrast. In the foreground, a stylized cricket ball streaks towards the viewer, leaving a trail of glowing data points representing performance metrics. The overall mood is electric and intense, suggesting a high-stakes match. Lighting should be dramatic, with neon accents highlighting the technological aspects. The style should be modern and sleek, resembling a high-tech sports broadcast overlay. Composition should be dynamic and engaging, drawing the viewer's eye towards the center of the image. Aim for photorealistic quality with a hint of futuristic fantasy. Generate a high-resolution image with vibrant colors and sharp details, suitable for a tech-focused YouTube Short."}, {'start': '00:30', 'duration': '00:05', 'text': 'Seriously. Like running Windows XP. You gotta adapt or get debugged, right?', 'url': 'output/images/segment_7.png', 'source': 'Gemini', 'prompt': 'A vertical (9:16) image depicting a stressed-out, stylized humanoid robot partially constructed from vintage computer parts (CRT monitor head, keyboard torso, floppy disk arms) struggling to play cricket on a futuristic, hyper-realistic cricket field. The robot is awkwardly holding a modern cricket bat. In the background, futuristic stadiums packed with cheering, diverse crowds are visible under a bright, slightly hazy sky. The overall mood is humorous and slightly anxious. Style should be vibrant, high-tech meets retro-tech, with a clean, modern aesthetic. Lighting should be dynamic with strong rim lighting to separate the robot from the background, casting long, dramatic shadows. Focus is sharp on the robot\'s distressed, pixelated "face." The composition should be slightly asymmetrical, with the robot positioned on the left side of the frame, leaving space on the right to suggest the upcoming "debugged" scenario. High quality, photo-realistic, but with a touch of stylized rendering.'}, {'start': '00:36', 'duration': '00:05', 'text': "I'm stoked about how tech drives performance. What software or gadget helps you stay ahead?", 'url': 'output/images/segment_8.png', 'source': 'Gemini', 'prompt': 'Vertical (9:16) image depicting a futuristic cricket stadium filled with cheering fans, rendered in a photorealistic style. The stadium is bathed in the vibrant, dynamic light of a late afternoon sun, casting long shadows across the emerald green pitch. In the foreground, a holographic display projects a stylized, abstract data visualization showing real-time performance metrics of the India vs. Pakistan 2025 Champions Trophy match. The visualization should incorporate elements like glowing circuitry, flowing particles, and a subtle representation of cricket ball trajectories. The overall mood is energetic and optimistic, reflecting the excitement of the match and the power of technology. Focus on sharp details and dynamic composition, creating a sense of depth and immersion. The stadium architecture should be sleek and modern, hinting at advanced technological integration. The image should be high-resolution and vibrant, with a professional aesthetic suitable for a tech-focused YouTube Short.'}, {'start': '00:43', 'duration': '00:01', 'text': 'Drop your optimization secrets below.', 'url': 'output/images/segment_9.png', 'source': 'Gemini', 'prompt': 'Vertical (9:16) image depicting a stylized cricket stadium crowd scene, India versus Pakistan 2025 Champions Trophy vibe. Focus on vibrant, celebrating fans: one half wearing Indian cricket jerseys (blue), the other half Pakistani jerseys (green). Emphasize dynamic movement: arms raised in victory, flags waving, confetti subtly raining down. Lighting should be dramatic, stadium spotlights creating strong contrasts and highlighting the energy of the crowd. Mood: Ecstatic, passionate, competitive. Style: Modern, semi-realistic, slightly painterly with bold colors. Composition: A slightly low angle, capturing the scale of the crowd and emphasizing the feeling of being immersed in the excitement. Vivid colors, high resolution, professional aesthetic, no text. The overall feeling should be one of intense rivalry and sporting celebration.'}]}
    result = create_video_with_overlays(state)
    print(result)
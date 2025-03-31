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
            height_scale = shorts_height / img_clip.h  # Use full screen height for scaling
            
            # Use the smaller scaling factor to ensure the entire image fits
            scale_factor = min(width_scale, height_scale)
            
            # Resize the image
            img_clip = img_clip.resize(scale_factor)
            
            # Center the image horizontally and vertically
            x_center = (shorts_width - img_clip.w) / 2
            y_center = (shorts_height - img_clip.h) / 2
            
            # Create a full screen background
            img_bg = ColorClip(size=(shorts_width, shorts_height), color=(0, 0, 0))
            img_bg = img_bg.set_duration(img_duration)
            
            # Add zoom-out effect to the image
            # Start with a larger size and zoom out to normal size
            def zoom_effect(t):
                # Calculate zoom factor: start at 2.5x zoom and end at 1.0x
                # Use the first 0.3 seconds for the zoom effect (extremely fast zoom)
                zoom_duration = min(0.3, img_duration * 0.15)  # Use at most 15% of duration for zoom
                
                if t < zoom_duration:
                    # Aggressive non-linear interpolation for much faster initial zoom
                    progress = t / zoom_duration
                    # Use a cubic function for very rapid initial movement
                    zoom_factor = 2.5 - (1.5 * (progress * progress * progress))
                    return zoom_factor
                else:
                    # After zoom duration, maintain normal size
                    return 1.0
            
            # Add vibration effect to the image
            def vibration_effect(t):
                # Further reduced amplitude vibration
                base_amplitude = 2.5  # Reduced from 4 to 2.5
                
                # Create subtle, non-uniform vibrations
                # Use different frequencies and random factors
                t_mod = t * 6  # Slower time scale (reduced from 8)
                
                # Create gentle abrupt changes
                abrupt_factor = 0.8 + 0.1 * np.sin(t_mod * 5.0)  # Reduced variation
                
                # Random spikes in movement (less frequent and smaller)
                if (t_mod % 1.0) < 0.1:  # Create sudden movements only 10% of the time
                    x_spike = base_amplitude * 1.0  # Reduced spike multiplier
                    y_spike = base_amplitude * 0.8  # Reduced spike multiplier
                else:
                    x_spike = 0
                    y_spike = 0
                
                # Combine smooth and abrupt movements
                x_offset = np.sin(t_mod * 4.0 + 0.5) * base_amplitude * abrupt_factor + x_spike
                y_offset = np.cos(t_mod * 5.0 + 1.5) * base_amplitude * abrupt_factor + y_spike
                
                return (x_offset, y_offset)
            
            # Apply the zoom effect to the image clip
            zoomed_img = img_clip.resize(lambda t: zoom_effect(t))
            
            # Recalculate position for the zoomed image to keep it centered and add vibration
            def position_function(t):
                zoom = zoom_effect(t)
                vib_x, vib_y = vibration_effect(t)
                
                # Calculate new dimensions based on zoom factor
                new_width = img_clip.w * zoom
                new_height = img_clip.h * zoom
                
                # Use the pre-calculated center positions and adjust for zoom
                # This ensures the image stays centered during zoom and vibration
                new_x = x_center - ((new_width - img_clip.w) / 2) + vib_x
                new_y = y_center - ((new_height - img_clip.h) / 2) + vib_y
                
                return (new_x, new_y)
            
            # Create the final positioned image with background
            positioned_img = CompositeVideoClip([
                img_bg,
                zoomed_img.set_position(position_function)
            ])
            
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
    state["bg_music_path"] = "assets/bg_music2.mp3"
    
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
        
        # Create image overlays using the local image paths from images_manifest
        # Create these first so they appear behind the text
        image_overlays = create_image_overlays(
            state["images_manifest"], 
            video_duration,
            shorts_width,
            shorts_height
        )
        
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
        
        # Add background music if provided
        final_audio = audio
        if "bg_music_path" in state and state["bg_music_path"] and os.path.exists(state["bg_music_path"]):
            try:
                # Load background music
                bg_music = AudioFileClip(state["bg_music_path"])
                
                # Set the volume to be low (40% of original)
                bg_music = bg_music.volumex(0.4)
                
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
    state = {'topic': 'The mysterious meeting between Krishna and Karna before the war', 'script': {'videoScript': [{'start': '00:00', 'duration': '00:04', 'text': 'Are yaar, Mahabharat ki sabse mysterious meeting ke bare mein sunoge?'}, {'start': '00:04', 'duration': '00:07', 'text': 'Krishna aur Karna, ek secret mulaqat, yudh se theek pehle.'}, {'start': '00:08', 'duration': '00:03', 'text': 'Main bahut excited hoon aapko yeh batane ke liye.'}, {'start': '00:11', 'duration': '00:04', 'text': 'Socho zara, Krishna ne Karna ko sach bataya, uska janm ka raaz,'}, {'start': '00:15', 'duration': '00:04', 'text': 'ki woh Kunti ka beta hai, Pandavon ka bada bhai. Kya offer diya Krishna ne?'}, {'start': '00:19', 'duration': '00:04', 'text': 'Poora rajya. Yudhishthira bhi taiyar tha taaj dene ko.'}, {'start': '00:23', 'duration': '00:05', 'text': 'Imagine karo, Karna raja banta, toh kya hota? Lekin Karna ne mana kar diya.'}, {'start': '00:28', 'duration': '00:05', 'text': 'Usne Duryodhana ki dosti nahi todi. Loyalty ya Dharma? Dot kya chuna Karna ne?'}, {'start': '00:33', 'duration': '00:04', 'text': 'Dot aur phir kuch aisa hua jo Mahabharat ka rukh badal gaya.'}, {'start': '00:37', 'duration': '00:03', 'text': 'Kya aapko lagta hai Karna ne sahi kiya?'}, {'start': '00:40', 'duration': '00:04', 'text': 'Comment mein batao. Aur aise hi amazing facts ke liye follow karna mat bhoolna.'}], 'totalDuration': '00:44'}, 'title': "🤯 Secret Mahabharat Meeting! Krishna's Shocking Offer!", 'description': "Did Karna make the right choice? 🤔 Krishna's secret reveal! 🔥 Raj or loyalty? Comment your thoughts! 👇 #Mahabharat #Krishna #Karna #Mythology #Shorts Follow for more! ❤️", 'thumbnail_url': 'https://avatars.githubusercontent.com/u/91617309?v=4', 'audio_path': 'output/audios/audio_1743446984.780353.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:04', 'text': 'Are yaar, Mahabharat ki sabse mysterious meeting ke bare mein sunoge?', 'url': 'output/images/segment_1.png', 'source': 'Gemini', 'prompt': "Vertical image, 1080x1920 resolution. A clandestine meeting between Krishna and Karna on a serene, yet subtly ominous, riverbank just before dusk. Karna, regal and conflicted, stands facing Krishna, who emanates wisdom and calm. Karna is adorned in golden armor, slightly tarnished with pre-battle anxiety. His expression is a complex blend of defiance and sorrow. Krishna, dressed in simple yellow robes, stands with a gentle, knowing smile. The Yamuna River flows calmly in the foreground, reflecting the fading sunlight.\n\nCinematic lighting with a strong rim light highlighting Karna's silhouette against the darkening sky, emphasizing his inner turmoil. Volumetric lighting pierces through the leaves of a nearby banyan tree, casting dappled shadows on Krishna's face, suggesting divine knowledge. Ultra high-quality, vibrant imagery with clear, sharp focus on both figures. Modern, professional aesthetic.\n\nHyper-realistic digital art style, 8K resolution, crystal clear details. Strategic depth of field blurs the background, focusing attention on the interaction between Krishna and Karna. Rich color grading with a complementary color scheme of warm golds and yellows contrasting with cool blues and purples of the twilight sky. HDR-like contrast emphasizing the emotional intensity of the moment. Photorealistic textures and materials: the gleam of Karna's armor, the fine weave of Krishna's robes, the rough bark of the banyan tree, the ripples on the river's surface – all rendered with microscopic detail.\n\nDynamic composition with a strong focal point on the faces of Krishna and Karna, creating a visual flow that guides the viewer's eye. Subtle lens effects, such as slight chromatic aberration around the brightest highlights and a faint lens flare from the setting sun, enhance realism. Reflections of the figures in the river, realistic shadows cast by the setting sun, and ambient occlusion create a sense of dimensional realism. Ray-traced lighting effects for photorealistic rendering of light and shadow. Atmospheric elements like subtle particles of dust motes floating in the air and volumetric fog clinging to the river's surface add depth and mystery."}, {'start': '00:04', 'duration': '00:07', 'text': 'Krishna aur Karna, ek secret mulaqat, yudh se theek pehle.', 'url': 'output/images/segment_2.png', 'source': 'Gemini', 'prompt': "A vertical (1080x1920) hyper-realistic digital painting depicting a secret meeting between Krishna and Karna just before the Kurukshetra war. The scene is set at dusk on the banks of the Yamuna River. Krishna, with his serene and knowing expression, stands slightly taller, adorned in vibrant yellow silk dhoti and peacock feather crown, though slightly weathered, suggesting a long journey. Karna, regal and conflicted, stands opposite him, clad in golden armor reflecting the fading sunlight, his face etched with a mixture of determination and sorrow.\n\nThe river flows calmly in the background, reflecting the orange and purple hues of the setting sun. Volumetric fog hangs low to the water, adding an ethereal quality. Sparse trees line the riverbank, their silhouettes sharp against the colorful sky. The composition should be dynamic, with a strong focal point on the faces of Krishna and Karna, their eyes meeting with intense unspoken understanding.\n\nLighting is crucial: use rim lighting to separate the figures from the background and volumetric lighting to enhance the atmosphere. The primary light source is the setting sun, casting long, dramatic shadows. Implement subtle lens flare and chromatic aberration effects around the brightest highlights.\n\nEmploy ray-traced lighting to render realistic reflections on Karna's armor and the river surface. Use depth of field to blur the background slightly, drawing attention to the two figures.\n\nColor grade the image with a complementary color scheme, using warm oranges and yellows contrasted with cooler blues and purples in the sky and river. HDR-like contrast should be applied to enhance the dynamic range.\n\nRender photorealistic textures and materials, paying attention to microscopic details in the silk of Krishna’s dhoti, the metal of Karna’s armor, and the bark of the trees. Ambient occlusion should be used to ground the figures in the scene and enhance the sense of depth.\n\nAdd subtle particles of dust or pollen floating in the air, catching the light and adding to the atmospheric depth. The overall style should be a modern, professional aesthetic, suitable for tech content, with crystal clear details and 8K resolution. Ensure a captivating and visually stunning image that perfectly captures the tension and significance of this pivotal moment. Avoid any text or words."}, {'start': '00:08', 'duration': '00:03', 'text': 'Main bahut excited hoon aapko yeh batane ke liye.', 'url': 'output/images/segment_3.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 portrait. Capture a clandestine meeting between Krishna and Karna on the banks of a darkened river, moments before the Kurukshetra war. Krishna, radiating a divine aura, stands to the left, clad in simple saffron robes, a gentle smile playing on his lips. His skin possesses a subtle, otherworldly glow. Karna, a towering warrior in battle-worn golden armor, stands opposite him, his face etched with conflict and inner turmoil, illuminated by flickering torchlight. The river, the Yamuna, reflects the fiery light of the torches, creating shimmering, distorted patterns.\n\nThe composition should employ a strong leading line from the bottom right to the top left, drawing the eye towards the faces of Krishna and Karna. Use a shallow depth of field, blurring the background elements like the distant battlefield campfires and the silhouettes of observing soldiers. The primary light source is the warm, intense glow of two torches held by unseen figures on either side, creating dramatic rim lighting on both characters, highlighting the edges of their forms and separating them from the dark background. Volumetric lighting should emanate from the torchlight, creating visible beams cutting through the atmospheric haze.\n\nThe style should be hyper-realistic digital art, rendered in 8K resolution with crystal clear detail. Focus on photorealistic textures: the rough weave of Krishna's robes, the intricate details of Karna's armor, the wetness of the riverbank. Implement subtle chromatic aberration and lens flare around the torchlight for added realism.\n\nEmploy rich color grading with a complementary color scheme of warm oranges and cool blues. HDR-like contrast should emphasize the dramatic lighting and shadow play. Utilize ray-traced lighting effects to accurately simulate light bouncing off surfaces, creating realistic reflections on Karna's armor and the water. Incorporate subtle volumetric fog near the river surface for added depth and atmosphere. Add fine particles of dust and embers floating in the torchlight. Use ambient occlusion to ground the characters in the scene and enhance the sense of dimensionality. Ensure clear, sharp focus on the faces of Krishna and Karna, capturing their expressions with microscopic detail. No text or words are to be visible in the image."}, {'start': '00:11', 'duration': '00:04', 'text': 'Socho zara, Krishna ne Karna ko sach bataya, uska janm ka raaz,', 'url': 'output/images/segment_4.png', 'source': 'Gemini', 'prompt': "Vertical image, 1080x1920, Ultra high-quality 8K resolution. Hyper-realistic digital art. Krishna and Karna meeting in a secluded, ancient Indian forest clearing. Krishna, depicted as a wise and compassionate elder statesman, stands facing Karna, a noble warrior burdened by his secret lineage. Karna is kneeling respectfully before Krishna. The scene is bathed in the warm, golden light of the setting sun filtering through the dense foliage, creating a dramatic and ethereal atmosphere.\n\nKrishna is adorned in rich, saffron-colored robes with intricate gold embroidery. His skin is a deep, radiant blue. His face is serene, etched with lines of wisdom and understanding. He has a gentle, almost sad, expression. Karna is depicted as a muscular and imposing figure, wearing battle-worn but regal golden armor. His face is etched with inner turmoil and conflict. His eyes are downcast, reflecting his humility and respect.\n\nThe forest floor is covered in fallen leaves and moss, illuminated by shafts of sunlight. Volumetric fog hangs low to the ground, adding depth and mystique. The background features towering trees with intricately detailed bark and leaves, receding into the distance with a shallow depth of field. Ray-traced lighting creates realistic reflections and shadows throughout the scene. Rim lighting highlights the contours of Krishna and Karna, separating them from the background.\n\nSubtle chromatic aberration adds a touch of realism around the edges of the bright light sources. Lens flare is subtly present where the sunlight breaks through the trees. Photorealistic textures and materials are used for the clothing, armor, and environment, with microscopic details visible upon close inspection. Dynamic composition leads the viewer's eye from Krishna to Karna, emphasizing their interaction.\n\nRich color grading employs complementary color schemes, with warm golds and oranges contrasting against the cool greens of the forest. HDR-like contrast enhances the overall vibrancy and impact. Ambient occlusion creates realistic shadows and depth around the characters and objects. Particles of dust and pollen float in the air, catching the sunlight and adding to the atmospheric depth. Avoid any text or words in the image."}, {'start': '00:15', 'duration': '00:04', 'text': 'ki woh Kunti ka beta hai, Pandavon ka bada bhai. Kya offer diya Krishna ne?', 'url': 'output/images/segment_5.png', 'source': 'Gemini', 'prompt': "Vertical portrait image, 1080x1920, ultra-high quality 8K resolution. Hyper-realistic digital art depicting a clandestine meeting at dusk. Karna, a noble warrior with golden armor subtly damaged, stands facing Krishna. Krishna, serene and wise, is positioned slightly to Karna's left. Rim lighting highlights the contours of Karna's face and armor, separating him from the background. Volumetric lighting streams through the trees, illuminating dust motes in the air. The mood is contemplative and tense. Hyper-realistic style with crystal-clear details in 8K resolution. The grove features lush, vibrant foliage in shades of emerald and gold, with photorealistic textures of bark and leaves. Strategic depth of field blurs the background, focusing attention on the two figures. Rich color grading with a complementary color scheme of warm golds and cool blues, HDR-like contrast. Photorealistic textures and materials, showing microscopic details in the weave of Karna's armor and the texture of Krishna's skin. Dynamic composition with Karna's face as the strong focal point, leading the eye towards Krishna. Subtle lens effects like chromatic aberration around the edges of bright highlights and a soft lens flare emanating from the setting sun. Reflections of the sunlight glint off Karna's armor. Deep shadows are cast by the trees, enhancing the sense of depth. Ambient occlusion creates realistic contact shadows. Ray-traced lighting effects create photorealistic rendering of light and shadow. Atmospheric elements like subtle volumetric fog near the ground add depth and mystery. The overall aesthetic is modern, professional, and cinematic, suitable for a tech-savvy audience. Avoid any text or words."}, {'start': '00:19', 'duration': '00:04', 'text': 'Poora rajya. Yudhishthira bhi taiyar tha taaj dene ko.', 'url': 'output/images/segment_6.png', 'source': 'Gemini', 'prompt': "A vertical (1080x1920) ultra-high-quality, 8K hyper-realistic digital art image depicting a pivotal moment before a great war. The scene features Karna, a noble warrior with sun-kissed skin and intricately detailed golden armor reflecting the setting sun, kneeling respectfully before Krishna, a divine figure radiating calm power. Krishna, draped in flowing saffron robes with subtle embroidery, stands tall and compassionate. The backdrop is a grand, yet desolate, throne room within a palace. Hints of past glory are visible in the architecture, but a sense of impending doom permeates the air.\n\nThe lighting should be dramatic and cinematic. Use rim lighting to highlight Karna's silhouette against a slightly darker background. Employ volumetric lighting to create god rays streaming through arched windows, illuminating dust particles suspended in the air, adding depth and atmosphere. A key light focuses on Krishna's face, emphasizing his serene expression.\n\nThe composition is dynamic, leading the eye from Karna's kneeling figure to Krishna's face. Depth of field should be shallow, blurring the background and focusing attention on the two figures. Subtle chromatic aberration and lens flare can be added around the light sources for realism.\n\nThe style is photorealistic with microscopic details in textures and materials. The armor should have realistic scratches and wear, the robes should have subtle folds and imperfections, and the skin should show pores and fine lines. Reflections should be visible on polished surfaces, and shadows should be accurately cast, enhancing the three-dimensionality of the scene. Ambient occlusion should be used to ground the figures in the environment.\n\nColor grading should utilize a complementary color scheme, perhaps oranges and blues, with HDR-like contrast to make the image pop. Ray-traced lighting effects should be employed to create photorealistic reflections and refractions. Subtle volumetric fog should be added near the floor to enhance the sense of depth and atmosphere. Avoid any text or words. The overall mood is somber, contemplative, and filled with unspoken tension. This image should convey the gravity of the choices being made before a world-altering conflict."}, {'start': '00:23', 'duration': '00:05', 'text': 'Imagine karo, Karna raja banta, toh kya hota? Lekin Karna ne mana kar diya.', 'url': 'output/images/segment_7.png', 'source': 'Gemini', 'prompt': "A hyper-realistic digital art image, vertical orientation, 1080x1920, depicting a pivotal moment: Karna refusing kingship. The scene is set in a richly decorated tent, bathed in the warm, golden light of the setting sun filtering through intricate fabric canopies. Karna, a noble warrior with striking features and a powerful physique, stands tall and resolute. He is adorned in golden armor, subtly reflecting the sunlight, with intricate carvings and embellishments visible at a microscopic level. His expression is a complex mix of humility and unwavering determination, captured with crystal-clear clarity. Before him kneels an attendant offering a jeweled crown on a velvet cushion. The attendant's face is partially obscured by shadow, hinting at their subservient role.\n\nThe tent is filled with opulent details – Persian rugs with intricate patterns, ornate golden lamps casting warm light, and silk cushions scattered around. Volumetric fog subtly hangs in the air, catching the light and adding depth. Ray-traced lighting enhances the realism, creating soft shadows and vibrant reflections on the metallic surfaces. Rim lighting highlights Karna's form, separating him from the background.\n\nThe overall mood is solemn and introspective. The color scheme is dominated by warm golds, reds, and browns, creating a sense of richness and history. HDR-like contrast enhances the details and adds a cinematic feel.\n\nA shallow depth of field focuses sharply on Karna's face and the offered crown, blurring the background and emphasizing the importance of the moment. Subtle chromatic aberration and lens flare add a touch of realism. The image is rendered in 8K resolution with photorealistic textures and materials. Reflections on Karna's armor and the attendant's clothing, along with ambient occlusion, create a sense of dimensional realism. Particle effects, like dust motes dancing in the sunlight, add to the atmosphere. The dynamic composition draws the eye towards Karna, creating a strong focal point and visual flow."}, {'start': '00:28', 'duration': '00:05', 'text': 'Usne Duryodhana ki dosti nahi todi. Loyalty ya Dharma? Dot kya chuna Karna ne?', 'url': 'output/images/segment_8.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 digital painting. Krishna and Karna in a secluded, mystical grove at sunset. Karna, depicted as a powerful warrior with golden armor subtly reflecting the setting sun, stands facing Krishna. Krishna, serene and wise, is positioned slightly to Karna's left. Rim lighting highlights the contours of Karna's face and armor, separating him from the background. Volumetric lighting streams through the trees, illuminating dust motes in the air. The mood is contemplative and tense. Hyper-realistic style with crystal-clear details in 8K resolution. The grove features lush, vibrant foliage in shades of emerald and gold, with photorealistic textures of bark and leaves. Strategic depth of field blurs the background, focusing attention on the two figures. Rich color grading with a complementary color scheme of warm golds and cool blues, HDR-like contrast. Photorealistic textures and materials, showing microscopic details in the weave of Karna's armor and the texture of Krishna's skin. Dynamic composition with Karna's face as the strong focal point, leading the eye towards Krishna. Subtle lens effects like chromatic aberration around the edges of bright highlights and a soft lens flare emanating from the setting sun. Reflections of the sunlight glint off Karna's armor. Deep shadows are cast by the trees, enhancing the sense of depth. Ambient occlusion creates realistic contact shadows. Ray-traced lighting effects create photorealistic rendering of light and shadow. Atmospheric elements like subtle volumetric fog near the ground add depth and mystery. The overall aesthetic is modern, professional, and cinematic, suitable for a tech-savvy audience. Avoid any text or words."}, {'start': '00:33', 'duration': '00:04', 'text': 'Dot aur phir kuch aisa hua jo Mahabharat ka rukh badal gaya.', 'url': 'output/images/segment_9.png', 'source': 'Gemini', 'prompt': "A vertical (1080x1920) hyper-realistic digital painting depicting a clandestine meeting between Krishna and Karna on the banks of a tranquil river at twilight. Krishna, radiating a serene, almost ethereal glow, stands facing Karna, whose face is etched with a mixture of conflict and resignation. Krishna is dressed in simple yet regal yellow robes, meticulously detailed with subtle embroidery that catches the fading light. Karna, clad in his golden armor, stands rigidly, the polished metal reflecting the somber sunset hues.\n\nThe river reflects the fiery sky, mirroring the tension in the air. Volumetric fog hangs low over the water, adding depth and mystery to the scene. Rim lighting highlights the contours of their faces and armor, separating them from the background. A single, ancient banyan tree looms behind Karna, its gnarled roots reaching towards the riverbank, symbolizing the weight of destiny.\n\nThe composition uses a shallow depth of field, blurring the background and focusing attention on the two figures. Subtle chromatic aberration around the brightest highlights adds a touch of realism. Ray-traced lighting creates realistic reflections on the water and armor. Particles of dust and pollen float in the air, illuminated by the setting sun.\n\nThe color palette is dominated by warm oranges, reds, and purples of the sunset, contrasted by the cool blues and greens of the river and foliage. HDR-like contrast enhances the dramatic mood. Photorealistic textures are crucial - every detail, from the weave of Krishna's robes to the scratches on Karna's armor, should be visible. Ambient occlusion grounds the figures in the environment, creating a sense of dimensional realism. A subtle lens flare emanates from the setting sun, adding a cinematic touch. 8K resolution ensures crystal-clear details. The overall style is modern, professional, and evocative of a pivotal moment in the Mahabharata."}, {'start': '00:37', 'duration': '00:03', 'text': 'Kya aapko lagta hai Karna ne sahi kiya?', 'url': 'output/images/segment_10.png', 'source': 'Gemini', 'prompt': "A hyper-realistic digital painting of a clandestine meeting between Krishna and Karna before the Mahabharata war. Vertical format, 1080x1920 resolution. Krishna, radiating divine composure and intelligence, stands on slightly higher ground. He is depicted with dark skin, adorned with subtle gold jewelry, and wearing a saffron dhoti. Karna, the tragic hero, stands before him, his face etched with inner turmoil, nobility, and a hint of desperation. He's clad in golden armor, slightly worn from battle, emphasizing his warrior status. The backdrop is a serene, yet somber forest clearing bathed in the pre-dawn light. Volumetric fog gently swirls around their feet, adding to the mystique. Rim lighting highlights both figures, separating them from the background. A single shaft of sunlight pierces through the dense foliage, illuminating Krishna's face and creating a dramatic focal point. The ground is covered with detailed photorealistic textures of leaves, rocks, and roots. Use strategic depth of field; Krishna is in sharp focus, while the background is slightly blurred. Ray-traced lighting creates realistic shadows and reflections. Subtle chromatic aberration around the edges of the bright sunlight adds a cinematic touch. Rich color grading with a complementary color scheme of warm gold and cool blues. HDR-like contrast enhances the visual impact. Photorealistic textures of skin, fabric, and metal with microscopic details. Dynamic composition with a strong focal point on the exchange between their eyes. Subtle lens flare emanating from the sunlight. Ambient occlusion defines the forms and adds depth. Incorporate particles of dust motes floating in the sunbeam. 8K resolution, ultra-high quality, crystal clear details. Modern, professional aesthetic suitable for tech content. No text or words in the image."}, {'start': '00:40', 'duration': '00:04', 'text': 'Comment mein batao. Aur aise hi amazing facts ke liye follow karna mat bhoolna.', 'url': 'output/images/segment_11.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 image. Krishna and Karna's secret meeting before the Kurukshetra war. Depict a secluded, rocky area near a tranquil riverbank at dusk. Krishna, radiant with divine light but appearing as a humble charioteer in simple yellow robes, stands facing Karna. Karna, a powerful warrior adorned in golden armor reflecting the setting sun, kneels respectfully before Krishna. Focus sharply on their faces, conveying a sense of somber understanding and unspoken destiny. Krishna's expression is serene yet carries a hint of melancholy, while Karna's displays resolute acceptance. Use rim lighting to highlight their silhouettes against the darkening sky and volumetric lighting to accentuate the dust motes dancing in the air. Style: Hyper-realistic digital art, 8K resolution, photorealistic textures and materials with microscopic detail on their clothing and skin. Composition: Dynamic composition with a strong focal point on the faces of Krishna and Karna. Use depth of field to blur the background river and rocks, drawing the viewer's eye to the subjects. Color grading: Rich, complementary color scheme of warm golds, oranges, and deep blues, HDR-like contrast. Lighting: Professional cinematic lighting with ray-traced effects, reflections on Karna's armor, realistic shadows and ambient occlusion. Subtle lens effects: slight chromatic aberration around the edges of bright objects, a delicate lens flare catching the setting sun. Atmospheric elements: subtle volumetric fog near the river's surface, particles of dust floating in the air. Modern, professional aesthetic suitable for tech content. The scene should feel emotionally resonant and visually captivating, avoiding any text or words."}]}
    result = create_video_with_overlays(state)
    print(result)
import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import os
import json
import base64
import mimetypes
from google import genai
from google.genai import types

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
)

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


def generate_images(state):
    print("Generating images...")
    
    # Function to generate images using Gemini
    def generate_image_with_gemini(prompt, file_name):
        """Generate images using Gemini's image generation capabilities"""
        try:
            client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY"),
            )

            model = "gemini-2.0-flash-exp-image-generation"
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            generate_content_config = types.GenerateContentConfig(
                response_modalities=[
                    "image",
                    "text",
                ],
                response_mime_type="text/plain",
            )

            image_saved = False
            full_path = ""
            
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
                if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                    continue
                if chunk.candidates[0].content.parts[0].inline_data:
                    inline_data = chunk.candidates[0].content.parts[0].inline_data
                    file_extension = mimetypes.guess_extension(inline_data.mime_type)
                    full_path = f"{file_name}{file_extension}"
                    
                    # Save the binary file
                    with open(full_path, "wb") as f:
                        f.write(inline_data.data)
                    
                    print(
                        f"Image of mime type {inline_data.mime_type} saved to: {full_path}"
                    )
                    image_saved = True
                else:
                    print(chunk.text)
            
            return full_path if image_saved else None
        except Exception as e:
            print(f"Error generating image with Gemini: {str(e)}")
            return None
    
    # Ensure output directory exists
    os.makedirs("output/images", exist_ok=True)
    
    # Template for generating optimized image prompts
    search_prompt = ChatPromptTemplate.from_template(
        """Create a detailed image generation prompt based on this video segment text for a YouTube Shorts video (vertical format).
        
        Video segment text: {segment_text}
        Video topic: {topic}
        
        Create an image generation prompt that:
        1. Is highly detailed and descriptive (at least 50 words)
        2. Specifies a vertical/portrait orientation with 1080x1620 dimensions
        3. Includes specific visual elements that would be engaging for YouTube Shorts
        4. Describes lighting, mood, style, and composition
        5. Requests high-quality, vibrant imagery with clear subjects
        6. Specifies a modern, professional aesthetic suitable for tech content
        7. Avoids any text or words in the image
        
        The prompt should be optimized for AI image generation to create visually stunning, 
        attention-grabbing images that perfectly complement the video segment.
        
        Return only the image generation prompt with no additional formatting."""
    )
    
    # Create chain for prompt generation
    prompt_chain = search_prompt | llm | StrOutputParser()
    
    images_manifest = []
    for i, segment in enumerate(state["script"]["videoScript"]):
        # Generate image prompt for this segment
        image_prompt = prompt_chain.invoke({"segment_text": segment['text'], "topic": state["topic"]})
        image_prompt = image_prompt.strip()
        print(f"\n\nGenerated image prompt: {image_prompt}")
        
        # Generate image with Gemini
        image_path = f"output/images/segment_{i+1}"
        full_image_path = generate_image_with_gemini(image_prompt, image_path)
        
        if full_image_path:
            print(f"Generated image for segment {i+1} at {full_image_path}")
            
            # Add to manifest
            images_manifest.append({
                "start": segment["start"],
                "duration": segment["duration"],
                "text": segment["text"],
                "url": full_image_path,  # Store local path
                "source": "Gemini",
                "prompt": image_prompt
            })
        else:
            print(f"Failed to generate image for segment {i+1}, using placeholder")
            # Use placeholder
            images_manifest.append({
                "start": segment["start"],
                "duration": segment["duration"],
                "text": segment["text"],
                "url": "output/images/placeholder.jpg"
            })
    
    print("Images manifest:", images_manifest)
    return {"images_manifest": images_manifest}
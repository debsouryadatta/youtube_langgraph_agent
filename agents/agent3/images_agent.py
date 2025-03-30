import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import os
import json

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
)

# Unsplash API credentials
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

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
    
    # Function to fetch images from Unsplash API
    def fetch_unsplash_images(query, num_images=1):
        """Fetch images from Unsplash API optimized for YouTube Shorts (vertical)"""
        # Ensure the API key exists
        api_key = os.getenv('UNSPLASH_API_KEY')
        if not api_key:
            raise ValueError("Unsplash API key is missing. Please set the UNSPLASH_API_KEY environment variable.")
        
        # YouTube Shorts dimensions: portrait orientation
        orientation = "portrait"
        if "vertical" not in query.lower():
            query = f"{query} vertical"

        url = f"https://api.unsplash.com/search/photos?per_page={num_images}&query={query}&client_id={api_key}&orientation={orientation}&w=1080&h=1920"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                image_urls = [img["urls"]["small_s3"] for img in data["results"]]
                return image_urls
            else:
                print(f"No results found for query: {query}")
                return []
        except Exception as e:
            print(f"Error fetching from Unsplash API: {str(e)}")
            return []
    
    # Ensure output directory exists
    os.makedirs("output/images", exist_ok=True)
    
    # Template for generating optimized search queries
    search_prompt = ChatPromptTemplate.from_template(
        """Create an image search query for Unsplash based on this video segment text for a YouTube Shorts video (vertical format).
        
        Video segment text: {segment_text}
        Video topic: {topic}
        
        Create a search query that:
        1. Is concise (3-5 key words)
        2. Focuses on the main visual subject that would be engaging for YouTube Shorts
        3. Specifies high quality, vibrant imagery suitable for vertical phone viewing
        4. Will result in vertically-oriented photos
        
        Return only the search query text with no additional formatting."""
    )
    
    # Create chain for search term generation
    search_chain = search_prompt | llm | StrOutputParser()
    
    images_manifest = []
    for i, segment in enumerate(state["script"]["videoScript"]):
        # Generate search term for this segment
        search_term = search_chain.invoke({"segment_text": segment['text'], "topic": state["topic"]})
        search_term = search_term.strip()
        print(f"Generated search term: {search_term}")
        
        # Fetch image URLs from Unsplash
        image_urls = fetch_unsplash_images(search_term)
        
        if not image_urls:
            print(f"No images found for segment {i+1}, trying alternative search...")
            # Try a more generic search if specific one fails
            fallback_search = "vertical professional " + state["topic"][:30]
            image_urls = fetch_unsplash_images(fallback_search)
        
        if image_urls:
            # Download the image
            image_path = f"output/images/segment_{i+1}.jpg"
            try:
                response = requests.get(image_urls[0], timeout=10)
                response.raise_for_status()
                
                with open(image_path, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded image for segment {i+1} to {image_path}")
                
                # Add attribution info as required by Unsplash API guidelines
                images_manifest.append({
                    "start": segment["start"],
                    "duration": segment["duration"],
                    "text": segment["text"],
                    "url": image_path,  # Store local path
                    "source": "Unsplash",
                    "search_term": search_term
                })
            except Exception as e:
                print(f"Failed to download image for segment {i+1}: {str(e)}")
                # Use a placeholder or fallback image
                images_manifest.append({
                    "start": segment["start"],
                    "duration": segment["duration"],
                    "text": segment["text"],
                    "url": "output/images/placeholder.jpg"  # Default placeholder
                })
        else:
            print(f"No images found for segment {i+1}, using placeholder")
            # Use placeholder
            images_manifest.append({
                "start": segment["start"],
                "duration": segment["duration"],
                "text": segment["text"],
                "url": "output/images/placeholder.jpg"
            })
    
    print("Images manifest:", images_manifest)
    return {"images_manifest": images_manifest}
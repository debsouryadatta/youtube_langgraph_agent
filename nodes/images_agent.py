import requests
from langchain_core.prompts import ChatPromptTemplate
from bs4 import BeautifulSoup
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import os
import re

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
    
    # Process script segments programmatically instead of using LLM
    original_segments = state["script"]["videoScript"]
    total_duration_str = state["script"]["totalDuration"]
    
    # Convert the total duration to seconds
    total_duration_seconds = timestamp_to_seconds(total_duration_str)
    
    # Combine all text from original segments
    all_text = " ".join([segment["text"] for segment in original_segments])
    
    # Calculate how many 4-second segments we need
    segment_duration = 4  # seconds
    num_segments = max(1, int(total_duration_seconds / segment_duration))
    
    # Calculate characters per segment based on total text length divided by number of segments
    chars_per_segment = max(1, len(all_text) // num_segments)
    
    # Create new segments
    new_segments = []
    start_time = 0
    
    for i in range(num_segments):
        # For the last segment, use all remaining text
        if i == num_segments - 1:
            segment_text = all_text[i * chars_per_segment:]
            segment_duration = total_duration_seconds - start_time
        else:
            segment_text = all_text[i * chars_per_segment:(i + 1) * chars_per_segment]
            segment_duration = 4  # fixed 4 seconds per segment
        
        # Format times as MM:SS
        start_str = f"{int(start_time // 60):02d}:{int(start_time % 60):02d}"
        duration_str = f"{int(segment_duration // 60):02d}:{int(segment_duration % 60):02d}"
        
        new_segments.append({
            "start": start_str,
            "duration": duration_str,
            "text": segment_text.strip()
        })
        
        start_time += segment_duration
    
    # Create result with the same structure as expected from the LLM
    result = {
        "videoScript": new_segments,
        "totalDuration": total_duration_str
    }
    
        # Create Google image search function
    def fetch_image_urls(query, num_images=1):
        # Prepare keywords for URL encoding
        query_for_url = query.replace(" ", "+")
        url = f"https://www.google.com/search?q={query_for_url}&tbm=isch"
        
        # Use a common User-Agent header to mimic a real browser
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/103.0.5060.114 Safari/537.36")
        }
        
        # Fetch the search result page
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Request failed with status code {response.status_code}")
            return []
        
        # Parse the page using BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        image_urls = []
        
        # First approach: look for <img> tags with src containing http
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and src.startswith("http"):
                image_urls.append(src)
            if len(image_urls) >= num_images:
                break

        # Fallback: use regex to extract jpg URLs from the raw HTML if not enough URLs found
        if len(image_urls) < num_images:
            regex_urls = re.findall(r'["\'](https?://[^"\']+?\.jpg)["\']', response.text)
            for url in regex_urls:
                if url not in image_urls:
                    image_urls.append(url)
                if len(image_urls) >= num_images:
                    break
        return image_urls[:num_images]
    
    
    # Ensure output directory exists
    os.makedirs("output/images", exist_ok=True)
    
    # Rest of the function remains the same as before
    search_prompt = ChatPromptTemplate.from_template(
        """Create a short and focused image search query based on this video segment text and the topic of the video.
        The query should directly relate to the core topic being discussed.
        
        Video segment text: {segment_text}
        Video topic: {topic}
        
        Create a search query that:
        1. Uses 3-5 key words
        2. Focuses on the main subject
        3. Describes a clear, relevant visual
        
        Return only the search query text with no additional formatting."""
    )
    
    # Create chain for search term generation
    search_chain = search_prompt | llm | StrOutputParser()
    
    images_manifest = []
    for i, segment in enumerate(state["script"]["videoScript"]):
        # Generate search term for this segment
        search_term = search_chain.invoke({"segment_text": segment['text'], "topic": state["topic"]})
        search_term = search_term.strip() + " vertical high quality"
        print(f"Generated search term: {search_term}")
        
        # Fetch image URLs
        image_urls = fetch_image_urls(search_term)
        
        if not image_urls:
            print(f"No images found for segment {i+1}, trying alternative search...")
            # Try a more generic search if specific one fails
            fallback_search = search_chain.invoke({"segment_text": "professional high quality " + segment['text'][:30]})
            image_urls = fetch_image_urls(fallback_search + " vertical")
        
        if image_urls:
            # Download the image
            image_path = f"output/images/segment_{i+1}.jpg"
            try:
                response = requests.get(image_urls[0], timeout=10)
                response.raise_for_status()
                
                with open(image_path, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded image for segment {i+1} to {image_path}")
                
                images_manifest.append({
                    "start": segment["start"],
                    "duration": segment["duration"],
                    "text": segment["text"],
                    "url": image_path  # Store local path instead of URL
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

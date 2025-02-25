import os
import re
import requests
from bs4 import BeautifulSoup

def fetch_image_urls(query, num_images=5):
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

def download_images(urls, output_dir="output"):
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/103.0.5060.114 Safari/537.36")
    }
    
    for idx, img_url in enumerate(urls):
        try:
            r = requests.get(img_url, headers=headers, timeout=10)
            r.raise_for_status()
            file_path = os.path.join(output_dir, f"image_{idx+1}.jpg")
            with open(file_path, "wb") as f:
                f.write(r.content)
            print(f"Downloaded image {idx+1} to {file_path}")
        except Exception as e:
            print(f"Failed to download image {idx+1} from {img_url}. Error: {e}")

if __name__ == "__main__":
    search_query = input("Enter search query: ")
    try:
        num = int(input("Enter number of images: "))
    except ValueError:
        num = 5

    print("Fetching Google Images search results...")
    urls = fetch_image_urls(search_query, num)
    if urls:
        download_images(urls)
    else:
        print("No images were found or downloaded.")

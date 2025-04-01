import base64
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic.v1 import tools

load_dotenv()

def generate(query):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-2.5-pro-exp-03-25"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"""{query}"""),
            ],
        ),
    ]
    tools = [
        types.Tool(google_search=types.GoogleSearch())
    ]
    generate_content_config = types.GenerateContentConfig(
        tools=tools,
        response_mime_type="text/plain",
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    print(response.text)

if __name__ == "__main__":
    generate("Why is ghibli style photos generated with new gpt-4o so popular?")

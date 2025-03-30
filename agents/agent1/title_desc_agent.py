from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import os

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
)

def generate_title_description(state):
    print("Generating title and description...")
    prompt = ChatPromptTemplate.from_template(
        """Generate compelling YouTube Shorts metadata for this script:
        {script}
        
        Follow these guidelines:
        1. Title must:
           - Start with a powerful action word or number
           - Include trending keywords
           - Create curiosity or urgency
           - Be optimized for YouTube search
           - Stay under 60 characters
        
        2. Description must:
           - Start with a hook
           - Include relevant hashtags
           - Use strategic emojis
           - Add a clear call-to-action
           - Stay under 200 characters
        
        Return JSON with(The output response should be exactly like this):
        {{
            "title": "Catchy title under 60 chars",
            "description": "Engaging description with emojis (200 chars)"
        }}"""
    )
    chain = prompt | llm | JsonOutputParser()
    metadata = chain.invoke({"script": state["script"]})
    print("Metadata generated:", metadata)
    return {"title": metadata["title"], "description": metadata["description"]}

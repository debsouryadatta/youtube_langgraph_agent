
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import os


tavily = TavilySearchResults(max_results=3)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
)

def research_and_generate_transcript(state):
    print("Researching and generating transcript...")
    topic = state["topic"]
    
    # Web research
    tavily_results = tavily.invoke({"query": topic})
    
    # Generate script
    script_prompt = ChatPromptTemplate.from_template(
        """Create a compelling 30-second YouTube Shorts script about {topic} using this research:
        {research}
        
        Follow these guidelines strictly:
        1. Hook (0-5s): Start with an attention-grabbing opening line
        2. Core Content (5-25s): Present key information in short, impactful sentences
        3. Call-to-Action (25-30s): End with an engaging prompt
        
        Each segment MUST:
        - Be written in a conversational, natural speaking style
        - Use interjections like "Hey!", "Wow!", "You won't believe this!"
        - Include emotional emphasis ("This is incredible!", "I'm so excited to share...")
        - Add natural pauses with "..." for dramatic effect
        - Use rhetorical questions to engage viewers
        - Avoid any formatting symbols or special characters
        - Sound authentic and human-like
        - The text key in the json response should only contain the text 

        Format JSON exactly(The output response should be exactly like this):
        {{
            "videoScript": [
                {{
                    "start": "00:00",
                    "duration": "00:02",
                    "text": "Hey guys! You won't believe what I discovered..."
                }},
                ...
            ],
            "totalDuration": "00:30"
        }}"""
    )
    chain = script_prompt | llm | JsonOutputParser()
    script = chain.invoke({
        "topic": topic,
        "research": f"Research: {tavily_results}"
    })
    print("Script generated:", script)
    return {"script": script}

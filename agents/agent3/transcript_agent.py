
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
        """Create a compelling 30-second YouTube Shorts script about {topic} focusing on tech motivation, tech tips & tricks, or tech stories. Use this research:
        {research}
        
        Follow these guidelines strictly:
        1. Hook (0-5s): Start with an attention-grabbing tech-related opening
        2. Core Content (5-25s): Present key tech information or insights
        3. Call-to-Action (25-30s): End with a tech-related engagement prompt

        Each segment MUST:
        - Use a conversational, tech-enthusiast speaking style
        - Include tech-specific interjections ("Whoa, check this out!", "This tech is mind-blowing!")
        - Express excitement about technology ("I'm stoked to share this tech breakthrough!")
        - Add dramatic pauses ("...and then, the algorithm did something unexpected...")
        - Pose tech-related rhetorical questions
        - Avoid formatting symbols or special characters
        - Sound like an authentic tech influencer
        - The text key should only contain the script text

        Format JSON exactly like this:
        {{
            "videoScript": [
                {{
                    "start": "00:00",
                    "duration": "00:03",
                    "text": "Hey tech enthusiasts! Ever wondered how AI is changing our daily lives?"
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

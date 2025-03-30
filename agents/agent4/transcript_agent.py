from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
)

def gemini_google_search(query):
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"""
                Conduct comprehensive research on the topic: {query}
                
                Please provide:
                1. Key facts and information about the topic
                2. Recent developments or trends
                3. Different perspectives or viewpoints
                4. Interesting statistics or data points
                5. Expert opinions or insights
                
                Format your response as a well-organized research summary with clear sections.
                Include citations or sources where relevant.
                Focus on providing accurate, detailed, and useful information.
                """),
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

    return response.text

def research_and_generate_transcript(state):
    print("Researching and generating transcript...")
    topic = state["topic"]
    
    # Web research using Gemini with Google Search
    research_results = gemini_google_search(topic)
    
    # Generate script
    script_prompt = ChatPromptTemplate.from_template(
        """Create a compelling 30-second YouTube Shorts script about {topic}. Use this research:
        {research}
        
        Follow these guidelines strictly:
        1. Hook (0-5s): Start with an attention-grabbing opening
        2. Core Content (5-25s): Present key information or insights
        3. Call-to-Action (25-30s): End with an engagement prompt

        The script MUST:
        - Use a conversational, enthusiastic speaking style
        - Include natural interjections and expressions ("Wow!", "Can you believe it?!", "This is incredible!")
        - Express genuine excitement ("I'm so excited to share this with you!")
        - Add dramatic pauses ("...and then, something amazing happened...")
        - Use question marks, exclamation points, and ellipses naturally
        - Include rhetorical questions that engage the viewer
        - Sound like a real person talking, not a robotic script
        - Be approximately 30 seconds when read aloud at a natural pace
        - DO NOT include any timestamps, markers, or time indicators in the script
        - DO NOT format the response as JSON or with any special formatting
        
        IMPORTANT: Return ONLY the plain text script that would be spoken by the narrator, with no timestamps, formatting, or structure beyond the natural flow of speech.
        """
    )
    chain = script_prompt | llm | StrOutputParser()
    script = chain.invoke({
        "topic": topic,
        "research": f"Research: {research_results}"
    })
    print("Script generated successfully: ", script)
    return {"script": script}

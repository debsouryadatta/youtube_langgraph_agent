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
                I need you to perform an exhaustive, in-depth research on: {query}
                
                Your research should:
                1. Analyze multiple high-quality sources (minimum 20-30 different websites)
                2. Extract comprehensive factual information with specific details
                3. Gather direct quotes from recognized authorities in the field
                4. Uncover lesser-known but significant insights about the topic
                
                Your response must be extremely thorough and detailed (at least 3000+ words).
                Organize information into clear, well-structured sections with appropriate headings.
                Prioritize authoritative sources.
                Synthesize information to provide a comprehensive, nuanced understanding of the topic.
                Do not summarize superficially - I need depth and substance in your research.
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
        """Create a compelling 30-second YouTube Shorts script about {topic} in Hindi but written using English letters (Roman script). Use this research:
        {research}
        
        Follow these guidelines strictly:
        1. Hook (0-5s): Start with an attention-grabbing opening
        2. Core Content (5-25s): Present key information or insights
        3. Call-to-Action (25-30s): End with an engagement prompt

        The script MUST:
        - Be primarily in Hindi but written using English letters/Roman script (like: "Aaj main aapko ek kahani sunane wala hoon")
        - Use a conversational, enthusiastic speaking style with natural Hindi expressions
        - Include natural Hindi interjections and expressions ("Arrey yaar!", "Kya baat hai!", "Socho zara!")
        - Express genuine excitement ("Main bohot excited hoon aapko yeh batane ke liye!")
        - Add dramatic pauses ("...aur phir, kuch aisa hua jo...")
        - Use question marks, exclamation points, and ellipses naturally
        - Include rhetorical questions in Hindi that engage the viewer
        - Sound like a real Indian person talking casually, not a robotic script
        - Use common Hindi phrases and expressions that young Indians use in everyday speech
        - Be approximately 30 seconds when read aloud at a natural pace
        - DO NOT include any timestamps, markers, or time indicators in the script
        - DO NOT format the response as JSON or with any special formatting
        
        IMPORTANT: Return ONLY the plain text script that would be spoken by the narrator, with no timestamps, formatting, or structure beyond the natural flow of speech. The script should sound completely natural as if spoken by a real person.
        
        Example of the style (but don't copy this content):
        "Arrey dosto! Kya aap jante hain ki duniya ka sabse bada janwar kaun sa hai? Neeli whale! Yeh itni badi hoti hai ki ek bus se bhi lambi ho sakti hai. Socho zara, kitna amazing hai na? Agar aapko yeh video pasand aaya to like karein aur comment mein batayein ki aapko kaun sa janwar sabse zyada pasand hai!"
        """
    )
    chain = script_prompt | llm | StrOutputParser()
    script = chain.invoke({
        "topic": topic,
        "research": f"Research: {research_results}"
    })
    print("Script generated successfully: ", script)
    return {"script": script}

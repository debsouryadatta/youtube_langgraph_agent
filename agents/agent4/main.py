# youtube langraph agent
from typing import TypedDict, List
from langgraph.graph import END, StateGraph

from transcript_agent import research_and_generate_transcript
from title_desc_agent import generate_title_description
from thumbnail_agent import generate_thumbnail
from audio_agent import generate_audio
from images_agent import generate_images
from video_agent import create_video_with_overlays
from uploader_agent import upload_to_youtube
from dotenv import load_dotenv

load_dotenv()

# 1. Define State Schema
class AgentState(TypedDict):
    topic: str
    script: dict
    title: str
    description: str
    thumbnail_url: str
    audio_path: str
    images_manifest: List[dict]
    final_video_path: str
    video_id: str

# 2. Initialize Tools and Models


# 3. Define Nodes/Agents
def transcript_agent(state: AgentState):
    result = research_and_generate_transcript(state)
    return {"script": result["script"]}

def title_desc_agent(state: AgentState):
    print("State in title_desc_agent:", state)
    result = generate_title_description(state)
    return {"title": result["title"], "description": result["description"]}

def thumbnail_agent(state: AgentState):
    result = generate_thumbnail(state)
    return {"thumbnail_url": result["thumbnail_url"]}

def audio_agent(state: AgentState):
    result = generate_audio(state)
    return {"audio_path": result["audio_path"], "script": result["script"]}

def images_agent(state: AgentState):
    result = generate_images(state)
    return {"images_manifest": result["images_manifest"]}

def video_agent(state: AgentState):
    result = create_video_with_overlays(state)
    return {"final_video_path": result["final_video_path"]}

def uploader_agent(state: AgentState):
    result = upload_to_youtube(state)
    return {"video_id": result["video_id"]}



# 4. Build Workflow
workflow = StateGraph(AgentState)

workflow.add_node("transcript_agent", transcript_agent)
workflow.add_node("title_desc_agent", title_desc_agent)
workflow.add_node("thumbnail_agent", thumbnail_agent)
workflow.add_node("audio_agent", audio_agent)
workflow.add_node("images_agent", images_agent)
workflow.add_node("video_agent", video_agent)
workflow.add_node("uploader_agent", uploader_agent)

workflow.set_entry_point("transcript_agent")
workflow.add_edge("transcript_agent", "title_desc_agent")
workflow.add_edge("title_desc_agent", "thumbnail_agent")
workflow.add_edge("thumbnail_agent", "audio_agent")
workflow.add_edge("audio_agent", "images_agent")
workflow.add_edge("images_agent", "video_agent")
workflow.add_edge("video_agent", END)
# workflow.add_edge("video_agent", "uploader_agent")
# workflow.add_edge("uploader_agent", END)

app = workflow.compile()

# 5. Execution
if __name__ == "__main__":
    result = app.invoke({
        "topic": "Arjuna's celestial weapons and how he acquired them from gods"
    })
    print(f"Final video created at: {result['final_video_path']}")
    # print(f"Final Shorts YT link: https://www.youtube.com/shorts/{result['video_id']}")

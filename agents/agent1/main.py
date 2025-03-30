# youtube langraph agent
from typing import TypedDict, List
from langgraph.graph import END, StateGraph

from transcript_agent import research_and_generate_transcript
from title_desc_agent import generate_title_description
from thumbnail_agent import generate_thumbnail
from audio_agent import generate_audio
from images_agent import generate_images
from avatar_video_agent import generate_avatar_video
from video_agent import create_video_with_overlays
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
    avatar_video_path: str
    final_video_path: str

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

def avatar_video_agent(state: AgentState):
    result = generate_avatar_video(state)
    return {"avatar_video_path": result["avatar_video_path"]}

def video_agent(state: AgentState):
    result = create_video_with_overlays(state)
    return {"final_video_path": result["final_video_path"]}



# 4. Build Workflow
workflow = StateGraph(AgentState)

workflow.add_node("transcript_agent", transcript_agent)
workflow.add_node("title_desc_agent", title_desc_agent)
workflow.add_node("thumbnail_agent", thumbnail_agent)
workflow.add_node("audio_agent", audio_agent)
workflow.add_node("images_agent", images_agent)
workflow.add_node("avatar_video_agent", avatar_video_agent)
workflow.add_node("video_agent", video_agent)

workflow.set_entry_point("transcript_agent")
workflow.add_edge("transcript_agent", "title_desc_agent")
workflow.add_edge("title_desc_agent", "thumbnail_agent")
workflow.add_edge("thumbnail_agent", "audio_agent")
workflow.add_edge("audio_agent", "images_agent")
workflow.add_edge("images_agent", "avatar_video_agent")
workflow.add_edge("avatar_video_agent", "video_agent")
workflow.add_edge("video_agent", END)

app = workflow.compile()

# 5. Execution
if __name__ == "__main__":
    result = app.invoke({
        "topic": "India versus Pakistan 2025 Champions Trophy, Match review"
    })
    print(f"Final video created at: {result['final_video_path']}")

import sys
import os
from pathlib import Path

# --- Local Development Path Fix ---
# This ensures Python can find the 'agency' framework in the parent src/ folder
# Once you package your framework with pip, you can remove this block!
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

import uvicorn
import json
import uuid
from agency.api import app, oversight_listener
import agency.api as api
from agency.loader import AgencyLoader

# --- Application Specific Endpoints ---

@app.post("/test-trigger")
async def trigger_task(task: str):
    """Manual trigger to drop tasks into the agent network."""
    await api.framework_broker.publish(
        topic="client_requests",
        message=json.dumps({
            "envelope": {
                "message_id": str(uuid.uuid4()), 
                "sender": "manual_tester", 
                "topic": "client_requests"
            },
            "context": {"session_id": "manual_1", "iteration_count": 0},
            "payload": {"type": "task", "content": task, "tool_calls": []}
        })
    )
    return {"status": "Task dispatched to broker!", "task": task}

# --- Framework Boot Sequence ---

class DummyLLM:
    """A placeholder LLM so the app boots successfully out-of-the-box."""
    async def generate_response(self, prompt: str, tools: list = None) -> dict:
        return {"type": "result", "content": "I am a dummy LLM response.", "tool_calls": []}

@app.on_event("startup")
async def boot_framework():
    loader = AgencyLoader("agency.yaml")
    
    # Inject the placeholder LLM. Replace this with your real OpenAI/Anthropic client later!
    dummy_llm = DummyLLM()
    broker, agents = await loader.boot(llm_client=dummy_llm)
    
    api.framework_broker = broker
    await broker.subscribe("human_oversight", oversight_listener)
    print("Framework running! Interactive dashboard mounted at http://localhost:8000/docs")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
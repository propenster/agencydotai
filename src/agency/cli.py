#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 18:39:48 2026

@author: faith508
"""

import argparse
import os
from pathlib import Path

YAML_TEMPLATE = """
version: '1.0'
globals:
  broker: "memory"
topics:
  - id: "client_requests"
  - id: "research_tasks"
  - id: "research_results"
  - id: "human_oversight"
agents:
  manager_agent:
    role: "hub"
    system_prompt_file: "./prompts/manager.md"
    subscribes: ["client_requests", "research_results"]
    publishes: ["research_tasks", "human_oversight"]
    interrupts:
      on_confidence_below: 0.70
  researcher_agent:
    role: "spoke"
    system_prompt_file: "./prompts/researcher.md"
    subscribes: ["research_tasks"]
    publishes: ["research_results"]
    tools: ["web_scraper"]
    interrupts:
      require_approval_for: ["web_scraper"]
"""

MAIN_TEMPLATE = """
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
    \"\"\"Manual trigger to drop tasks into the agent network.\"\"\"
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
    \"\"\"A placeholder LLM so the app boots successfully out-of-the-box.\"\"\"
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
"""

# --- Core CLI Logic ---

def create_file(path: Path, content: str):
    """Helper to safely write files and create parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())

def init_project(project_name: str):
    """Scaffolds the project directory."""
    base = Path(project_name)
    if base.exists():
        print(f"Error: Directory '{project_name}' already exists.")
        return

    print(f"Initializing new agency in ./{project_name}...")
    
    # Generate Core Files
    create_file(base / "agency.yaml", YAML_TEMPLATE)
    create_file(base / "main.py", MAIN_TEMPLATE)
    create_file(base / ".env", "OPENAI_API_KEY=your_key_here")
    
    #toosl
    create_file(base / "tools" / "__init__.py", "")
    create_file(base / "tools" / "web_scraper.py", "def run():\n    pass")
    create_file(base / "prompts" / "manager.md", "You are the orchestrator.")
    create_file(base / "prompts" / "researcher.md", "You are the researcher.")

    print("Scaffolding complete!")
    print(f"Next steps:\n   cd {project_name}\n   python main.py")

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Framework CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a new project")
    init_parser.add_argument("name", help="Name of the project directory")

    args = parser.parse_args()

    if args.command == "init":
        init_project(args.name)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 18:42:10 2026

@author: faith508
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio
import json
from typing import Dict, Any
import uuid
from datetime import datetime, timezone
from pathlib import Path

app = FastAPI(title="Framework Oversight API")

# In-memory storage for paused states - stackexxhange
# Keys are message_ids of the interrupts
pending_reviews: Dict[str, dict] = {}

# Global reference to our broker so the API can publish the human's decision
framework_broker = None 

# The Pydantic Models for the API
class HumanReviewRequest(BaseModel):
    message_id: str
    action: str  # "approve", "reject", "modify"
    feedback: str = ""
    modified_tool_params: dict = None

# The Listener (Bridging the Broker and the API)
async def oversight_listener(raw_message: str):
    """Subscribes to the human_oversight topic on the event bus."""
    msg = json.loads(raw_message)
    
    # Store the paused state in memory so the API can serve it
    message_id = msg["envelope"]["message_id"]
    pending_reviews[message_id] = msg
    
    sender = msg["envelope"]["sender"]
    print(f"[Oversight API] Caught interrupt from '{sender}'. Awaiting human review.")

#Review endpoints...
@app.get("/reviews")
async def get_pending_reviews():
    """UI dashboard calls this to see all paused agents."""
    return {"pending_count": len(pending_reviews), "reviews": pending_reviews}

@app.post("/reviews/resolve")
async def resolve_review(decision: HumanReviewRequest):
    """Human submits their decision here."""
    
    if decision.message_id not in pending_reviews:
        raise HTTPException(status_code=404, detail="Review not found or already resolved.")
        
    paused_msg = pending_reviews.pop(decision.message_id)
    original_sender = paused_msg["envelope"]["sender"]
    
    # Handle Rejections
    if decision.action == "reject":
        content = f"SYSTEM OVERRIDE: Human rejected the action. Feedback: {decision.feedback}"
        tool_calls = []
        
    # Handle Approvals / Modifications
    else:
        content = f"SYSTEM OVERRIDE: Action approved. Feedback: {decision.feedback}"
        # If the human tweaked the SQL query before approving, use their version
        tool_calls = paused_msg["payload"].get("tool_calls", [])
        if decision.modified_tool_params and tool_calls:
            tool_calls[0]["parameters"] = decision.modified_tool_params

    # Resume the flow by publishing back to the agent
    # We construct a new message targeting the agent that paused
    resume_msg = {
        "envelope": {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender": "human_oversight_api",
            "topic": f"{original_sender}_inbox"
        },
        "context": {
            "session_id": paused_msg["context"]["session_id"],
            "iteration_count": paused_msg["context"]["iteration_count"] + 1
        },
        "payload": {
            "type": "task",
            "content": content,
            "tool_calls": tool_calls
        },
        "metadata": {
            "confidence_score": 1.0,
            "human_approved": True 
        }
    }
    
    # Fire it back into the cb
    await framework_broker.publish(resume_msg["envelope"]["topic"], json.dumps(resume_msg))
    
    print(f"[Oversight API] Resolved {decision.message_id}. Agent '{original_sender}' resumed.")
    return {"status": "success", "message": "Agent resumed."}

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the frontend HTML for the debugging dashboard."""
    # Locates the dashboard.html file in the templates folder
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/firehose")
async def get_firehose_logs():
    """Returns the entire history of messages that crossed the event bus."""
    if framework_broker:
        return {"logs": framework_broker.firehose_log}
    return {"logs": []}


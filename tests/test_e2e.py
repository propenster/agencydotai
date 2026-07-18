#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 19:04:18 2026

@author: faith508
"""

import pytest
import asyncio
import json
import tempfile
import os
from httpx import AsyncClient, ASGITransport
# Import your framework modules (assuming the package is named 'agency')
from agency.api import app, pending_reviews
import agency.api as api
from agency.loader import AgencyLoader
from agency.agency import BaseAgent

# --- 1. The Mock LLM Client ---
class MockLLMClient:
    """Simulates LLM responses to ensure tests are fast and deterministic."""
    async def generate(self, prompt: str, available_tools: list):
        # Trigger the interrupt flow if the prompt mentions SQL
        if "sql" in prompt.lower():
            return {
                "content": "I need to run a SQL query.",
                "tool_calls": [{"tool_name": "sql_query_builder", "parameters": {"query": "DROP TABLE users;"}}],
                "confidence": 0.8
            }
        
        # Standard response for normal workflows
        return {
            "content": "Research completed successfully.",
            "tool_calls": [],
            "confidence": 0.95
        }

# --- 2. Test Setup Fixtures ---
@pytest.fixture
def agency_yaml():
    """Creates a temporary agency.yaml file for the router to load."""
    config = {
        "version": "1.0",
        "globals": {"broker": "memory"},
        "topics": [{"id": "client_requests"}, {"id": "client_requests_done"}, {"id": "human_oversight"}],
        "agents": {
            "test_hub": {
                "role": "hub",
                # The Hub manages oversight, and authorizes the client topics.
                # Because it doesn't *subscribe* to client_requests_done, 
                # we avoid the infinite loop!
                "subscribes": ["human_oversight"],
                "publishes": ["client_requests", "client_requests_done"]
            },
            "test_spoke": {
                "role": "spoke",
                "subscribes": ["client_requests"],
                "publishes": ["client_requests_done"],
                "tools": ["sql_query_builder"],
                "interrupts": {
                    "require_approval_for": ["sql_query_builder"]
                }
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
        import yaml
        yaml.dump(config, f)
        temp_path = f.name
        
    yield temp_path
    os.remove(temp_path)

@pytest.fixture
async def boot_framework(agency_yaml):
    """Initializes the framework exactly as main.py would."""
    # Clear state between tests
    pending_reviews.clear() 
    
    # 1. Instantiate the mock LLM we defined at the top of the test file
    mock_llm = MockLLMClient()
    
    # 2. Load the YAML and boot the network, injecting the mock LLM
    loader = AgencyLoader(agency_yaml)
    broker, agents = await loader.boot(llm_client=mock_llm)
    
    # 3. Bind the API to the broker
    api.framework_broker = broker
    await broker.subscribe("human_oversight", api.oversight_listener)
    
    yield broker, agents

# --- 3. The Test Cases ---

@pytest.mark.asyncio
async def test_standard_message_flow(boot_framework):
    """Tests that a message propagates through the broker and agent."""
    broker, agents = boot_framework
    agent = agents["test_spoke"]

    # 1. Publish a standard task (does not contain "sql")
    initial_context = {"session_id": "test_sess_1", "iteration_count": 0}
    await broker.publish(
        topic="client_requests",
        message=json.dumps({
            "envelope": {"sender": "test_script", "topic": "client_requests"},
            "context": initial_context,
            "payload": {"type": "task", "content": "Run a standard report.", "tool_calls": []}
        })
    )

    # Allow the event loop to process the message
    await asyncio.sleep(0.1)

    # 2. Verify the agent processed it and published to its output topic
    # The firehose log should have 2 entries: the initial task, and the agent's result
    assert len(broker.firehose_log) == 2
    final_msg = broker.firehose_log[-1]
    
    assert final_msg["envelope"]["sender"] == "test_spoke"
    assert final_msg["payload"]["type"] == "result"
    assert final_msg["payload"]["content"] == "Research completed successfully."


@pytest.mark.asyncio
async def test_human_interrupt_cycle(boot_framework):
    """Tests the full lifecycle of an agent pausing, API holding state, and human resolving it."""
    broker, agents = boot_framework

    # 1. Trigger the interrupt by asking for SQL
    initial_context = {"session_id": "test_sess_2", "iteration_count": 0}
    await broker.publish(
        topic="client_requests",
        message=json.dumps({
            "envelope": {"message_id": "msg_001", "sender": "test_script", "topic": "client_requests"},
            "context": initial_context,
            "payload": {"type": "task", "content": "Run a sql query on the database.", "tool_calls": []}
        })
    )

    await asyncio.sleep(0.1)

    # 2. Verify the API caught the interrupt
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/reviews")
        assert response.status_code == 200
        data = response.json()
        
        assert data["pending_count"] == 1
        
        # Grab the message ID the API is holding
        paused_msg_id = list(data["reviews"].keys())[0]
        paused_msg = data["reviews"][paused_msg_id]
        
        # Ensure the risky tool call was captured
        assert paused_msg["payload"]["tool_calls"][0]["tool_name"] == "sql_query_builder"

        # 3. Simulate a human overriding the dangerous SQL via the API
        resolve_payload = {
            "message_id": paused_msg_id,
            "action": "modify",
            "feedback": "Use SELECT instead of DROP.",
            "modified_tool_params": {"query": "SELECT * FROM users;"}
        }
        
        resolve_response = await client.post("/reviews/resolve", json=resolve_payload)
        assert resolve_response.status_code == 200

    await asyncio.sleep(0.1)

    # 4. Verify the agent was resumed and the original request is no longer pending
    assert len(pending_reviews) == 0
    
    # The firehose should now contain the resume message sent by the API
    resume_msg = broker.firehose_log[-1]
    # assert resume_msg["envelope"]["sender"] == "human_oversight_api"
    # assert resume_msg["envelope"]["sender"] == "test_hub"
    assert resume_msg["envelope"]["sender"] == "human_oversight_api"
    assert resume_msg["metadata"]["human_approved"] == True
    assert resume_msg["payload"]["tool_calls"][0]["parameters"]["query"] == "SELECT * FROM users;"
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 18:32:45 2026

@author: faith508
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Awaitable

class BaseAgent:
    def __init__(self, agent_id: str, config: Dict[str, Any], broker: Any, llm_client: Any):
        self.agent_id = agent_id
        self.role = config.get("role", "spoke")
        self.subscribes = config.get("subscribes", [])
        self.publishes = config.get("publishes", [])
        self.interrupt_rules = config.get("interrupts", {})
        
        self.broker = broker
        # The pluggable LLM client... (Langchain, OpenAI, etc.)        
        self.llm = llm_client
        self.tools = config.get("tools", [])

    async def start(self):
        """Wakes up the agent and binds it to the event bus topics."""
        print(f"[{self.agent_id}] Starting as {self.role.upper()}...")
        for topic in self.subscribes:
            # We register this agent's handle_message method as the callback
            await self.broker.subscribe(topic, self.handle_message)
            print(f"[{self.agent_id}] Subscribed to: {topic}")

    async def handle_message(self, raw_message: str):
        """The I/O Transceiver: Parses incoming JSON and triggers the brain."""
        try:
            msg = json.loads(raw_message)
            envelope = msg["envelope"]
            context = msg["context"]
            payload = msg["payload"]
            
            # Circuit Breaker: Stop infinite
            if context["iteration_count"] >= 15:
                print(f"[{self.agent_id}] Circuit breaker tripped! Max iterations reached.")
                return

            print(f"[{self.agent_id}] Received {payload['type']} from {envelope['sender']}")

            # Process based on message type
            if payload["type"] == "task" or payload["type"] == "result":
                await self._process_with_llm(msg)
            elif payload["type"] == "interrupt":
                print(f"[{self.agent_id}] Message requires human oversight. Ignoring.")

        except Exception as e:
            print(f"[{self.agent_id}] Transceiver error: {e}")

    async def _process_with_llm(self, incoming_msg: Dict[str, Any]):
        """The core logic: Asks the LLM what to do next."""
        
        # In a real app, you would fetch full session history from the DB here
        prompt = incoming_msg["payload"]["content"]
        
        # Call the pluggable LLM (Abstracted away from the developer)
        # Returns a structured dict with {content, tool_calls, confidence}
        llm_response = await self.llm.generate(prompt, available_tools=self.tools)
        
        # Check for human-in-the-loop interrupts then freeze
        if self._requires_interrupt(llm_response):
            await self._publish_interrupt(incoming_msg, llm_response)
            return
            
        # Determine where the response goes
        target_topic = self.publishes[0] if self.publishes else "client_requests"
        
        # Format and publish the result
        await self.publish(
            topic=target_topic,
            msg_type="result",
            content=llm_response["content"],
            tool_calls=llm_response.get("tool_calls", []),
            context=incoming_msg["context"]
        )

    def _requires_interrupt(self, llm_response: Dict[str, Any]) -> bool:
        """Evaluates YAML rules to see if we need to freeze for human review."""
        confidence = llm_response.get("confidence", 1.0)
        min_confidence = self.interrupt_rules.get("on_confidence_below", 0.0)
        
        if confidence < min_confidence:
            return True
            
        restricted_tools = self.interrupt_rules.get("require_approval_for", [])
        for tool in llm_response.get("tool_calls", []):
            if tool["tool_name"] in restricted_tools:
                return True
                
        return False

    async def _publish_interrupt(self, incoming_msg: Dict[str, Any], llm_response: Dict[str, Any]):
        """Reroutes the message to the human_oversight topic."""
        print(f"[{self.agent_id}] INTERRUPT TRIGGERED. Suspending state.")
        await self.publish(
            topic="human_oversight",
            msg_type="interrupt",
            content="Agent state suspended pending human approval.",
            tool_calls=llm_response.get("tool_calls", []),
            context=incoming_msg["context"]
        )

    async def publish(self, topic: str, msg_type: str, content: str, tool_calls: list, context: Dict[str, Any]):
        """Packages data into the universal JSON schema and fires it to the bus."""
        outgoing_msg = {
            "envelope": {
                "message_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sender": self.agent_id,
                "topic": topic
            },
            "context": {
                "session_id": context["session_id"],
                "parent_message_id": context.get("message_id"),
                "iteration_count": context["iteration_count"] + 1
            },
            "payload": {
                "type": msg_type,
                "content": content,
                "tool_calls": tool_calls
            },
            "metadata": {
                "confidence_score": 1.0,
                "human_approved": False
            }
        }
        
        #publish to cb...
        await self.broker.publish(topic, json.dumps(outgoing_msg))
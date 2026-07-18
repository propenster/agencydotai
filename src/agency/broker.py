#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 18:35:05 2026

@author: faith508
"""

import asyncio
import json
from typing import Callable, Dict, List, Any

class MemoryBroker:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.firehose_log: List[Dict[str, Any]] = []

    async def subscribe(self, topic: str, callback: Callable):
        """Registers an agent's transceiver to listen to a specific topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
            
        self.subscribers[topic].append(callback)

    async def publish(self, topic: str, message: str):
        """Receives a message and routes it to all listeners of that topic."""
        msg_data = json.loads(message)
        self.firehose_log.append(msg_data)
        
        if topic not in self.subscribers or not self.subscribers[topic]:
            sender = msg_data.get("envelope", {}).get("sender", "Unknown")
            print(f"[Broker] Dead Letter: '{sender}' published to '{topic}', but nobody is listening.")
            return


        for callback in self.subscribers[topic]:
            asyncio.create_task(self._deliver(callback, message, topic))

    async def _deliver(self, callback: Callable, message: str, topic: str):
        """Safely executes the callback to prevent one crashing agent from killing the bus."""
        try:
            await callback(message)
        except Exception as e:
            # If an agent's code crashes hard, the broker catches it and keeps the system alive
            print(f"[Broker] Delivery failure on topic '{topic}': {e}")
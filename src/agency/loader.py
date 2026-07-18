#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 18:36:45 2026

@author: faith508
"""

import yaml
from typing import Dict, Any
from .broker import MemoryBroker
from .agency import BaseAgent

class AgencyLoader:
    def __init__(self, yaml_path: str):
        with open(yaml_path, 'r') as file:
            self.config = yaml.safe_load(file)
            
        # Initialize globals...
        broker_type = self.config.get("globals", {}).get("broker", "memory")
        if broker_type == "memory":
            self.broker = MemoryBroker()
        else:
            raise NotImplementedError("Redis/RabbitMQ brokers coming in v1.1")
            
        self.live_agents = {}

    def _validate_topology(self):
        """
        Story 3.2: Barabási-Albert Validator.
        Ensures Spokes only talk to topics managed by a Hub, preventing 
        infinite, unmonitored agent-to-agent loops.
        """
        managed_topics = set()
        
        # Map all topics connected to a Hub
        for agent_id, cfg in self.config.get('agents', {}).items():
            if cfg.get('role') == 'hub':
                managed_topics.update(cfg.get('subscribes', []))
                managed_topics.update(cfg.get('publishes', []))

        # Enforce Spoke compliance
        for agent_id, cfg in self.config.get('agents', {}).items():
            if cfg.get('role') == 'spoke':
                spoke_topics = set(cfg.get('subscribes', []) + cfg.get('publishes', []))
                rogue_topics = spoke_topics - managed_topics
                
                if rogue_topics:
                    raise ValueError(
                        f"[Topology Error] Spoke '{agent_id}' is trying to use "
                        f"unmanaged topics: {rogue_topics}. Spokes must route through Hubs."
                    )
                    
        print("[Router] Hub-and-Spoke network topology verified.")

    async def boot(self, llm_client=None):
        """Story 3.3: Dynamic Wiring."""
        print("Initializing framework...")
        self._validate_topology()
        
        agent_configs = self.config.get("agents", {})
        
        # Instantiate and bind all agents
        for agent_id, config in agent_configs.items():
            agent = BaseAgent(
                agent_id=agent_id,
                config=config,
                broker=self.broker,
                llm_client=llm_client  # We now pass the injected client here
            )
            self.live_agents[agent_id] = agent
            
            # This attaches the agent's transceiver to the broker
            await agent.start() 
            
        print(f"[Router] Successfully booted {len(self.live_agents)} agents.")
        return self.broker, self.live_agents
### agencydotai 

<p align="center">
  <h1 align="center">Asynchronous Event-Driven Multi-Agent Framework</h1>
</p>


<p align="center">
  <a href="https://github.com/propenster/agencydotai/network/members">
    <img src="https://img.shields.io/github/forks/propenster/agencydotai/framework" alt="GitHub forks">
  </a>
  <a href="https://github.com/propenster/agencydotai/issues">
    <img src="https://img.shields.io/github/issues/propenster/agencydotai/framework" alt="GitHub issues">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
  </a>
</p>

### Fast, Asynchronous, and Decoupled Multi-Agent AI Orchestration

> This is an open-source, high-performance Python framework built specifically for running production-grade multi-agent architectures using asynchronous pub/sub message passing. 
> By decoupling agents entirely through a centralized event broker and strict JSON schemas, this framework provides predictable, event-driven control, zero-overhead idle states, and native human-in-the-loop circuit breakers.

- **MemoryBroker Event Bus**: Eliminates tight coupling. Agents communicate purely by publishing and subscribing to discrete topics.
- **Zero-Overhead Asynchrony**: Built on Python `asyncio`, ensuring agents only consume CPU cycles when actively processing an event.
- **Declarative Topologies**: Define your entire multi-agent network, human-in-the-loop triggers, and tool permissions in a single YAML file.

## Table of contents

- [Why This Framework?](#why-this-framework)
- [Getting Started](#getting-started)
- [Scaffolding a Project](#scaffolding-a-project)
- [Configuration and Usage](#configuration-and-usage)
- [Key Features](#key-features)
- [When to Use This Framework](#when-to-use-this-framework)
- [Contribution](#contribution)
- [License](#license)
- [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq)

## Why This Framework?

Traditional multi-agent frameworks rely heavily on synchronous linear loops or tight class inheritance that couples agents directly to one another. This framework introduces a radically different paradigm designed for robust engineering requirements:

- **Event-Driven Asynchrony**: Agents sleep when no events are present on their subscribed topics, reducing idle hardware utilization to zero.
- **Total Structural Decoupling**: Agents do not know other agents exist. They only know what topics they subscribe to and what topics they output to, making runtime hot-swapping and scaling trivial.
- **Deterministic Guardrails**: Native iteration counters act as circuit breakers to prevent runaway LLM loops and control costs out of the box.

## Getting Started

Ensure you have Python >=3.10 installed on your system. You can install the framework directly using pip or uv:

```shell
pip install agencydotai
```

### 2. Scaffolding a Project
The framework includes a built-in CLI tool to generate clean, production-ready directory layouts instantly. Run the initialization command to build your architecture workspace:
```Shell
agencydotai init examples/my_agentic_project
```

This command automatically generates a structured, isolated directory tree with all necessary boilerplate:

```Plaintext
examples/my_agentic_project/
│   └── agency.yaml
│   ├── __init__.py
│   ├── agency/
│   │   ├── __init__.py
│   │   └── prompts/
│   │       ├── manager.md
│   │       └── researcher.md
│   │   └── tools/
│   │       ├── __init__.py
│   │       └── custom_tool.py
│   └── main.py
└── .env
```

### Configuration and Usage
You do not need to write complex Python loops to connect your agents. The entire topology of your system is defined declaratively.
#### Defining Your Network
Modify the generated `agency.yaml` to define your agents, their `pub/sub` routes, and their safety guardrails:
YAML
# agency.yaml

```yaml
manager_agent:
  role: "manager"
  subscribes:
    - "client_requests"
  publishes:
    - "analyst_tasks"
  tools: []
  interrupts:
    on_confidence_below: 0.7

analyst_agent:
  role: "spoke"
  subscribes:
    - "analyst_tasks"
  publishes:
    - "client_requests"
  tools:
    - "fetch_database_records"
  interrupts:
    require_approval_for:
      - "fetch_database_records"     
```


#### Running Your Architecture
Once configured, boot your framework using the standard Uvicorn server. The MemoryBroker will automatically bind your agents to the topics defined in your YAML.
```Shell
cd examples/my_agentic_project
python main.py
```
### Key Features
- Strict Message Contracts: A universal JSON schema validation layer guarantees that missing headers, context, or trace tags reject early at the interface, keeping agent code clean.
- Deterministic Loop Prevention: Built-in maximum iteration caps catch cascading multi-agent feedback logic errors before they trigger expensive runtime billing surprises.
- Dynamic Event Interception: Reroute execution flows instantly using custom confidence limits or tool usage intercept matrices natively via the YAML configuration.
- Auto-Generated Tool Scaffolding: The CLI automatically drops extensible base classes into your tools/ directory, making it trivial to add custom database, API, or local system integrations.

### When to Use This Framework
- Use this framework when you need more than a simple chatbot or a rigid linear script. It is designed for engineering teams that require:
- Real-time observability into exactly what agents are passing to one another.
- The ability to pause agent execution for human review before a destructive tool is fired.
- High-concurrency environments where running infinite while True loops for idle agents is unacceptable.
- The architectural freedom to swap out a single agent without rewriting the workflow logic of the entire system.





### Contribution
Contributions are welcome and encouraged. To contribute:
- Fork the repository.
- Create a new feature branch.
- Ensure all type hints and configurations are validated.
- Submit a clean Pull Request targeting the base branch.

### License
This framework is released under the [MIT License](LICENSE.md).


### Frequently Asked Questions (FAQ)
- Q: Are the agents running concurrently on their own infinite loops?
- A: No. The agents use async event-driven callbacks. They consume zero CPU cycles when idle and wake up instantly when a new serialized message hits their subscribed message broker topic.
- Q: How does the framework protect against runaway agent API execution costs?
- A: The message schema carries a mandatory context block keeping track of iteration_count. If a workflow loops continuously across the message broker between agents, the circuit breaker halts execution once the safety count is exceeded.
- Q: Can this structure connect to alternative LLM backends or local models?
- A: Yes. Because the agent brain is abstract and decoupled from I/O mechanisms, you can pass any LangChain-compatible generator module, direct HTTP clients, or local Ollama setups without altering your core messaging layout.
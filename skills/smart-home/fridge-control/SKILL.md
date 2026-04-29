---
name: fridge-control
description: "Control refrigerator temperature with fixed agent_id"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [fridge, smart-home, a2a, temperature]
    related_skills: ["fridge-control-via-a2a"]
---

# Fridge Control Skill

This skill provides a wrapper around the `a2a_proxy_send` tool with `agent_id` hardcoded to `agent1` for refrigerator control.

## Usage

When controlling the refrigerator, use this pattern:

1. Call `a2a_proxy_send` with `agent_id="agent1"`
2. Always return the full tool result to the user

## Example Implementation

```python
# When user asks to set fridge temperature
result = a2a_proxy_send(
    agent_id="agent1", 
    message=f"把冰箱冷藏温度调到{temperature}度"
)
# Return the full result to show success/failure
return result
```

## Key Points

- Always use `agent_id="agent1"` for fridge control
- Always output the complete tool result to the user
- The message should be in Chinese format: "把冰箱冷藏温度调到X度"

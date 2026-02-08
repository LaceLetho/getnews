---
name: grok-api-reference
description: Use when working with xAI Grok API - comprehensive reference for REST API, model capabilities, SDKs, and advanced features
---

# Grok API Reference Skill

Comprehensive documentation for the xAI Grok API, covering REST API, gRPC, model capabilities, SDKs, and advanced usage patterns.

## What is Grok?

Grok is a family of Large Language Models (LLMs) developed by xAI, designed to deliver truthful, insightful answers. The xAI API provides programmatic access to Grok models with full OpenAI SDK compatibility.

**Base URL:** `https://api.x.ai`
**Authentication:** Bearer token via `Authorization: Bearer <your_xai_api_key>`

## When to Use This Skill

This skill should be triggered when:
- Implementing xAI Grok API integrations
- Working with text generation, image generation, or video generation
- Setting up voice agents or real-time audio
- Using advanced features (async, batch API, deferred completions)
- Debugging Grok API issues or errors
- Managing collections, files, or embeddings
- Implementing function calling or structured outputs
- Setting up billing, authentication, or team management
- Looking for code examples in Python, JavaScript, or other languages

## Quick Reference

### Basic Chat Completion

```bash
curl https://api.x.ai/v1/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $XAI_API_KEY" \
-d '{
    "input": [
        {"role": "system", "content": "You are Grok, a helpful AI assistant."},
        {"role": "user", "content": "What is the meaning of life?"}
    ],
    "model": "grok-4-1-fast-reasoning"
}'
```

### Python with xAI SDK

```python
from xai_sdk import Client
from xai_sdk.chat import user, system

client = Client(api_key="your_api_key")
chat = client.chat.create(model="grok-4-1-fast-reasoning")
chat.append(system("You are Grok, a helpful AI assistant."))
chat.append(user("What is the meaning of life?"))
response = chat.sample()
print(response.content)
```

### Python with OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="your_api_key",
    base_url="https://api.x.ai/v1"
)

completion = client.chat.completions.create(
    model="grok-4-1-fast-reasoning",
    messages=[
        {"role": "system", "content": "You are Grok, a helpful AI assistant."},
        {"role": "user", "content": "What is the meaning of life?"}
    ]
)
```

### Streaming Responses

```python
# With xAI SDK
for chunk in chat.stream():
    print(chunk.content, end="", flush=True)

# With OpenAI SDK
for chunk in client.chat.completions.create(
    model="grok-4-1-fast-reasoning",
    messages=[...],
    stream=True
):
    print(chunk.choices[0].delta.content, end="")
```

### Image Generation

```python
response = client.images.generate(
    prompt="A serene mountain landscape at sunset",
    model="aurora",
    n=1,
    size="1024x1024"
)
```

### Voice Agent (Real-time Audio)

```python
import websockets
import json

async with websockets.connect(
    "wss://api.x.ai/v1/realtime",
    additional_headers={"Authorization": f"Bearer {api_key}"}
) as ws:
    # Configure session
    await ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "voice": "Ara",  # Options: Ara, Rex, Sal, Eve, Leo
            "instructions": "You are a helpful assistant."
        }
    }))
```

### Batch API

```python
# Create batch
batch = client.batches.create(
    requests=[
        {"custom_id": "req-1", "input": [...], "model": "grok-4-1-fast-reasoning"},
        {"custom_id": "req-2", "input": [...], "model": "grok-4-1-fast-reasoning"}
    ]
)

# Check status
status = client.batches.retrieve(batch.id)
```

### Common Models

- `grok-4-1-fast-reasoning` - Latest reasoning model with enhanced capabilities
- `grok-beta` - Beta version with latest features
- `grok-vision-beta` - Vision-enabled model
- `aurora` - Image generation model
- `aurora-edit` - Image editing model

## Reference Files

Organized documentation is available in `references/`. Each file contains detailed information with code examples:

### Core API Documentation
- **getting-started.md** (2 sections) - Quickstart guide and introduction
- **api-reference.md** (16 sections) - Complete REST API reference
- **grpc-reference.md** (1 section) - gRPC API documentation

### Model Capabilities
- **model-capabilities.md** (12 sections) - Text, audio, images, video, reasoning, structured outputs
- **models-and-pricing.md** (2 sections) - Model overview, pricing, and migration guides

### Advanced Features
- **advanced-api-usage.md** (7 sections) - Async, batch API, deferred completions, fingerprinting, code prompt engineering
- **function-calling.md** (1 section) - Tool use and function calling
- **collections-api.md** (4 sections) - Document collections and search
- **files-api.md** (5 sections) - File handling and management

### Integration & Management
- **management-api.md** (5 sections) - Billing, authentication, audit
- **developers.md** (6 sections) - SDK documentation and examples
- **guides.md** (4 sections) - Implementation guides and best practices
- **libraries-sdks.md** - SDK references for various languages

### Console & Support
- **console.md** (6 sections) - xAI Console usage and billing
- **faq.md** (8 sections) - Frequently asked questions
- **debugging.md** (1 section) - Troubleshooting guide
- **community.md** (1 section) - Community resources

## Working with This Skill

### For Beginners
Start with `references/getting-started.md` for:
- Creating an xAI account
- Generating API keys
- Making your first request
- SDK setup and basic examples

### For API Integration
Use `references/api-reference.md` for:
- Complete endpoint documentation
- Request/response formats
- Authentication details
- Error handling

### For Advanced Features
Explore `references/advanced-api-usage.md` for:
- Asynchronous processing
- Batch requests
- Deferred completions
- Prompt engineering for code

### For Model Capabilities
Check `references/model-capabilities.md` for:
- Text generation and streaming
- Image understanding and generation
- Video generation
- Audio/voice agents
- Structured outputs
- Reasoning capabilities

## Key Features

### OpenAI SDK Compatibility
The xAI API is fully compatible with the OpenAI SDK. Simply change the base URL:
```python
client = OpenAI(
    api_key="your_xai_api_key",
    base_url="https://api.x.ai/v1"
)
```

### Multiple Authentication Methods
- API Key (server-side): Direct authentication with your API key
- Ephemeral tokens (client-side): Secure, time-limited tokens for browser/client apps

### Billing Options
- **Prepaid credits**: Purchase credits upfront, consumption deducted from balance
- **Monthly invoiced billing**: Automatic billing at end of month (requires spending limit > $0)

## Common Tasks

| Task | Reference File | Section |
|------|---------------|---------|
| Quick start guide | getting-started.md | developers/quickstart |
| REST API endpoints | api-reference.md | Multiple sections |
| Text generation | model-capabilities.md | text/generate-text |
| Image generation | model-capabilities.md | images/generation |
| Voice/audio | model-capabilities.md | audio/voice-agent |
| Streaming | model-capabilities.md | text/streaming |
| Batch processing | advanced-api-usage.md | batch-api |
| Function calling | function-calling.md | Full file |
| Collections | collections-api.md | collection, search |
| Billing setup | console.md | console/billing |
| Troubleshooting | debugging.md | Full file |

## Resources

### Official Links
- Console: https://console.x.ai
- API Keys: https://console.x.ai/team/default/api-keys
- Billing: https://console.x.ai/team/default/billing
- Documentation: https://docs.x.ai

### Reference Structure
```
references/
├── index.md                    # Documentation index
├── getting-started.md         # Quickstart and introduction
├── api-reference.md           # REST API endpoints
├── model-capabilities.md      # Model features
├── models-and-pricing.md      # Models, pricing, migration
├── advanced-api-usage.md      # Advanced patterns
├── management-api.md          # Admin operations
├── grpc-reference.md          # gRPC API
├── collections-api.md         # Collections
├── files-api.md              # File handling
├── function-calling.md        # Tool use
├── console.md                # Console docs
├── guides.md                 # Best practices
├── developers.md             # SDK reference
├── faq.md                    # FAQs
├── debugging.md              # Troubleshooting
└── community.md              # Community
```

## Notes

- **OpenAI SDK compatible**: Use existing OpenAI code with minimal changes
- **Anthropic SDK deprecated**: Migrate to Responses API or gRPC
- **Timeout recommendations**: Use 3600s timeout for reasoning models
- **Environment variables**: Store API keys as `XAI_API_KEY`
- **Rate limits**: Check console for current rate limits and usage
- **Billing**: Set invoiced spending limit > $0 to avoid service disruption

## Updating

This skill was automatically generated from official xAI documentation. To refresh with updated docs, re-run the scraper with the same configuration.

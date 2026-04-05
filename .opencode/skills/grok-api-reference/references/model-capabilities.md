# Grok API - Model Capabilities

**Sections:** 12

---

## Table of Contents

- developers/model-capabilities/audio/voice-agent
- developers/model-capabilities/audio/voice
- developers/model-capabilities/files/chat-with-files
- developers/model-capabilities/images/generation
- developers/model-capabilities/images/understanding
- developers/model-capabilities/legacy/chat-completions
- developers/model-capabilities/text/comparison
- developers/model-capabilities/text/generate-text
- developers/model-capabilities/text/reasoning
- developers/model-capabilities/text/streaming
- developers/model-capabilities/text/structured-outputs
- developers/model-capabilities/video/generation

---

===/developers/model-capabilities/audio/voice-agent===
#### Model Capabilities

# Voice Agent API

Build interactive voice conversations with Grok models using WebSocket. The Grok Voice Agent API accepts audio and text inputs and creates text and audio responses in real-time.

**WebSocket Endpoint:** `wss://api.x.ai/v1/realtime`

## Authentication

You can authenticate [WebSocket](#connect-via-websocket) connections using the xAI API key or an ephemeral token.

**IMPORTANT:** It is **recommended to use an ephemeral token** when authenticating from the client side (e.g. browser).
If you use the xAI API key to authenticate from the client side, **the client may see the API key and make unauthorized API requests with it.**

### Fetching Ephemeral Tokens

You need to set up another server or endpoint to fetch the ephemeral token from xAI. The ephemeral token will give the holder a scoped access to resources.

**Endpoint:** `POST https://api.x.ai/v1/realtime/client_secrets`

```bash
curl --url https://api.x.ai/v1/realtime/client_secrets \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  --data '{
    "expires_after": { 
      "seconds": 300 
    }
  }'

# Note: Does not support "session" or "expires_after.anchor" fields
```

```pythonWithoutSDK
# Example ephemeral token endpoint with FastAPI

import os
import httpx
from fastapi import FastAPI

app = FastAPI()
SESSION_REQUEST_URL = "https://api.x.ai/v1/realtime/client_secrets"
XAI_API_KEY = os.getenv("XAI_API_KEY")

@app.post("/session")
async def get_ephemeral_token():
    # Send request to xAI endpoint to retrieve the ephemeral token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=SESSION_REQUEST_URL,
            headers={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"expires_after": {"seconds": 300}},
        )
    
    # Return the response body from xAI with ephemeral token
    return response.json()
```

```javascriptWithoutSDK
// Example ephemeral token endpoint with Express

import express from 'express';

const app = express();
const SESSION_REQUEST_URL = "https://api.x.ai/v1/realtime/client_secrets";

app.use(express.json());

app.post("/session", async (req, res) => {
  const r = await fetch(SESSION_REQUEST_URL, {
    method: "POST",
    headers: {
      Authorization: \`Bearer \${process.env.XAI_API_KEY}\`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      expires_after: { seconds: 300 }
    }),
  });
  
  const data = await r.json();
  res.json(data);
});

app.listen(8081);
```

### Using API Key Directly

For server-side applications where the API key is not exposed to clients, you can authenticate directly with your xAI API key.

**Server-side only:** Only use API key authentication from secure server environments. Never expose your API key in client-side code.

```pythonWithoutSDK
import os
import websockets

XAI_API_KEY = os.getenv("XAI_API_KEY")
base_url = "wss://api.x.ai/v1/realtime"

# Connect with API key in Authorization header
async with websockets.connect(
    uri=base_url,
    ssl=True,
    additional_headers={"Authorization": f"Bearer {XAI_API_KEY}"}
) as websocket:
    # WebSocket connection is now authenticated
    pass
```

```javascriptWithoutSDK
import WebSocket from "ws";

const baseUrl = "wss://api.x.ai/v1/realtime";

// Connect with API key in Authorization header
const ws = new WebSocket(baseUrl, {
  headers: {
    Authorization: "Bearer " + process.env.XAI_API_KEY,
    "Content-Type": "application/json",
  },
});

ws.on("open", () => {
  console.log("Connected with API key authentication");
});
```

## Voice Options

The Grok Voice Agent API supports 5 different voice options, each with distinct characteristics. Select the voice that best fits your application's personality and use case.

### Available Voices

| Voice | Type | Tone | Description | Sample |
|-------|------|------|-------------|:------:|
| **`Ara`** | Female | Warm, friendly | Default voice, balanced and conversational |  |
| **`Rex`** | Male | Confident, clear | Professional and articulate, ideal for business applications |  |
| **`Sal`** | Neutral | Smooth, balanced | Versatile voice suitable for various contexts |  |
| **`Eve`** | Female | Energetic, upbeat | Engaging and enthusiastic, great for interactive experiences |  |
| **`Leo`** | Male | Authoritative, strong | Decisive and commanding, suitable for instructional content |  |

### Selecting a Voice

Specify the voice in your session configuration using the `voice` parameter:

```pythonWithoutSDK
# Configure session with a specific voice
session_config = {
    "type": "session.update",
    "session": {
        "voice": "Ara",  # Choose from: Ara, Rex, Sal, Eve, Leo
        "instructions": "You are a helpful assistant.",
        # Audio format settings (these are the defaults if not specified)
        "audio": {
            "input": {"format": {"type": "audio/pcm", "rate": 24000}},
            "output": {"format": {"type": "audio/pcm", "rate": 24000}}
        }
    }
}

await ws.send(json.dumps(session_config))
```

```javascriptWithoutSDK
// Configure session with a specific voice
const sessionConfig = {
  type: "session.update",
  session: {
    voice: "Ara", // Choose from: Ara, Rex, Sal, Eve, Leo
    instructions: "You are a helpful assistant.",
    // Audio format settings (these are the defaults if not specified)
    audio: {
      input: { format: { type: "audio/pcm", rate: 24000 } },
      output: { format: { type: "audio/pcm", rate: 24000 } }
    }
  }
};

ws.send(JSON.stringify(sessionConfig));
```

## Audio Format

The Grok Voice Agent API supports multiple audio formats for real-time audio streaming. Audio data must be encoded as base64 strings when sent over WebSocket.

### Supported Audio Formats

The API supports three audio format types:

| Format | Encoding | Container Types | Sample Rate |
|--------|----------|-----------------|-------------|
| **`audio/pcm`** | Linear16, Little-endian | Raw, WAV, AIFF | Configurable (see below) |
| **`audio/pcmu`** | G.711 μ-law (Mulaw) | Raw | 8000 Hz |
| **`audio/pcma`** | G.711 A-law | Raw | 8000 Hz |

### Supported Sample Rates

When using `audio/pcm` format, you can configure the sample rate to one of the following supported values:

| Sample Rate | Quality | Description |
|-------------|---------|-------------|
| **8000 Hz** | Telephone | Narrowband, suitable for voice calls |
| **16000 Hz** | Wideband | Good for speech recognition |
| **21050 Hz** | Standard | Balanced quality and bandwidth |
| **24000 Hz** | High (Default) | Recommended for most use cases |
| **32000 Hz** | Very High | Enhanced audio clarity |
| **44100 Hz** | CD Quality | Standard for music / media |
| **48000 Hz** | Professional | Studio-grade audio / Web Browser |

**Note:** Sample rate configuration is only applicable for `audio/pcm` format. The `audio/pcmu` and `audio/pcma` formats use their standard encoding specifications.

### Audio Specifications

| Property | Value | Description |
|----------|-------|-------------|
| **Sample Rate** | Configurable (PCM only) | Sample rate in Hz (see supported rates above) |
| **Default Sample Rate** | 24kHz | 24,000 samples per second (for PCM) |
| **Channels** | Mono | Single channel audio |
| **Encoding** | Base64 | Audio bytes encoded as base64 string |
| **Byte Order** | Little-endian | 16-bit samples in little-endian format (for PCM) |

### Configuring Audio Format

You can configure the audio format and sample rate for both input and output in the session configuration:

```pythonWithoutSDK
# Configure audio format with custom sample rate for input and output
session_config = {
    "type": "session.update",
    "session": {
        "audio": {
            "input": {
                "format": {
                    "type": "audio/pcm",  # or "audio/pcmu" or "audio/pcma"
                    "rate": 16000  # Only applicable for audio/pcm
                }
            },
            "output": {
                "format": {
                    "type": "audio/pcm",  # or "audio/pcmu" or "audio/pcma"
                    "rate": 16000  # Only applicable for audio/pcm
                }
            }
        },
        "instructions": "You are a helpful assistant.",
    }
}

await ws.send(json.dumps(session_config))
```

```javascriptWithoutSDK
// Configure audio format with custom sample rate for input and output
const sessionConfig = {
  type: "session.update",
  session: {
    audio: {
      input: {
        format: {
          type: "audio/pcm", // or "audio/pcmu" or "audio/pcma"
          rate: 16000 // Only applicable for audio/pcm
        }
      },
      output: {
        format: {
          type: "audio/pcm", // or "audio/pcmu" or "audio/pcma"
          rate: 16000 // Only applicable for audio/pcm
        }
      }
    },
    instructions: "You are a helpful assistant.",
  }
};

ws.send(JSON.stringify(sessionConfig));
```

## Connect via WebSocket

You can connect to the realtime model via WebSocket. The audio data needs to be serialized into base64-encoded strings.

The examples below show connecting to the WebSocket endpoint from the server environment.

```pythonWithoutSDK
import asyncio
import json
import os
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

XAI_API_KEY = os.getenv("XAI_API_KEY")
base_url = "wss://api.x.ai/v1/realtime"

# Process received message

async def on_message(ws: ClientConnection, message: websockets.Data):
    data = json.loads(message)
    print("Received event:", json.dumps(data, indent=2))

    # Optionally, you can send an event after processing message
    # You can create an event dictionary and send:
    # await send_message(ws, event)

# Send message with an event to server

async def send_message(ws: ClientConnection, event: dict[str, Any]):
    await ws.send(json.dumps(event))

# Example event to be sent on connection open

async def on_open(ws: ClientConnection):
    print("Connected to server.")

    # Configure the session with voice, audio format, and instructions
    session_config = {
        "type": "session.update",
        "session": {
            "voice": "Ara",
            "instructions": "You are a helpful assistant.",
            "turn_detection": {"type": "server_vad"},
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": 24000}},
                "output": {"format": {"type": "audio/pcm", "rate": 24000}}
            }
        }
    }
    await send_message(ws, session_config)

    # Send a user text message content
    event = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        },
    }
    await send_message(ws, event)

    # Send an event to request a response, so Grok will start processing on our previous message
    event = {
        "type": "response.create",
        "response": {
            "modalities": ["text", "audio"],
        },
    }
    await send_message(ws, event)

async def main(): # Connect to the secure websocket
async with websockets.connect(
uri=base_url,
ssl=True,
additional_headers={"Authorization": f"Bearer {XAI_API_KEY}"}
) as websocket:

        # Send request on connection open
        await on_open(ws=websocket)

        while True:
            try:
                # Receive message and print it
                message = await websocket.recv()
                await on_message(websocket, message)
            except websockets.exceptions.ConnectionClosed:
                print("Connection Closed")
                break

asyncio.run(main())
```

```javascriptWithoutSDK
import WebSocket from "ws";

const baseUrl = "wss://api.x.ai/v1/realtime";
const ws = new WebSocket(baseUrl, {
  headers: {
    Authorization: "Bearer " + process.env.XAI_API_KEY,
    "Content-Type": "application/json",
  },
});

ws.on("open", function open() {
  console.log("Connected to server.");

  // Configure the session with voice, audio format, and instructions
  const sessionConfig = {
    type: "session.update",
    session: {
      voice: "Ara",
      instructions: "You are a helpful assistant.",
      turn_detection: { type: "server_vad" },
      audio: {
        input: { format: { type: "audio/pcm", rate: 24000 } },
        output: { format: { type: "audio/pcm", rate: 24000 } }
      }
    }
  };
  ws.send(JSON.stringify(sessionConfig));

  // Create a new conversation message and send to server
  let event = {
    type: "conversation.item.create",
    item: {
      type: "message",
      role: "user",
      content: [{ type: "input_text", text: "hello" }],
    },
  };
  ws.send(JSON.stringify(event));

  // Send an event to request a response, so Grok will start processing on our previous message
  event = {
    type: "response.create",
  };
  ws.send(JSON.stringify(event));
});

ws.on("message", function incoming(message) {
  const serverEvent = JSON.parse(message);
  console.log(serverEvent);
});
```

## Message types

There are a few message types used in interacting with the models. [Client events](#client-events) are sent by user to the server, and [Server events](#server-events) are sent by server to client.

### Client Events

### Server Events

## Session Messages

### Client Events

* **`"session.update"`** - Update session configuration such as system prompt, voice, audio format and search settings

  ```json
  {
      "type": "session.update",
      "session": {
          "instructions": "pass a system prompt here",
          "voice": "Ara",
          "turn_detection": {
              "type": "server_vad" or null,
          },
          "audio": {
              "input": {
                  "format": {
                      "type": "audio/pcm",
                      "rate": 24000
                  }
              },
              "output": {
                  "format": {
                      "type": "audio/pcm",
                      "rate": 24000
                  }
              }
          }
      }
  }
  ```

  **Session Parameters:**

  | Parameter | Type | Description |
  |-----------|------|-------------|
  | `instructions` | string | System prompt |
  | `voice` | string | Voice selection: `Ara`, `Rex`, `Sal`, `Eve`, `Leo` (see [Voice Options](#voice-options)) |
  | `turn_detection.type` | string | null | `"server_vad"` for automatic detection, `null` for manual text turns |
  | `audio.input.format.type` | string | Input format: `"audio/pcm"`, `"audio/pcmu"`, or `"audio/pcma"` |
  | `audio.input.format.rate` | number | Input sample rate (PCM only): 8000, 16000, 21050, 24000, 32000, 44100, 48000 |
  | `audio.output.format.type` | string | Output format: `"audio/pcm"`, `"audio/pcmu"`, or `"audio/pcma"` |
  | `audio.output.format.rate` | number | Output sample rate (PCM only): 8000, 16000, 21050, 24000, 32000, 44100, 48000 |

### Receiving and Playing Audio

Decode and play base64 PCM16 audio received from the API. Use the same sample rate as configured:

```pythonWithoutSDK
import base64
import numpy as np

# Configure session with 16kHz sample rate for lower bandwidth (input and output)
session_config = {
    "type": "session.update",
    "session": {
        "instructions": "You are a helpful assistant.",
        "voice": "Ara",
        "turn_detection": {
            "type": "server_vad",
        },
        "audio": {
            "input": {
                "format": {
                    "type": "audio/pcm",
                    "rate": 16000  # 16kHz for lower bandwidth usage
                }
            },
            "output": {
                "format": {
                    "type": "audio/pcm",
                    "rate": 16000  # 16kHz for lower bandwidth usage
                }
            }
        }
    }
}
await ws.send(json.dumps(session_config))

# When processing audio, use the same sample rate
SAMPLE_RATE = 16000

# Convert audio data to PCM16 and base64
def audio_to_base64(audio_data: np.ndarray) -> str:
    """Convert float32 audio array to base64 PCM16 string."""
    # Normalize to [-1, 1] and convert to int16
    audio_int16 = (audio_data * 32767).astype(np.int16)
    # Encode to base64
    audio_bytes = audio_int16.tobytes()
    return base64.b64encode(audio_bytes).decode('utf-8')

# Convert base64 PCM16 to audio data
def base64_to_audio(base64_audio: str) -> np.ndarray:
    """Convert base64 PCM16 string to float32 audio array."""
    # Decode base64
    audio_bytes = base64.b64decode(base64_audio)
    # Convert to int16 array
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    # Normalize to [-1, 1]
    return audio_int16.astype(np.float32) / 32768.0
```

```javascriptWithoutSDK
// Configure session with 16kHz sample rate for lower bandwidth (input and output)
const sessionConfig = {
  type: "session.update",
  session: {
    instructions: "You are a helpful assistant.",
    voice: "Ara",
    turn_detection: { type: "server_vad" },
    audio: {
      input: {
        format: {
          type: "audio/pcm",
          rate: 16000 // 16kHz for lower bandwidth usage
        }
      },
      output: {
        format: {
          type: "audio/pcm",
          rate: 16000 // 16kHz for lower bandwidth usage
        }
      }
    }
  }
};
ws.send(JSON.stringify(sessionConfig));

// When processing audio, use the same sample rate
const SAMPLE_RATE = 16000;

// Create AudioContext with matching sample rate
const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });

// Helper function to convert Float32Array to base64 PCM16
function float32ToBase64PCM16(float32Array) {
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  const bytes = new Uint8Array(pcm16.buffer);
  return btoa(String.fromCharCode(...bytes));
}

// Helper function to convert base64 PCM16 to Float32Array
function base64PCM16ToFloat32(base64String) {
  const binaryString = atob(base64String);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  const pcm16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i++) {
    float32[i] = pcm16[i] / 32768.0;
  }
  return float32;
}
```

### Server Events

* **`"session.updated"`** - Acknowledge the client's `"session.update"` message that the session has been updated
  ```json
  {
      "event_id": "event_123",
      "type": "session.updated",
      "session": {
          "instructions": "You are a helpful assistant.",
          "voice": "Ara",
          "turn_detection": {
              "type": "server_vad"
          }
      }
  }
  ```

## Using Tools with Grok Voice Agent API

The Grok Voice Agent API supports various tools that can be configured in your session to enhance the capabilities of your voice agent. Tools can be configured in the `session.update` message.

### Available Tool Types

* **Collections Search (`file_search`)** - Search through your uploaded document collections
* **Web Search (`web_search`)** - Search the web for current information
* **X Search (`x_search`)** - Search X (Twitter) for posts and information
* **Custom Functions** - Define your own function tools with JSON schemas

### Configuring Tools in Session

Tools are configured in the `tools` array of the session configuration. Here are examples showing how to configure different tool types:

### Collections Search with `file_search`

Use the `file_search` tool to enable your voice agent to search through document collections. You'll need to create a collection first using the [Collections API](/developers/collections-api).

```pythonWithoutSDK
COLLECTION_ID = "your-collection-id"  # Replace with your collection ID

session_config = {
    "type": "session.update",
    "session": {
        ...
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [COLLECTION_ID],
                "max_num_results": 10,
            },
        ],
    },
}
```

```javascriptWithoutSDK
const COLLECTION_ID = "your-collection-id"; // Replace with your collection ID

const sessionConfig = {
    type: "session.update",
    session: {
        ...
        tools: [
            {
                type: "file_search",
                vector_store_ids: [COLLECTION_ID],
                max_num_results: 10,
            },
        ],
    },
};
```

### Web Search and X Search

Configure web search and X search tools to give your voice agent access to current information from the web and X (Twitter).

```pythonWithoutSDK
session_config = {
    "type": "session.update",
    "session": {
        ...
        "tools": [
            {
                "type": "web_search",
            },
            {
                "type": "x_search",
                "allowed_x_handles": ["elonmusk", "xai"],
            },
        ],
    },
}
```

```javascriptWithoutSDK
const sessionConfig = {
    type: "session.update",
    session: {
        ...
        tools: [
            {
                type: "web_search",
            },
            {
                type: "x_search",
                allowed_x_handles: ["elonmusk", "xai"],
            },
        ],
    },
};
```

### Custom Function Tools

You can define custom function tools with JSON schemas to extend your voice agent's capabilities.

```pythonWithoutSDK
session_config = {
    "type": "session.update",
    "session": {
        ...
        "tools": [
            {
                "type": "function",
                "name": "generate_random_number",
                "description": "Generate a random number between min and max values",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min": {
                            "type": "number",
                            "description": "Minimum value (inclusive)",
                        },
                        "max": {
                            "type": "number",
                            "description": "Maximum value (inclusive)",
                        },
                    },
                    "required": ["min", "max"],
                },
            },
        ],
    },
}
```

```javascriptWithoutSDK
const sessionConfig = {
    type: "session.update",
    session: {
        ...
        tools: [
            {
                type: "function",
                name: "generate_random_number",
                description: "Generate a random number between min and max values",
                parameters: {
                    type: "object",
                    properties: {
                        min: {
                            type: "number",
                            description: "Minimum value (inclusive)",
                        },
                        max: {
                            type: "number",
                            description: "Maximum value (inclusive)",
                        },
                    },
                    required: ["min", "max"],
                },
            },
        ],
    },
};
```

### Combining Multiple Tools

You can combine multiple tool types in a single session configuration:

```pythonWithoutSDK
session_config = {
    "type": "session.update",
    "session": {
        ...
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": ["your-collection-id"],
                "max_num_results": 10,
            },
            {
                "type": "web_search",
            },
            {
                "type": "x_search",
            },
            {
                "type": "function",
                "name": "generate_random_number",
                "description": "Generate a random number",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "number"},
                        "max": {"type": "number"},
                    },
                    "required": ["min", "max"],
                },
            },
        ],
    },
}
```

```javascriptWithoutSDK
const sessionConfig = {
    type: "session.update",
    session: {
        ...
        tools: [
            {
                type: "file_search",
                vector_store_ids: ["your-collection-id"],
                max_num_results: 10,
            },
            {
                type: "web_search",
            },
            {
                type: "x_search",
            },
            {
                type: "function",
                name: "generate_random_number",
                description: "Generate a random number",
                parameters: {
                    type: "object",
                    properties: {
                        min: { type: "number" },
                        max: { type: "number" },
                    },
                    required: ["min", "max"],
                },
            },
        ],
    },
};
```

For more details on Collections, see the [Collections API documentation](/developers/collections-api). For search tool parameters and options, see the [Web Search](/developers/tools/web-search) and [X Search](/developers/tools/x-search) guides.

### Handling Function Call Responses

When you define custom function tools, the voice agent will call these functions during conversation. You need to handle these function calls, execute them, and return the results to continue the conversation.

### Function Call Flow

1. **Agent decides to call a function** → sends `response.function_call_arguments.done` event
2. **Your code executes the function** → processes the arguments and generates a result
3. **Send result back to agent** → sends `conversation.item.create` with the function output
4. **Request continuation** → sends `response.create` to let the agent continue

### Complete Example

```pythonWithoutSDK
import json
import websockets

# Define your function implementations
def get_weather(location: str, units: str = "celsius"):
    """Get current weather for a location"""
    # In production, call a real weather API
    return {
        "location": location,
        "temperature": 22,
        "units": units,
        "condition": "Sunny",
        "humidity": 45
    }

def book_appointment(date: str, time: str, service: str):
    """Book an appointment"""
    # In production, interact with your booking system
    import random
    confirmation = f"CONF{random.randint(1000, 9999)}"
    return {
        "status": "confirmed",
        "confirmation_code": confirmation,
        "date": date,
        "time": time,
        "service": service
    }

# Map function names to implementations
FUNCTION_HANDLERS = {
    "get_weather": get_weather,
    "book_appointment": book_appointment
}

async def handle_function_call(ws, event):
    """Handle function call from the voice agent"""
    function_name = event["name"]
    call_id = event["call_id"]
    arguments = json.loads(event["arguments"])
    
    print(f"Function called: {function_name} with args: {arguments}")
    
    # Execute the function
    if function_name in FUNCTION_HANDLERS:
        result = FUNCTION_HANDLERS[function_name](**arguments)
        
        # Send result back to agent
        await ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result)
            }
        }))
        
        # Request agent to continue with the result
        await ws.send(json.dumps({
            "type": "response.create"
        }))
    else:
        print(f"Unknown function: {function_name}")

# In your WebSocket message handler
async def on_message(ws, message):
    event = json.loads(message)
    
    # Listen for function calls
    if event["type"] == "response.function_call_arguments.done":
        await handle_function_call(ws, event)
    elif event["type"] == "response.output_audio.delta":
        # Handle audio response
        pass
```

```javascriptWithoutSDK
// Define your function implementations
const functionHandlers = {
  get_weather: async (args) => {
    // In production, call a real weather API
    return {
      location: args.location,
      temperature: 22,
      units: args.units || "celsius",
      condition: "Sunny",
      humidity: 45
    };
  },
  
  book_appointment: async (args) => {
    // In production, interact with your booking system
    const confirmation = \`CONF\${Math.floor(Math.random() * 9000) + 1000}\`;
    return {
      status: "confirmed",
      confirmation_code: confirmation,
      date: args.date,
      time: args.time,
      service: args.service
    };
  }
};

// Handle function calls from the voice agent
async function handleFunctionCall(ws, event) {
  const functionName = event.name;
  const callId = event.call_id;
  const args = JSON.parse(event.arguments);
  
  console.log(\`Function called: \${functionName\} with args:\`, args);
  
  // Execute the function
  const handler = functionHandlers[functionName];
  if (handler) {
    const result = await handler(args);
    
    // Send result back to agent
    ws.send(JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: callId,
        output: JSON.stringify(result)
      }
    }));
    
    // Request agent to continue with the result
    ws.send(JSON.stringify({
      type: "response.create"
    }));
  } else {
    console.error(\`Unknown function: \${functionName\}\`);
  }
}

// In your WebSocket message handler
ws.on("message", (message) => {
  const event = JSON.parse(message);
  
  // Listen for function calls
  if (event.type === "response.function_call_arguments.done") {
    handleFunctionCall(ws, event);
  } else if (event.type === "response.output_audio.delta") {
    // Handle audio response
  }
});
```

### Function Call Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `response.function_call_arguments.done` | Server → Client | Function call triggered with complete arguments |
| `conversation.item.create` (function\_call\_output) | Client → Server | Send function execution result back |
| `response.create` | Client → Server | Request agent to continue processing |

### Real-World Example: Weather Query

When a user asks "What's the weather in San Francisco?", here's the complete flow:

| Step | Direction | Event | Description |
|:----:|:---------:|-------|-------------|
| 1 | Client → Server | `input_audio_buffer.append` | User speaks: "What's the weather in San Francisco?" |
| 2 | Server → Client | `response.function_call_arguments.done` | Agent decides to call `get_weather` with `location: "San Francisco"` |
| 3 | Client → Server | `conversation.item.create` | Your code executes `get_weather()` and sends result: `{temperature: 68, condition: "Sunny"}` |
| 4 | Client → Server | `response.create` | Request agent to continue with function result |
| 5 | Server → Client | `response.output_audio.delta` | Agent responds: "The weather in San Francisco is currently 68°F and sunny." |

Function calls happen automatically during conversation flow. The agent decides when to call functions based on the function descriptions and conversation context.

## Conversation messages

### Server Events

* **`"conversation.created"`** - The first message at connection. Notifies the client that a conversation session has been created

  ```json
  {
      "event_id": "event_9101",
      "type": "conversation.created",
      "conversation": {
          "id": "conv_001",
          "object": "realtime.conversation"
      }
  }
  ```

## Conversation item messages

### Client

* `"conversation.item.create"`: Create a new user message with text.

  ```json
  {
      "type": "conversation.item.create",
      "previous_item_id": "", // Optional, used to insert turn into history
      "item": {
          "type": "message",
          "role": "user",
          "content": [
              {
                  "type": "input_text",
                  "text": "Hello, how are you?"
              }
          ]
      }
  }
  ```

### Server

* `"conversation.item.added"`: Responding to the client that a new user message has been added to conversation history, or if an assistance response has been added to conversation history.

  ```json
  {
    "event_id": "event_1920",
    "type": "conversation.item.added",
    "previous_item_id": "msg_002",
    "item": {
      "id": "msg_003",
      "object": "realtime.item",
      "type": "message",
      "status": "completed",
      "role": "user",
      "content": [
        {
          "type": "input_audio",
          "transcript": "hello how are you"
        }
      ]
    }
  }
  ```

* `"conversation.item.input_audio_transcription.completed"`: Notify the client the audio transcription for input has been completed.

  ```json
  {
      "event_id": "event_2122",
      "type": "conversation.item.input_audio_transcription.completed",
      "item_id": "msg_003",
      "transcript": "Hello, how are you?"
  }
  ```

## Input audio buffer messages

### Client

* `"input_audio_buffer.append"`: Append chunks of audio data to the buffer. The audio needs to be base64-encoded. The server does not send back corresponding message.

  ```json
  {
      "type": "input_audio_buffer.append",
      "audio": "<Base64EncodedAudioData>"
  }
  ```

* `"input_audio_buffer.clear"`: Clear input audio buffer. Server sends back `"input_audio_buffer.cleared"` message.

  ```json
  {
    "type": "input_audio_buffer.clear"
  }
  ```

* `"input_audio_buffer.commit"`: Create a new user message by committing the audio buffer created by previous `"input_audio_buffer.append"` messages. Confirmed by `"input_audio_buffer.committed"` from server.

  Only available when `"turn_detection"` setting in session is `"type": null`. Otherwise the
  conversation turn will be automatically committed by VAD on the server.

  ```json
  {
      "type": "input_audio_buffer.commit"
  }
  ```

### Server

* `"input_audio_buffer.speech_started"`: Notify the client the server's VAD has detected the start of a speech.

  Only available when `"turn_detection"` setting in session is `"type": "server_vad"`.

  ```json
  {
    "event_id": "event_1516",
    "type": "input_audio_buffer.speech_started",
    "item_id": "msg_003"
  }
  ```

* `"input_audio_buffer.speech_stopped"`: Notify the client the server's VAD has detected the end of a speech.

  Only available when `"turn_detection"` setting in session is `"type": "server_vad"`.

  ```json
  {
    "event_id": "event_1516",
    "type": "input_audio_buffer.speech_stopped",
    "item_id": "msg_003"
  }
  ```

* `"input_audio_buffer.cleared"`: Input audio buffer has been cleared.

  ```json
  {
    "event_id": "event_1516",
    "type": "input_audio_buffer.cleared"
  }
  ```

* `"input_audio_buffer.committed"`: Input audio buffer has been committed.

  ```json
  {
    "event_id": "event_1121",
    "type": "input_audio_buffer.committed",
    "previous_item_id": "msg_001",
    "item_id": "msg_002"
  }
  ```

## Response messages

### Client

* `"response.create"`: Request the server to create a new assistant response when using client side vad. (This is handled automatically when using server side vad.)

  ```json
  {
      "type": "response.create"
  }
  ```

### Server

* `"response.created"`: A new assistant response turn is in progress. Audio delta created from this assistant turn will have the same response id. Followed by `"response.output_item.added"`.

  ```json
  {
    "event_id": "event_2930",
    "type": "response.created",
    "response": {
      "id": "resp_001",
      "object": "realtime.response",
      "status": "in_progress",
      "output": []
    }
  }
  ```

* `"response.output_item.added"`: A new assistant response is added to message history.

  ```json
  {
    "event_id": "event_3334",
    "type": "response.output_item.added",
    "response_id": "resp_001",
    "output_index": 0,
    "item": {
      "id": "msg_007",
      "object": "realtime.item",
      "type": "message",
      "status": "in_progress",
      "role": "assistant",
      "content": []
    }
  }
  ```

* `"response.done"`: The assistant's response is completed. Sent after all the `"response.output_audio_transcript.done"` and `"response.output_audio.done"` messages. Ready for the client to add a new conversation item.

  ```json
  {
      "event_id": "event_3132",
      "type": "response.done",
      "response": {
          "id": "resp_001",
          "object": "realtime.response",
          "status": "completed",
      }
  }
  ```

## Response audio and transcription messages

### Client

The client does not need to send messages to get these audio and transcription responses. They would be automatically created following `"response.create"` message.

### Server

* `"response.output_audio_transcript.delta"`: Audio transcript delta of the assistant response.
  ```json
  {
    "event_id": "event_4950",
    "type": "response.output_audio_transcript.delta",
    "response_id": "resp_001",
    "item_id": "msg_008",
    "delta": "Text response..."
  }
  ```

* `"response.output_audio_transcript.done"`: The audio transcript delta of the assistant response has finished generating.

  ```json
  {
    "event_id": "event_5152",
    "type": "response.output_audio_transcript.done",
    "response_id": "resp_001",
    "item_id": "msg_008"
  }
  ```

* `"response.output_audio.delta"`: The audio stream delta of the assistant response.
  ```json
  {
    "event_id": "event_4950",
    "type": "response.output_audio.delta",
    "response_id": "resp_001",
    "item_id": "msg_008",
    "output_index": 0,
    "content_index": 0,
    "delta": "<Base64EncodedAudioDelta>"
  }
  ```

* `"response.output_audio.done"`: Notifies client that the audio for this turn has finished generating.
  ```json
  {
      "event_id": "event_5152",
      "type": "response.output_audio.done",
      "response_id": "resp_001",
      "item_id": "msg_008",
  }
  ```

===/developers/model-capabilities/audio/voice===
#### Model Capabilities

# Voice Overview

We're introducing a new API for voice interactions with Grok. We're initially launching with the Grok Voice Agent API and will soon be launching dedicated speech-to-text and text-to-speech APIs.

## Grok Voice Agent API

Build powerful real-time voice applications with the Grok Voice Agent API. Create interactive voice conversations with Grok models via WebSocket for voice assistants, phone agents, and interactive voice applications.

**WebSocket Endpoint:** `wss://api.x.ai/v1/realtime`

## <NotificationBanner variant={"info"}>The Voice Agent API is only available in `us-east-1` region.</NotificationBanner>

### Enterprise Ready

Optimized for enterprise use cases across Customer Support, Medical, Legal, Finance, Insurance, and more. The Grok Voice Agent API delivers the reliability and precision that regulated industries demand.

* **Telephony** - Connect to platforms like Twilio, Vonage, and other SIP providers
* **Tool Calling** - CRMs, calendars, ticketing systems, databases, and custom APIs
* **Multilingual** - Serve global customers in their native language with natural accents
* **Low Latency** - Real-time responses for natural, human-like conversations
* **Accuracy** - Precise transcription and understanding of critical information:
  * Industry-specific terminology including medical, legal, and financial vocabulary
  * Email addresses, dates, and alphanumeric codes
  * Names, addresses, and phone numbers

### Getting Started

The Grok Voice Agent API enables interactive voice conversations with Grok models via WebSocket. Perfect for building voice assistants, phone agents, and interactive voice applications.

**Use Cases:**

* Voice Assistants for web and mobile
* AI-powered phone systems with Twilio
* Real-time customer support
* Interactive Voice Response (IVR) systems

[Documentation →](/developers/model-capabilities/audio/voice-agent)

### Low Latency

Built for real-time conversations. The Grok Voice Agent API is optimized for minimal response times, enabling natural back-and-forth dialogue without awkward pauses. Stream audio bidirectionally over WebSocket for instant voice-to-voice interactions that feel like talking to a human.

### Multilingual with Natural Accents

The Grok Voice Agent API speaks over 100 languages with native-quality accents. The model automatically detects the input language and responds naturally in the same language-no configuration required.

### Supported Languages

English, Spanish, French, German, Italian, Portuguese, Dutch, Russian, Chinese (Mandarin), Japanese, Korean, Arabic, Hindi, Turkish, Polish, Swedish, Danish, Norwegian, Finnish, Czech, and many more.

Each language features natural pronunciation, appropriate intonation patterns, and culturally-aware speech rhythms. You can also specify a preferred language or accent in your system instructions for consistent multilingual experiences.

### Tool Calling

Extend your voice agent's capabilities with powerful built-in tools that execute during conversations:

* **Web Search** - Real-time internet search for current information, news, and facts
* **X Search** - Search posts, trends, and discussions from X
* **Collections** - RAG-powered search over your uploaded documents and knowledge bases
* **Custom Functions** - Define your own tools with JSON schemas for booking, lookups, calculations, and more

Tools are called automatically based on conversation context. Your voice agent can search the web, query your documents, and execute custom business logic-all while maintaining a natural conversation flow.

### Voice Personalities

Choose from 5 distinct voices, each with unique characteristics suited to different applications:

| Voice | Type | Tone | Description | Sample |
|-------|------|------|-------------|:------:|
| **`Ara`** | Female | Warm, friendly | Default voice, balanced and conversational |  |
| **`Rex`** | Male | Confident, clear | Professional and articulate, ideal for business applications |  |
| **`Sal`** | Neutral | Smooth, balanced | Versatile voice suitable for various contexts |  |
| **`Eve`** | Female | Energetic, upbeat | Engaging and enthusiastic, great for interactive experiences |  |
| **`Leo`** | Male | Authoritative, strong | Decisive and commanding, suitable for instructional content |  |

### Flexible Audio Formats

Support for multiple audio formats and sample rates to match your application's requirements:

* **PCM (Linear16)** - High-quality audio with configurable sample rates (8kHz–48kHz)
* **G.711 μ-law** - Optimized for telephony applications
* **G.711 A-law** - Standard for international telephony

### Example Applications

Complete working examples are available demonstrating various voice integration patterns:

#### Web Voice Agent

Real-time voice chat in the browser with React frontend and Python/Node.js backends.

**Architecture:**

```
Browser (React) ←WebSocket→ Backend (FastAPI/Express) ←WebSocket→ xAI API
```

**Features:**

* Real-time audio streaming
* Visual transcript display
* Debug console for development
* Interchangeable backends

[GitHub →](https://github.com/xai-org/xai-cookbook/tree/main/voice-examples/agent/web)

#### Phone Voice Agent (Twilio)

AI-powered phone system using Twilio integration.

**Architecture:**

```
Phone Call ←SIP→ Twilio ←WebSocket→ Node.js Server ←WebSocket→ xAI API
```

**Features:**

* Phone call integration
* Real-time voice processing
* Function/tool calling support
* Production-ready architecture

[GitHub →](https://github.com/xai-org/xai-cookbook/tree/main/voice-examples/agent/telephony)

#### WebRTC Voice Agent

The Grok Voice Agent API uses WebSocket connections. Direct WebRTC connections are not available currently.

You can use a WebRTC server to connect the client to a server that then connects to the Grok Voice Agent API.

**Architecture:**

```
Browser (React) ←WebRTC→ Backend (Express) ←WebSocket→ xAI API
```

**Features:**

* Real-time audio streaming
* Visual transcript display
* Debug console for development
* WebRTC backend handles all WebSocket connections to xAI API

[GitHub →](https://github.com/xai-org/xai-cookbook/tree/main/voice-examples/agent/webrtc)

### Third Party Integrations

Build voice agents using popular third-party frameworks and platforms that integrate with the Grok Voice Agent API.

**LiveKit**

Build real-time voice agents using LiveKit's open-source framework with native Grok Voice Agent API integration and WebRTC Support.

[Docs →](https://docs.livekit.io/agents/integrations/xai/) | [GitHub →](https://github.com/livekit/agents/tree/main/livekit-plugins/livekit-plugins-xai)

**Voximplant**

Build real-time voice agents using Voximplant's open-source framework with native Grok Voice Agent API integration and SIP Support.

[Docs →](https://voximplant.com/products/grok-client) | [GitHub →](https://github.com/voximplant/grok-voice-agent-example)

**Pipecat**

Build real-time voice agents using Pipecat's open-source framework with native Grok Voice Agent API integration and advanced conversation management.

[Docs →](https://docs.pipecat.ai/server/services/s2s/grok) | [GitHub →](https://github.com/pipecat-ai/pipecat/blob/main/examples/foundational/51-grok-realtime.py)

===/developers/model-capabilities/files/chat-with-files===
#### Model Capabilities

# Chat with Files

Once you've uploaded files, you can reference them in conversations using the `file()` helper function in the xAI Python SDK. When files are attached, the system automatically enables document search capabilities, transforming your request into an agentic workflow.

## Basic Chat with a Single File

Reference an uploaded file in a conversation to let the model search through it for relevant information.

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload a document
document_content = b"""Quarterly Sales Report - Q4 2024

Revenue Summary:
- Total Revenue: $5.2M
- Year-over-Year Growth: +18%
- Quarter-over-Quarter Growth: +7%

Top Performing Products:
- Product A: $2.1M revenue (+25% YoY)
- Product B: $1.8M revenue (+12% YoY)
- Product C: $1.3M revenue (+15% YoY)
"""

uploaded_file = client.files.upload(document_content, filename="sales_report.txt")

# Create a chat with the file attached
chat = client.chat.create(model="grok-4-fast")
chat.append(user("What was the total revenue in this report?", file(uploaded_file.id)))

# Get the response
response = chat.sample()

print(f"Answer: {response.content}")
print(f"\\nUsage: {response.usage}")

# Clean up
client.files.delete(uploaded_file.id)
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Upload a file
document_content = b"""Quarterly Sales Report - Q4 2024

Revenue Summary:
- Total Revenue: $5.2M
- Year-over-Year Growth: +18%
"""

with open("temp_sales.txt", "wb") as f:
    f.write(document_content)

with open("temp_sales.txt", "rb") as f:
    uploaded_file = client.files.create(file=f, purpose="assistants")

# Create a chat with the file
response = client.responses.create(
    model="grok-4-fast",
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "What was the total revenue in this report?"},
                {"type": "input_file", "file_id": uploaded_file.id}
            ]
        }
    ]
)

final_answer = response.output[-1].content[0].text

print(f"Answer: {final_answer}")

# Clean up
client.files.delete(uploaded_file.id)
```

```pythonRequests
import os
import requests

api_key = os.getenv("XAI_API_KEY")
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

# Upload file first
upload_url = "https://api.x.ai/v1/files"
files = {"file": ("sales_report.txt", b"Total Revenue: $5.2M")}
data = {"purpose": "assistants"}
upload_response = requests.post(upload_url, headers={"Authorization": f"Bearer {api_key}"}, files=files, data=data)
file_id = upload_response.json()["id"]

# Create chat with file
chat_url = "https://api.x.ai/v1/responses"
payload = {
    "model": "grok-4-fast",
    "input": [
        {
            "role": "user",
            "content": "What was the total revenue in this report?",
            "attachments": [
                {
                    "file_id": file_id,
                    "tools": [{"type": "file_search"}]
                }
            ]
        }
    ]
}
response = requests.post(chat_url, headers=headers, json=payload)
print(response.json())
```

```bash
# First upload the file
FILE_ID=$(curl https://api.x.ai/v1/files \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -F file=@sales_report.txt \\
  -F purpose=assistants | jq -r '.id')

# Then use it in chat
curl -X POST "https://api.x.ai/v1/responses" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d "{
    \\"model\\": \\"grok-4-fast\\",
    \\"input\\": [
      {
        \\"role\\": \\"user\\",
        \\"content\\": [
          {\\"type\\": \\"input_text\\", \\"text\\": \\"What was the total revenue in this report?\\"},
          {\\"type\\": \\"input_file\\", \\"file_id\\": \\"$FILE_ID\\"}
        ]
      }
    ]
  }"
```

## Streaming Chat with Files

Get real-time responses while the model searches through your documents.

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload a document
document_content = b"""Product Specifications:
- Model: XR-2000
- Weight: 2.5 kg
- Dimensions: 30cm x 20cm x 10cm
- Power: 100W
- Features: Wireless connectivity, LCD display, Energy efficient
"""

uploaded_file = client.files.upload(document_content, filename="specs.txt")

# Create chat with streaming
chat = client.chat.create(model="grok-4-fast")
chat.append(user("What is the weight of the XR-2000?", file(uploaded_file.id)))

# Stream the response
is_thinking = True
for response, chunk in chat.stream():
    # Show tool calls as they happen
    for tool_call in chunk.tool_calls:
        print(f"\\nSearching: {tool_call.function.name}")
    
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    
    if chunk.content and is_thinking:
        print("\\n\\nAnswer:")
        is_thinking = False
    
    if chunk.content:
        print(chunk.content, end="", flush=True)

print(f"\\n\\nUsage: {response.usage}")

# Clean up
client.files.delete(uploaded_file.id)
```

## Multiple File Attachments

Query across multiple documents simultaneously.

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload multiple documents
file1_content = b"Document 1: The project started in January 2024."
file2_content = b"Document 2: The project budget is $500,000."
file3_content = b"Document 3: The team consists of 5 engineers and 2 designers."

file1 = client.files.upload(file1_content, filename="timeline.txt")
file2 = client.files.upload(file2_content, filename="budget.txt")
file3 = client.files.upload(file3_content, filename="team.txt")

# Create chat with multiple files
chat = client.chat.create(model="grok-4-fast")
chat.append(
    user(
        "Based on these documents, when did the project start, what is the budget, and how many people are on the team?",
        file(file1.id),
        file(file2.id),
        file(file3.id),
    )
)

response = chat.sample()

print(f"Answer: {response.content}")
print("\\nDocuments searched: 3")
print(f"Usage: {response.usage}")

# Clean up
client.files.delete(file1.id)
client.files.delete(file2.id)
client.files.delete(file3.id)
```

## Multi-Turn Conversations with Files

Maintain context across multiple questions about the same documents. Use encrypted content to preserve file context efficiently across multiple turns.

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload an employee record
document_content = b"""Employee Information:
Name: Alice Johnson
Department: Engineering
Years of Service: 5
Performance Rating: Excellent
Skills: Python, Machine Learning, Cloud Architecture
Current Project: AI Platform Redesign
"""

uploaded_file = client.files.upload(document_content, filename="employee.txt")

# Create a multi-turn conversation with encrypted content
chat = client.chat.create(
    model="grok-4-fast",
    use_encrypted_content=True,  # Enable encrypted content for efficient multi-turn
)

# First turn: Ask about the employee name
chat.append(user("What is the employee's name?", file(uploaded_file.id)))
response1 = chat.sample()
print("Q1: What is the employee's name?")
print(f"A1: {response1.content}\\n")

# Add the response to conversation history
chat.append(response1)

# Second turn: Ask about department (agentic context is retained via encrypted content)
chat.append(user("What department does this employee work in?"))
response2 = chat.sample()
print("Q2: What department does this employee work in?")
print(f"A2: {response2.content}\\n")

# Add the response to conversation history
chat.append(response2)

# Third turn: Ask about skills
chat.append(user("What skills does this employee have?"))
response3 = chat.sample()
print("Q3: What skills does this employee have?")
print(f"A3: {response3.content}\\n")

# Clean up
client.files.delete(uploaded_file.id)
```

## Combining Files with Other Modalities

You can combine file attachments with images and other content types in a single message.

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file, image

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload a text document with cat care information
text_content = b"Cat Care Guide: Cats require daily grooming, especially long-haired breeds. Regular brushing helps prevent matting and reduces shedding."
text_file = client.files.upload(text_content, filename="cat-care.txt")

# Use both file and image in the same message
chat = client.chat.create(model="grok-4-fast")
chat.append(
    user(
        "Based on the attached care guide, do you have any advice about the pictured cat?",
        file(text_file.id),
        image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg"),
    )
)

response = chat.sample()

print(f"Analysis: {response.content}")
print(f"\\nUsage: {response.usage}")

# Clean up
client.files.delete(text_file.id)
```

## Combining Files with Code Execution

For data analysis tasks, you can attach data files and enable the code execution tool. This allows Grok to write and run Python code to analyze and process your data.

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file
from xai_sdk.tools import code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload a CSV data file
csv_content = b"""product,region,revenue,units_sold
Product A,North,245000,1200
Product A,South,189000,950
Product A,East,312000,1500
Product A,West,278000,1350
Product B,North,198000,800
Product B,South,156000,650
Product B,East,234000,950
Product B,West,201000,850
Product C,North,167000,700
Product C,South,134000,550
Product C,East,198000,800
Product C,West,176000,725
"""

data_file = client.files.upload(csv_content, filename="sales_data.csv")

# Create chat with both file attachment and code execution
chat = client.chat.create(
    model="grok-4-fast",
    tools=[code_execution()],  # Enable code execution
)

chat.append(
    user(
        "Analyze this sales data and calculate: 1) Total revenue by product, 2) Average units sold by region, 3) Which product-region combination has the highest revenue",
        file(data_file.id)
    )
)

# Stream the response to see code execution in real-time
is_thinking = True
for response, chunk in chat.stream():
    for tool_call in chunk.tool_calls:
        if tool_call.function.name == "code_execution":
            print("\\n[Executing Code]")
    
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    
    if chunk.content and is_thinking:
        print("\\n\\nAnalysis Results:")
        is_thinking = False
    
    if chunk.content:
        print(chunk.content, end="", flush=True)

print(f"\\n\\nUsage: {response.usage}")

# Clean up
client.files.delete(data_file.id)
```

The model will:

1. Access the attached data file
2. Write Python code to load and analyze the data
3. Execute the code in a sandboxed environment
4. Perform calculations and statistical analysis
5. Return the results and insights in the response

## Limitations and Considerations

### Request Constraints

* **No batch requests**: File attachments with document search are agentic requests and do not support batch mode (`n > 1`)
* **Streaming recommended**: Use streaming mode for better observability of document search process

### Document Complexity

* Highly unstructured or very long documents may require more processing
* Well-organized documents with clear structure are easier to search
* Large documents with many searches can result in higher token usage

### Model Compatibility

* **Recommended models**: `grok-4-fast`, `grok-4` for best document understanding
* **Agentic requirement**: File attachments require [agentic-capable](/developers/tools/overview) models that support server-side tools.

## Next Steps

Learn more about managing your files:

===/developers/model-capabilities/images/generation===
#### Model Capabilities

# Image Generation

Generate images from text prompts, edit existing images with natural language, or iteratively refine images through multi-turn conversations. The API supports batch generation of multiple images, and control over aspect ratio and resolution.

## Quick Start

Generate an image with a single API call:

Images are returned as URLs by default. URLs are temporary, so download or process promptly. You can also request [base64 output](#base64-output) for embedding images directly.

## Image Editing

Edit an existing image by providing a source image along with your prompt. The model understands the image content and applies your requested changes.

> **Note:** The OpenAI SDK's `images.edit()` method is not supported for image editing because it uses `multipart/form-data`, while the xAI API requires `application/json`. Use the xAI SDK, Vercel AI SDK, or direct HTTP requests instead.

With the xAI SDK, use the same `sample()` method — just add the `image_url` parameter:

You can provide the source image as:

* A **public URL** pointing to an image
* A **base64-encoded data URI** (e.g., `data:image/jpeg;base64,...`)

## Multi-Turn Editing

Chain multiple edits together by using each output as the input for the next. This enables iterative refinement — start with a base image and progressively add details, adjust styles, or make corrections.

The images below show this workflow in action:

## Style Transfer

The `grok-imagine-image` model excels across a wide range of visual styles — from ultra-realistic photography to anime, oil paintings, pencil sketches, and beyond. Transform existing images by simply describing the desired aesthetic in your prompt.

Using `AsyncClient` with `asyncio.gather` lets you process multiple style transfers concurrently, making it significantly faster than sequential requests:

## Configuration

### Multiple Images

Generate multiple images in a single request using the `sample_batch()` method and the `n` parameter. This returns a list of `ImageResponse` objects.

### Aspect Ratio

Control image dimensions with the `aspect_ratio` parameter:

| Ratio | Use case |
|-------|----------|
| `1:1` | Social media, thumbnails |
| `16:9` / `9:16` | Widescreen, mobile, stories |
| `4:3` / `3:4` | Presentations, portraits |
| `3:2` / `2:3` | Photography |
| `2:1` / `1:2` | Banners, headers |
| `19.5:9` / `9:19.5` | Modern smartphone displays |
| `20:9` / `9:20` | Ultra-wide displays |
| `auto` | Model auto-selects the best ratio for the prompt |

### Base64 Output

For embedding images directly without downloading, request base64:

### Response Details

The xAI SDK exposes additional metadata on the response object beyond the image URL or base64 data.

**Moderation** — Check whether the generated image passed content moderation:

**Model** — Get the actual model used (resolving any aliases):

## Pricing

Image generation uses flat per-image pricing rather than token-based pricing like text models. Each generated image incurs a fixed fee regardless of prompt length.

For image editing, you are charged for both the input image and the generated output image.

For full pricing details on the `grok-imagine-image` model, see the [model page](/docs/models/grok-imagine-image).

## Limitations

* **Maximum images per request:** 10
* **URL expiration:** Generated URLs are temporary
* **Content moderation:** Images are subject to content policy review

## Related

* [Models](/docs/models) — Available image models
* [Video Generation](/developers/model-capabilities/video/generation) — Animate generated images
* [API Reference](/api-reference) — Full endpoint documentation

===/developers/model-capabilities/images/understanding===
#### Model Capabilities

# Image Understanding

When sending images, it is advised to not store request/response history on the server. Otherwise the request may fail.
See .

Some models allow images in the input. The model will consider the image context when generating the response.

## Constructing the message body - difference from text-only prompt

The request message to image understanding is similar to text-only prompt. The main difference is that instead of text input:

```json
[
  {
    "role": "user",
    "content": "What is in this image?"
  }
]
```

We send in `content` as a list of objects:

```json
[
  {
    "role": "user",
    "content": [
      {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,<base64_image_string>",
        "detail": "high"
      },
      {
        "type": "input_text",
        "text": "What is in this image?"
      }
    ]
  }
]
```

The `image_url.url` can also be the image's url on the Internet.

### Image understanding example

### Image input general limits

* Maximum image size: `20MiB`
* Maximum number of images: No limit
* Supported image file types: `jpg/jpeg` or `png`.
* Any image/text input order is accepted (e.g. text prompt can precede image prompt)

===/developers/model-capabilities/legacy/chat-completions===
#### Model Capabilities

# Chat Completions

Chat Completions is offered as a legacy endpoint. Most of our new features will come to  first.

Looking to migrate? Check out our [Migrating to Responses API](/developers/model-capabilities/text/comparison) guide for a detailed comparison and migration steps.

Text in, text out. Chat is the most popular feature on the xAI API, and can be used for anything from summarizing articles, generating creative writing, answering questions, providing customer support, to assisting with coding tasks.

## Prerequisites

* xAI Account: You need an xAI account to access the API.
* API Key: Ensure that your API key has access to the Chat Completions endpoint and the model you want to use is enabled.

If you don't have these and are unsure of how to create one, follow [the Hitchhiker's Guide to Grok](/developers/quickstart).

You can create an API key on the [xAI Console API Keys Page](https://console.x.ai/team/default/api-keys).

Set your API key in your environment:

```bash
export XAI_API_KEY="your_api_key"
```

## A basic chat completions example

You can also stream the response, which is covered in [Streaming Response](/developers/model-capabilities/text/streaming).

The user sends a request to the xAI API endpoint. The API processes this and returns a complete response.

Response:

## Conversations

The xAI API is stateless and does not process new request with the context of your previous request history.

However, you can provide previous chat generation prompts and results to a new chat generation request to let the model process your new request with the context in mind.

An example message:

```json
{
  "role": "system",
  "content": [{ "type": "text", "text": "You are a helpful and funny assistant."}]
}
{
  "role": "user",
  "content": [{ "type": "text", "text": "Why don't eggs tell jokes?" }]
},
{
  "role": "assistant",
  "content": [{ "type": "text", "text": "They'd crack up!" }]
},
{
  "role": "user",
  "content": [{"type": "text", "text": "Can you explain the joke?"}],
}
```

By specifying roles, you can change how the model ingests the content.
The `system` role content should define, in an instructive tone, the way the model should respond to user request.
The `user` role content is usually used for user requests or data sent to the model.
The `assistant` role content is usually either in the model's response, or when sent within the prompt, indicates the model's response as part of conversation history.

The `developer` role is supported as an alias for `system`. Only a **single** system/developer message should be used, and it should always be the **first message** in your conversation.

## Image understanding

Some models allow image in the input. The model will consider the image context, when generating the response.

### Constructing the message body - difference from text-only prompt

The request message to image understanding is similar to text-only prompt. The main difference is that instead of text input:

```json
[
{
    "role": "user",
    "content": "What is in this image?"
}
]
```

We send in `content` as a list of objects:

```json
[
{
    "role": "user",
    "content": [
{
    "type": "image_url",
    "image_url": {
    "url": "data:image/jpeg;base64,<base64_image_string>",
    "detail": "high"
}
},
{
    "type": "text",
    "text": "What is in this image?"
}
    ]
}
]
```

The `image_url.url` can also be the image's url on the Internet.

### Image understanding example

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user, image

client = Client(api_key=os.getenv('XAI_API_KEY'))

image_url = "https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png"

chat = client.chat.create(model="grok-4")
chat.append(
    user(
        "What's in this image?",
        image(image_url=image_url, detail="high"),
    )
)

response = chat.sample()
print(response.content)
```

```pythonOpenAISDK
import os
from openai import OpenAI

XAI_API_KEY = os.getenv("XAI_API_KEY")
image_url = (
"https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png"
)

client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": "high",
                },
            },
            {
                "type": "text",
                "text": "What's in this image?",
            },
        ],
    },
]

completion = client.chat.completions.create(
    model="grok-4",
    messages=messages,
)

print(completion.choices[0].message.content)
```

```javascriptOpenAISDK
import OpenAI from "openai";
const openai = new OpenAI({
apiKey: process.env.XAI_API_KEY,
baseURL: "https://api.x.ai/v1",
});
const image_url =
"https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png";

const completion = await openai.chat.completions.create({
    model: "grok-4",
    messages: [
        {
            role: "user",
            content: [
                {
                    type: "image_url",
                    image_url: {
                        url: image_url,
                        detail: "high",
                    },
                },
                {
                    type: "text",
                    text: "What's in this image?",
                },
            ],
        },
    ],
});

console.log(completion.choices[0].message.content);
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const result = await generateText({
model: "grok-4",
messages: [
        {
            role: 'user',
            content: [
                {
                    type: 'image',
                    image: new URL(
                        'https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png',
                    ),
                },
                {
                    type: 'text',
                    text: "What's in this image?",
                },
            ],
        },
    ],
});

console.log(result.text);
```

### Image input general limits

* Maximum image size: `20MiB`
* Maximum number of images: No limit
* Supported image file types: `jpg/jpeg` or `png`.
* Any image/text input order is accepted (e.g. text prompt can precede image prompt)

### Image detail levels

The `"detail"` field controls the level of pre-processing applied to the image that will be provided to the model. It is optional and determines the resolution at which the image is processed. The possible values for `"detail"` are:

* **`"auto"`**: The system will automatically determine the image resolution to use. This is the default setting, balancing speed and detail based on the model's assessment.
* **`"low"`**: The system will process a low-resolution version of the image. This option is faster and consumes fewer tokens, making it more cost-effective, though it may miss finer details.
* **`"high"`**: The system will process a high-resolution version of the image. This option is slower and more expensive in terms of token usage, but it allows the model to attend to more nuanced details in the image.

===/developers/model-capabilities/text/comparison===
#### Model Capabilities

# Comparison with Chat Completions API

The Responses API is the recommended way to interact with xAI models. Here's how it compares to the legacy Chat Completions API:

| Feature | Responses API | Chat Completions API (Deprecated) |
|---------|---------------|-----------------------------------|
| **Stateful Conversations** |  Built-in support via `previous_response_id` |  Stateless - must resend full history |
| **Server-side Storage** |  Responses stored for 30 days |  No storage - manage history yourself |
| **Reasoning Models** |  Full support with encrypted reasoning content |  Limited - only `grok-3-mini` returns `reasoning_content` |
| **Agentic Tools** |  Native support for tools (search, code execution, MCP) |  Function calling only |
| **Billing Optimization** |  Automatic caching of conversation history |  Full history billed on each request |
| **Future Features** |  All new capabilities delivered here first |  Legacy endpoint, limited updates |

## Key API Changes

### Parameter Mapping

| Chat Completions | Responses API | Notes |
|-----------------|---------------|-------|
| `messages` | `input` | Array of message objects |
| `max_tokens` | `max_output_tokens` | Maximum tokens to generate |
| — | `previous_response_id` | Continue a stored conversation |
| — | `store` | Control server-side storage (default: `true`) |
| — | `include` | Request additional data like `reasoning.encrypted_content` |

### Response Structure

The response format differs between the two APIs:

**Chat Completions** returns content in `choices[0].message.content`:

```json
{
  "id": "chatcmpl-123",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you?"
    }
  }]
}
```

**Responses API** returns content in an `output` array with typed items:

```json
{
  "id": "resp_123",
  "output": [{
    "type": "message",
    "role": "assistant",
    "content": [{
      "type": "output_text",
      "text": "Hello! How can I help you?"
    }]
  }]
}
```

### Multi-turn Conversations

With Chat Completions, you must resend the entire conversation history with each request. With Responses API, you can use `previous_response_id` to continue a conversation:

```pythonWithoutSDK
# First request
response = client.responses.create(
    model="grok-4",
    input=[{"role": "user", "content": "What is 2+2?"}],
)

# Continue the conversation - no need to resend history
second_response = client.responses.create(
    model="grok-4",
    previous_response_id=response.id,
    input=[{"role": "user", "content": "Now multiply that by 10"}],
)
```

## Migration Path

Migrating from Chat Completions to Responses API is straightforward. Here's how to update your code for each SDK:

### Vercel AI SDK

Switch from `xai()` to `xai.responses()`:

```javascriptAISDK deletedLines="1" addedLines="2"
  model: xai('grok-4'),
  model: xai.responses('grok-4'),
```

### OpenAI SDK (JavaScript)

Switch from `client.chat.completions.create` to `client.responses.create`, and rename `messages` to `input`:

```javascriptWithoutSDK deletedLines="1,3" addedLines="2,4"
const response = await client.chat.completions.create({
const response = await client.responses.create({
    messages: [
    input: [
        { role: "user", content: "Hello!" }
    ],
});
```

### OpenAI SDK (Python)

Switch from `client.chat.completions.create` to `client.responses.create`, and rename `messages` to `input`:

```pythonWithoutSDK deletedLines="1,3" addedLines="2,4"
response = client.chat.completions.create(
response = client.responses.create(
    messages=[
    input=[
        {"role": "user", "content": "Hello!"}
    ],
)
```

### cURL

Change the endpoint from `/v1/chat/completions` to `/v1/responses`, and rename `messages` to `input`:

```bash deletedLines="1,5" addedLines="2,6"
curl https://api.x.ai/v1/chat/completions \
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{ "model": "grok-4", "messages": [{"role": "user", "content": "Hello!"}] }'
  -d '{ "model": "grok-4", "input": [{"role": "user", "content": "Hello!"}] }'
```

This will work for most use cases. If you have a unique integration, refer to the [Responses API documentation](/developers/model-capabilities/text/generate-text) for detailed guidance.

===/developers/model-capabilities/text/generate-text===
#### Model Capabilities

# Generate Text

The Responses API is the preferred way of interacting with our models via API. It allows optional **stateful interactions** with our models,
where **previous input prompts, reasoning content and model responses are saved and stored on xAI's servers**. You can continue the interaction by appending new
prompt messages instead of resending the full conversation. This behavior is on by default. If you would like to store your request/response locally, please see [Disable storing previous request/response on server](#disable-storing-previous-requestresponse-on-server).

Although you don't need to enter the conversation history in the request body, you will still be
billed for the entire conversation history when using Responses API. The cost might be reduced as
part of the conversation history is .

**The responses will be stored for 30 days, after which they will be removed. This means you can use the response ID to retrieve or continue a conversation within 30 days of sending the request.**
If you want to continue a conversation after 30 days, please store your responses history and the encrypted thinking content locally, and pass them in a new request body.

For Python, we also offer our [xAI SDK](https://github.com/xai-org/xai-sdk-python) which covers all of our features and uses gRPC for optimal performance. It's fine to mix both. The xAI SDK allows you to interact with all our products such as Collections, Voice API, API key management, and more, while the Responses API is more suited for chatbots and usage in RESTful APIs.

## Prerequisites

* xAI Account: You need an xAI account to access the API.
* API Key: Ensure that your API key has access to the Responses API endpoint and the model you want to use is enabled.

If you don't have these and are unsure of how to create one, follow [the Hitchhiker's Guide to Grok](/developers/quickstart).

You can create an API key on the [xAI Console API Keys Page](https://console.x.ai/team/default/api-keys).

Set your API key in your environment:

```bash
export XAI_API_KEY="your_api_key"
```

## Creating a new model response

The first step in using Responses API is analogous to using the legacy Chat Completions API. You will create a new response with prompts. By default, your request/response history is stored on our server.

`instructions` parameter is currently not supported. The API will return an error if it is specified.

The `developer` role is supported as an alias for `system`. Only a **single** system/developer message should be used, and it should always be the **first message** in your conversation.

### Disable storing previous request/response on server

If you do not want to store your previous request/response on the server, you can set `store: false` on the request.

### Returning encrypted thinking content

If you want to return the encrypted thinking traces, you need to specify `use_encrypted_content=True` in xAI SDK or gRPC request message, or `include: ["reasoning.encrypted_content"]` in the request body.

Modify the steps to create a chat client (xAI SDK) or change the request body as following:

See [Adding encrypted thinking content](#adding-encrypted-thinking-content) on how to use the returned encrypted thinking content when making a new request.

## Chaining the conversation

We now have the `id` of the first response. With Chat Completions API, we typically send a stateless new request with all the previous messages.

With Responses API, we can send the `id` of the previous response, and the new messages to append to it.

### Adding encrypted thinking content

After returning the encrypted thinking content, you can also add it to a new response's input:

## Retrieving a previous model response

If you have a previous response's ID, you can retrieve the content of the response.

## Delete a model response

If you no longer want to store the previous model response, you can delete it.

===/developers/model-capabilities/text/reasoning===
#### Model Capabilities

# Reasoning

`presencePenalty`, `frequencyPenalty` and `stop` parameters are not supported by reasoning models.
Adding them in the request would result in an error.

## Key Features

* **Think Before Responding**: Thinks through problems step-by-step before delivering an answer.
* **Math & Quantitative Strength**: Excels at numerical challenges and logic puzzles.
* **Reasoning Trace**: Usage metrics expose `reasoning_tokens`. Some models can also return encrypted reasoning via `include: ["reasoning.encrypted_content"]` (see below).

In Chat Completions, only `grok-3-mini` returns `message.reasoning_content`.

`grok-3`, `grok-4` and `grok-4-fast-reasoning` do not return `reasoning_content`. If supported, you can request [encrypted reasoning content](#encrypted-reasoning-content) via `include: ["reasoning.encrypted_content"]` in the Responses API instead.

### Encrypted Reasoning Content

For `grok-4`, the reasoning content is encrypted by us and can be returned if you pass `include: ["reasoning.encrypted_content"]` to the Responses API. You can send the encrypted content back to provide more context to a previous conversation. See [Adding encrypted thinking content](/developers/model-capabilities/text/generate-text#adding-encrypted-thinking-content) for more details on how to use the content.

## Control how hard the model thinks

`reasoning_effort` is not supported by `grok-3`, `grok-4` and `grok-4-fast-reasoning`. Specifying `reasoning_effort` parameter will get
an error response. Only `grok-3-mini` supports `reasoning_effort`.

The `reasoning_effort` parameter controls how much time the model spends thinking before responding. It must be set to one of these values:

* **`low`**: Minimal thinking time, using fewer tokens for quick responses.
* **`high`**: Maximum thinking time, leveraging more tokens for complex problems.

Choosing the right level depends on your task: use `low` for simple queries that should complete quickly, and `high` for harder problems where response latency is less important.

## Usage Example

Here’s a simple example using `grok-3-mini` to multiply 101 by 3.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import system, user

client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    timeout=3600, # Override default timeout with longer timeout for reasoning models
)

chat = client.chat.create(
    model="grok-3-mini",
    reasoning_effort="high",
    messages=[system("You are a highly intelligent AI assistant.")],
)
chat.append(user("What is 101\*3?"))

response = chat.sample()

print("Final Response:")
print(response.content)

print("Number of completion tokens:")
print(response.usage.completion_tokens)

print("Number of reasoning tokens:")
print(response.usage.reasoning_tokens)
```

```pythonOpenAISDK
import os
import httpx
from openai import OpenAI

client = OpenAI(
    base_url="https://api.x.ai/v1",
    api_key=os.getenv("XAI_API_KEY"),
    timeout=httpx.Timeout(3600.0), # Override default timeout with longer timeout for reasoning models
)

response = client.responses.create(
    model="grok-3-mini",
    reasoning={"effort": "high"},
    input=[
        {"role": "system", "content": "You are a highly intelligent AI assistant."},
        {"role": "user", "content": "What is 101*3?"},
    ],
)

message = next(item for item in response.output if item.type == "message")
text = next(c.text for c in message.content if c.type == "output_text")

print("Final Response:")
print(text)

print("Number of output tokens:")
print(response.usage.output_tokens)

print("Number of reasoning tokens:")
print(response.usage.output_tokens_details.reasoning_tokens)
```

```javascriptOpenAISDK
import OpenAI from "openai";

const client = new OpenAI({
    apiKey: "<api key>",
    baseURL: "https://api.x.ai/v1",
    timeout: 360000, // Override default timeout with longer timeout for reasoning models
});

const response = await client.responses.create({
    model: "grok-3-mini",
    reasoning: { effort: "high" },
    input: [
        {
            "role": "system",
            "content": "You are a highly intelligent AI assistant.",
        },
        {
            "role": "user",
            "content": "What is 101*3?",
        },
    ],
});

// Find the message in the output array
const message = response.output.find((item) => item.type === "message");
const textContent = message?.content?.find((c) => c.type === "output_text");

console.log("\\nFinal Response:", textContent?.text);

console.log("\\nNumber of output tokens:", response.usage.output_tokens);

console.log("\\nNumber of reasoning tokens:", response.usage.output_tokens_details.reasoning_tokens);
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const result = await generateText({
  model: xai.responses('grok-3-mini'),
  system: 'You are a highly intelligent AI assistant.',
  prompt: 'What is 101*3?',
});

console.log('Final Response:', result.text);
console.log('Number of completion tokens:', result.totalUsage.completionTokens);
console.log('Number of reasoning tokens:', result.totalUsage.reasoningTokens);
```

```bash
curl https://api.x.ai/v1/responses \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer $XAI_API_KEY" \\
-m 3600 \\
-d '{
    "input": [
        {
            "role": "system",
            "content": "You are a highly intelligent AI assistant."
        },
        {
            "role": "user",
            "content": "What is 101*3?"
        }
    ],
    "model": "grok-3-mini",
    "reasoning": { "effort": "high" },
    "stream": false
}'
```

### Sample Output

```output

Final Response:
The result of 101 multiplied by 3 is 303.

Number of completion tokens:
14

Number of reasoning tokens:
310
```

## Notes on Consumption

When you use a reasoning model, the reasoning tokens are also added to your final consumption amount. The reasoning token consumption will likely increase when you use a higher `reasoning_effort` setting.

===/developers/model-capabilities/text/streaming===
#### Model Capabilities

# Streaming

Streaming outputs is **supported by all models with text output capability** (Chat, Image Understanding, etc.). It is **not supported by models with image output capability** (Image Generation).

Streaming outputs uses [Server-Sent Events (SSE)](https://en.wikipedia.org/wiki/Server-sent_events) that let the server send back the delta of content in event streams.

Streaming responses are beneficial for providing real-time feedback, enhancing user interaction by allowing text to be displayed as it's generated.

To enable streaming, you must set `"stream": true` in your request.

When using streaming output with reasoning models, you might want to **manually override request
timeout** to avoid prematurely closing connection.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user, system

client = Client(
    api_key=os.getenv('XAI_API_KEY'),
    timeout=3600, # Override default timeout with longer timeout for reasoning models
)

chat = client.chat.create(model="grok-4-1-fast-reasoning")
chat.append(
    system("You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."),
)
chat.append(
    user("What is the meaning of life, the universe, and everything?")
)

for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True) # Each chunk's content
    print(response.content, end="", flush=True) # The response object auto-accumulates the chunks

print(response.content) # The full response
```

```pythonOpenAISDK
import os
import httpx
from openai import OpenAI

XAI_API_KEY = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
    timeout=httpx.Timeout(3600.0) # Timeout after 3600s for reasoning models
)

stream = client.chat.completions.create(
    model="grok-4-1-fast-reasoning",
    messages=[
        {"role": "system", "content": "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."},
        {"role": "user", "content": "What is the meaning of life, the universe, and everything?"},
    ],
    stream=True # Set streaming here
)

for chunk in stream:
    print(chunk.choices[0].delta.content, end="", flush=True)
```

```javascriptOpenAISDK
import OpenAI from "openai";
const openai = new OpenAI({
    apiKey: "<api key>",
    baseURL: "https://api.x.ai/v1",
    timeout: 360000, // Timeout after 3600s for reasoning models
});

const stream = await openai.chat.completions.create({
    model: "grok-4-1-fast-reasoning",
    messages: [
        { role: "system", content: "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy." },
        {
            role: "user",
            content: "What is the meaning of life, the universe, and everything?",
        }
    ],
    stream: true
});

for await (const chunk of stream) {
    console.log(chunk.choices[0].delta.content);
}
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { streamText } from 'ai';

const result = streamText({
  model: xai.responses('grok-4'),
  system:
    "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy.",
  prompt: 'What is the meaning of life, the universe, and everything?',
});

for await (const chunk of result.textStream) {
  process.stdout.write(chunk);
}
```

```bash
curl https://api.x.ai/v1/chat/completions \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer $XAI_API_KEY" \\
-m 3600 \\
-d '{
    "messages": [
        {
            "role": "system",
            "content": "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."
        },
        {
            "role": "user",
            "content": "What is the meaning of life, the universe, and everything?"
        }
    ],
    "model": "grok-4-1-fast-reasoning",
    "stream": true
}'
```

You'll get the event streams like these:

```json
data: {
    "id":"<completion_id>","object":"chat.completion.chunk","created":<creation_time>,
    "model":"grok-4-1-fast-reasoning",
    "choices":[{"index":0,"delta":{"content":"Ah","role":"assistant"}}],
    "usage":{"prompt_tokens":41,"completion_tokens":1,"total_tokens":42,
    "prompt_tokens_details":{"text_tokens":41,"audio_tokens":0,"image_tokens":0,"cached_tokens":0}},
    "system_fingerprint":"fp_xxxxxxxxxx"
}

data: {
    "id":"<completion_id>","object":"chat.completion.chunk","created":<creation_time>,
    "model":"grok-4-1-fast-reasoning",
    "choices":[{"index":0,"delta":{"content":",","role":"assistant"}}],
    "usage":{"prompt_tokens":41,"completion_tokens":2,"total_tokens":43,
    "prompt_tokens_details":{"text_tokens":41,"audio_tokens":0,"image_tokens":0,"cached_tokens":0}},
    "system_fingerprint":"fp_xxxxxxxxxx"
}

data: [DONE]
```

It is recommended that you use a client SDK to parse the event stream.

Example streaming responses in Python/Javascript:

```
Ah, the ultimate question! According to Douglas Adams, the answer is **42**. However, the trick lies in figuring out what the actual question is. If you're looking for a bit more context or a different perspective:

- **Philosophically**: The meaning of life might be to seek purpose, happiness, or to fulfill one's potential.
- **Biologically**: It could be about survival, reproduction, and passing on genes.
- **Existentially**: You create your own meaning through your experiences and choices.

But let's not forget, the journey to find this meaning might just be as important as the answer itself! Keep exploring, questioning, and enjoying the ride through the universe. And remember, don't panic!
```

===/developers/model-capabilities/text/structured-outputs===
#### Model Capabilities

# Structured Outputs

Structured Outputs is a feature that lets the API return responses in a specific, organized format, like JSON or other schemas you define. Instead of getting free-form text, you receive data that's consistent and easy to parse.

Ideal for tasks like document parsing, entity extraction, or report generation, it lets you define schemas using tools like
[Pydantic](https://pydantic.dev/) or [Zod](https://zod.dev/) to enforce data types, constraints, and structure.

When using structured outputs, the LLM's response is **guaranteed** to match your input schema.

## Supported models

Structured outputs is supported by all language models.

## Supported schemas

For structured output, the following types are supported for structured output:

* string
  * `minLength` and `maxLength` properties are not supported
* number
  * integer
  * float
* object
* array
  * `minItems` and `maxItem` properties are not supported
  * `maxContains` and `minContains` properties are not supported
* boolean
* enum
* anyOf

`allOf` is not supported at the moment.

## Example: Invoice Parsing

A common use case for Structured Outputs is parsing raw documents. For example, invoices contain structured data like vendor details, amounts, and dates, but extracting this data from raw text can be error-prone. Structured Outputs ensure the extracted data matches a predefined schema.

Let's say you want to extract the following data from an invoice:

* Vendor name and address
* Invoice number and date
* Line items (description, quantity, price)
* Total amount and currency

We'll use structured outputs to have Grok generate a strongly-typed JSON for this.

### Step 1: Defining the Schema

You can use [Pydantic](https://pydantic.dev/) or [Zod](https://zod.dev/) to define your schema.

```pythonWithoutSDK
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class LineItem(BaseModel):
    description: str = Field(description="Description of the item or service")
    quantity: int = Field(description="Number of units", ge=1)
    unit_price: float = Field(description="Price per unit", ge=0)

class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City")
    postal_code: str = Field(description="Postal/ZIP code")
    country: str = Field(description="Country")

class Invoice(BaseModel):
    vendor_name: str = Field(description="Name of the vendor")
    vendor_address: Address = Field(description="Vendor's address")
    invoice_number: str = Field(description="Unique invoice identifier")
    invoice_date: date = Field(description="Date the invoice was issued")
    line_items: list[LineItem] = Field(description="List of purchased items/services")
    total_amount: float = Field(description="Total amount due", ge=0)
    currency: Currency = Field(description="Currency of the invoice")
```

```javascriptWithoutSDK
import { z } from "zod";

const CurrencyEnum = z.enum(["USD", "EUR", "GBP"]);

const LineItemSchema = z.object({
    description: z.string().describe("Description of the item or service"),
    quantity: z.number().int().min(1).describe("Number of units"),
    unit_price: z.number().min(0).describe("Price per unit"),
});

const AddressSchema = z.object({
    street: z.string().describe("Street address"),
    city: z.string().describe("City"),
    postal_code: z.string().describe("Postal/ZIP code"),
    country: z.string().describe("Country"),
});

const InvoiceSchema = z.object({
    vendor_name: z.string().describe("Name of the vendor"),
    vendor_address: AddressSchema.describe("Vendor's address"),
    invoice_number: z.string().describe("Unique invoice identifier"),
    invoice_date: z.string().date().describe("Date the invoice was issued"),
    line_items: z.array(LineItemSchema).describe("List of purchased items/services"),
    total_amount: z.number().min(0).describe("Total amount due"),
    currency: CurrencyEnum.describe("Currency of the invoice"),
});
```

### Step 2: Prepare The Prompts

### System Prompt

The system prompt instructs the model to extract invoice data from text. Since the schema is defined separately, the prompt can focus on the task without explicitly specifying the required fields in the output JSON.

```text
Given a raw invoice, carefully analyze the text and extract the relevant invoice data into JSON format.
```

### Example Invoice Text

```text
Vendor: Acme Corp, 123 Main St, Springfield, IL 62704
Invoice Number: INV-2025-001
Date: 2025-02-10
Items:
- Widget A, 5 units, $10.00 each
- Widget B, 2 units, $15.00 each
Total: $80.00 USD
```

### Step 3: The Final Code

Use the structured outputs feature of the the SDK to parse the invoice.

```pythonXAI
import os
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from xai_sdk import Client
from xai_sdk.chat import system, user

# Pydantic Schemas

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class LineItem(BaseModel):
    description: str = Field(description="Description of the item or service")
    quantity: int = Field(description="Number of units", ge=1)
    unit_price: float = Field(description="Price per unit", ge=0)

class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City")
    postal_code: str = Field(description="Postal/ZIP code")
    country: str = Field(description="Country")

class Invoice(BaseModel):
    vendor_name: str = Field(description="Name of the vendor")
    vendor_address: Address = Field(description="Vendor's address")
    invoice_number: str = Field(description="Unique invoice identifier")
    invoice_date: date = Field(description="Date the invoice was issued")
    line_items: list[LineItem] = Field(description="List of purchased items/services")
    total_amount: float = Field(description="Total amount due", ge=0)
    currency: Currency = Field(description="Currency of the invoice")

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(model="grok-4-1-fast-reasoning")

chat.append(system("Given a raw invoice, carefully analyze the text and extract the invoice data into JSON format."))
chat.append(
user("""
Vendor: Acme Corp, 123 Main St, Springfield, IL 62704
Invoice Number: INV-2025-001
Date: 2025-02-10
Items: - Widget A, 5 units, $10.00 each - Widget B, 2 units, $15.00 each
Total: $80.00 USD
""")
)

# The parse method returns a tuple of the full response object as well as the parsed pydantic object.

response, invoice = chat.parse(Invoice)
assert isinstance(invoice, Invoice)

# Can access fields of the parsed invoice object directly

print(invoice.vendor_name)
print(invoice.invoice_number)
print(invoice.invoice_date)
print(invoice.line_items)
print(invoice.total_amount)
print(invoice.currency)

# Can also access fields from the raw response object such as the content.

# In this case, the content is the JSON schema representation of the parsed invoice object

print(response.content)
```

```pythonOpenAISDK
from openai import OpenAI

from pydantic import BaseModel, Field
from datetime import date
from enum import Enum

# Pydantic Schemas

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class LineItem(BaseModel):
    description: str = Field(description="Description of the item or service")
    quantity: int = Field(description="Number of units", ge=1)
    unit_price: float = Field(description="Price per unit", ge=0)

class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City")
    postal_code: str = Field(description="Postal/ZIP code")
    country: str = Field(description="Country")

class Invoice(BaseModel):
    vendor_name: str = Field(description="Name of the vendor")
    vendor_address: Address = Field(description="Vendor's address")
    invoice_number: str = Field(description="Unique invoice identifier")
    invoice_date: date = Field(description="Date the invoice was issued")
    line_items: list[LineItem] = Field(description="List of purchased items/services")
    total_amount: float = Field(description="Total amount due", ge=0)
    currency: Currency = Field(description="Currency of the invoice")

client = OpenAI(
    api_key="<YOUR_XAI_API_KEY_HERE>",
    base_url="https://api.x.ai/v1",
)

completion = client.beta.chat.completions.parse(
    model="grok-4-1-fast-reasoning",
    messages=[
    {"role": "system", "content": "Given a raw invoice, carefully analyze the text and extract the invoice data into JSON format."},
    {"role": "user", "content": """
    Vendor: Acme Corp, 123 Main St, Springfield, IL 62704
    Invoice Number: INV-2025-001
    Date: 2025-02-10
    Items:

    - Widget A, 5 units, $10.00 each
    - Widget B, 2 units, $15.00 each
      Total: $80.00 USD
      """}
      ],
      response_format=Invoice,
  )

invoice = completion.choices[0].message.parsed
print(invoice)
```

```javascriptOpenAISDK
import OpenAI from "openai";
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from "zod";

const CurrencyEnum = z.enum(["USD", "EUR", "GBP"]);

const LineItemSchema = z.object({
    description: z.string().describe("Description of the item or service"),
    quantity: z.number().int().min(1).describe("Number of units"),
    unit_price: z.number().min(0).describe("Price per unit"),
});

const AddressSchema = z.object({
    street: z.string().describe("Street address"),
    city: z.string().describe("City"),
    postal_code: z.string().describe("Postal/ZIP code"),
    country: z.string().describe("Country"),
});

const InvoiceSchema = z.object({
    vendor_name: z.string().describe("Name of the vendor"),
    vendor_address: AddressSchema.describe("Vendor's address"),
    invoice_number: z.string().describe("Unique invoice identifier"),
    invoice_date: z.string().date().describe("Date the invoice was issued"),
    line_items: z.array(LineItemSchema).describe("List of purchased items/services"),
    total_amount: z.number().min(0).describe("Total amount due"),
    currency: CurrencyEnum.describe("Currency of the invoice"),
});

const client = new OpenAI({
    apiKey: "<api key>",
    baseURL: "https://api.x.ai/v1",
});

const completion = await client.beta.chat.completions.parse({
    model: "grok-4-1-fast-reasoning",
    messages: [
    { role: "system", content: "Given a raw invoice, carefully analyze the text and extract the invoice data into JSON format." },
    { role: "user", content: \`
    Vendor: Acme Corp, 123 Main St, Springfield, IL 62704
    Invoice Number: INV-2025-001
    Date: 2025-02-10
    Items:

    - Widget A, 5 units, $10.00 each
    - Widget B, 2 units, $15.00 each
      Total: $80.00 USD
      \` },
    ],
    response_format: zodResponseFormat(InvoiceSchema, "invoice"),
});

const invoice = completion.choices[0].message.parsed;
console.log(invoice);
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText, Output } from 'ai';
import { z } from 'zod';

const CurrencyEnum = z.enum(['USD', 'EUR', 'GBP']);

const LineItemSchema = z.object({
  description: z.string().describe('Description of the item or service'),
  quantity: z.number().int().min(1).describe('Number of units'),
  unit_price: z.number().min(0).describe('Price per unit'),
});

const AddressSchema = z.object({
  street: z.string().describe('Street address'),
  city: z.string().describe('City'),
  postal_code: z.string().describe('Postal/ZIP code'),
  country: z.string().describe('Country'),
});

const InvoiceSchema = z.object({
  vendor_name: z.string().describe('Name of the vendor'),
  vendor_address: AddressSchema.describe("Vendor's address"),
  invoice_number: z.string().describe('Unique invoice identifier'),
  invoice_date: z.string().date().describe('Date the invoice was issued'),
  line_items: z
    .array(LineItemSchema)
    .describe('List of purchased items/services'),
  total_amount: z.number().min(0).describe('Total amount due'),
  currency: CurrencyEnum.describe('Currency of the invoice'),
});

const result = await generateText({
  model: xai.responses('grok-4'),
  output: Output.object({ schema: InvoiceSchema }),
  system:
    'Given a raw invoice, carefully analyze the text and extract the invoice data into JSON format.',
  prompt: \`
  Vendor: Acme Corp, 123 Main St, Springfield, IL 62704
  Invoice Number: INV-2025-001
  Date: 2025-02-10
  Items:

  - Widget A, 5 units, $10.00 each
  - Widget B, 2 units, $15.00 each
    Total: $80.00 USD
    \`,
});

console.log(result._output);
```

### Step 4: Type-safe Output

The output will **always** be type-safe and respect the input schema.

```json
{
  "vendor_name": "Acme Corp",
  "vendor_address": {
    "street": "123 Main St",
    "city": "Springfield",
    "postal_code": "62704",
    "country": "IL"
  },
  "invoice_number": "INV-2025-001",
  "invoice_date": "2025-02-10",
  "line_items": [
    { "description": "Widget A", "quantity": 5, "unit_price": 10.0 },
    { "description": "Widget B", "quantity": 2, "unit_price": 15.0 }
  ],
  "total_amount": 80.0,
  "currency": "USD"
}
```

## Structured Outputs with Tools

Structured outputs with tools is only available for the Grok 4 family of models (e.g., `grok-4-1-fast`, `grok-4-fast`, `grok-4-1-fast-non-reasoning`, `grok-4-fast-non-reasoning`).

You can combine structured outputs with tool calling to get type-safe responses from tool-augmented queries. This works with both:

* **[Agentic tool calling](/developers/tools/overview)**: Server-side tools like web search, X search, and code execution that the model orchestrates autonomously.
* **[Function calling](/developers/tools/function-calling)**: User-supplied tools where you define custom functions and handle tool execution yourself.

This combination enables workflows where the model can use tools to gather information and return results in a predictable, strongly-typed format.

### Example: Agentic Tools with Structured Output

This example uses web search to find the latest research on a topic and extracts structured data into a schema:

### Example: Client-side Tools with Structured Output

This example uses a client-side function tool to compute Collatz sequence steps and returns the result in a structured format:

## Alternative: Using `response_format` with `sample()` or `stream()`

When using the xAI Python SDK, there's an alternative way to retrieve structured outputs. Instead of using the `parse()` method, you can pass your Pydantic model directly to the `response_format` parameter when creating a chat, and then use `sample()` or `stream()` to get the response.

### How It Works

When you pass a Pydantic model to `response_format`, the SDK automatically:

1. Converts your Pydantic model to a JSON schema
2. Constrains the model's output to conform to that schema
3. Returns the response as a JSON string, that is conforming to the Pydantic model, in `response.content`

You then manually parse the JSON string into your Pydantic model instance.

### Key Differences

| Approach | Method | Returns | Parsing |
|----------|--------|---------|---------|
| **Using `parse()`** | `chat.parse(Model)` | Tuple of `(Response, Model)` | Automatic - SDK parses for you |
| **Using `response_format`** | `chat.sample()` or `chat.stream()` | `Response` with JSON string | Manual - You parse `response.content` |

### When to Use Each Approach

* **Use `parse()`** when you want the simplest, most convenient experience with automatic parsing
* **Use `response_format` + `sample()` or `stream()`** when you:
  * Want more control over the parsing process
  * Need to handle the raw JSON string before parsing
  * Want to use streaming with structured outputs
  * Are integrating with existing code that expects to work with `sample()` or `stream()`

### Example Using `response_format`

```pythonXAI
import os
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field
from xai_sdk import Client
from xai_sdk.chat import system, user

# Pydantic Schemas
class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class LineItem(BaseModel):
    description: str = Field(description="Description of the item or service")
    quantity: int = Field(description="Number of units", ge=1)
    unit_price: float = Field(description="Price per unit", ge=0)


class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City")
    postal_code: str = Field(description="Postal/ZIP code")
    country: str = Field(description="Country")


class Invoice(BaseModel):
    vendor_name: str = Field(description="Name of the vendor")
    vendor_address: Address = Field(description="Vendor's address")
    invoice_number: str = Field(description="Unique invoice identifier")
    invoice_date: date = Field(description="Date the invoice was issued")
    line_items: list[LineItem] = Field(description="List of purchased items/services")
    total_amount: float = Field(description="Total amount due", ge=0)
    currency: Currency = Field(description="Currency of the invoice")


client = Client(api_key=os.getenv("XAI_API_KEY"))

# Pass the Pydantic model to response_format instead of using parse()
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    response_format=Invoice,  # Pass the Pydantic model here
)

chat.append(system("Given a raw invoice, carefully analyze the text and extract the invoice data into JSON format."))
chat.append(
    user("""
Vendor: Acme Corp, 123 Main St, Springfield, IL 62704
Invoice Number: INV-2025-001
Date: 2025-02-10
Items: - Widget A, 5 units, $10.00 each - Widget B, 2 units, $15.00 each
Total: $80.00 USD
""")
)

# Use sample() instead of parse() - returns Response object
response = chat.sample()

# The response.content is a valid JSON string conforming to your schema
print(response.content)
# Output: {"vendor_name": "Acme Corp", "vendor_address": {...}, ...}

# Manually parse the JSON string into your Pydantic model
invoice = Invoice.model_validate_json(response.content)
assert isinstance(invoice, Invoice)

# Access fields of the parsed invoice object
print(invoice.vendor_name)
print(invoice.invoice_number)
print(invoice.total_amount)
```

### Streaming with Structured Outputs

You can also use `stream()` with `response_format` to get streaming structured output. The chunks will progressively build up the JSON string:

```pythonXAI
import os

from pydantic import BaseModel, Field
from xai_sdk import Client
from xai_sdk.chat import system, user


class Summary(BaseModel):
    title: str = Field(description="A brief title")
    key_points: list[str] = Field(description="Main points from the text")
    sentiment: str = Field(description="Overall sentiment: positive, negative, or neutral")


client = Client(api_key=os.getenv("XAI_API_KEY"))

chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    response_format=Summary,  # Pass the Pydantic model here
)

chat.append(system("Analyze the following text and provide a structured summary."))
chat.append(user("The new product launch exceeded expectations with record sales..."))


# Stream the response - chunks contain partial JSON
for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True)


# Parse the complete JSON string into your model
summary = Summary.model_validate_json(response.content)
print(f"Title: {summary.title}")
print(f"Sentiment: {summary.sentiment}")
```

===/developers/model-capabilities/video/generation===
#### Model Capabilities

# Video Generation

All video generation/edit requests are deferred requests, where a user sends a video generation/edit request, get a response with a request ID, and retrieve the video result later using the request ID.
If you're using our SDK, it can handle the polling of the result automatically.

## Generate/Edit a Video with Automatic Polling

For easiness of use, our SDK can automatically send the video generation/edit request, and poll for the response until the result is available, or if the request has failed.

Generate a video directly from a text prompt:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.generate(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
)
print(f"Video URL: {response.url}")
```

Generate a video from a user-provided image:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.generate(
    prompt="Generate a video based on the provided image.",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    image_url=<url of the image>,
)
print(f"Video URL: {response.url}")
```

Edit an existing video:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.generate(
    prompt="Make the ball larger.",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    video_url=<url of the video to edit>,
)
print(f"Video URL: {response.url}")
```

## Send a Video Generation Request

If you do not want to use our SDK, or prefer to send a request and retrieve the result yourself, you can still send a regular video generation request. This will return a `response_id` which you can use to retrieve the generated video later.

### Video Generation from Text

Send a request to start generating a video from a text prompt.

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.start(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
)
print(f"Request ID: {response.request_id}")
```

```javascriptWithoutSDK
const response = await fetch('https://api.x.ai/v1/videos/generations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
  body: JSON.stringify({
    prompt: 'A cat playing with a ball',
    model: '{{LATEST_VIDEO_MODEL_NAME}}',
  }),
});
const data = await response.json();
console.log('Request ID:', data.request_id);
```

```bash
curl -X 'POST' https://api.x.ai/v1/videos/generations \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{
      "prompt": "A cat playing with a ball",
      "model": "{{LATEST_VIDEO_MODEL_NAME}}"
  }'
```

The response includes a `request_id`, which you'll use to retrieve the generated video result.

```bash
{"request_id":"aa87081b-1a29-d8a6-e5bf-5807e3a7a561"}
```

### Video Generation from Image

You can also generate a video from an existing image.

To generate from an image:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.start(
    prompt="Generate a video based on the provided image.",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    image_url=<url of the image>,
)
print(f"Request ID: {response.request_id}")
```

```javascriptWithoutSDK
const response = await fetch('https://api.x.ai/v1/videos/generations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
  body: JSON.stringify({
    prompt: 'Generate a video based on the provided image.',
    model: '{{LATEST_VIDEO_MODEL_NAME}}',
    image: { url: '<url of the image>' },
  }),
});
const data = await response.json();
console.log('Request ID:', data.request_id);
```

```bash
curl -X 'POST' https://api.x.ai/v1/videos/generations \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{
      "prompt": "Generate a video based on the provided image.",
      "model": "{{LATEST_VIDEO_MODEL_NAME}}",
      "image": {"url": "<url of the image>"}
  }'
```

### Edit a Video

Provide an input video (via a publicly accessible URL) and a prompt describing the desired changes. The API will generate a new edited video based on your instructions.

**Note:** The input video URL must be a direct, publicly accessible link to the video file. The maximum supported video length is 8.7 seconds.

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.start(
    prompt="Make the ball in the video larger.",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    video_url=<url of the previous video>,
)
print(f"Request ID: {response.request_id}")
```

```javascriptWithoutSDK
const response = await fetch('https://api.x.ai/v1/videos/edits', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
  body: JSON.stringify({
    prompt: 'Make the ball in the video larger.',
    video: { url: '<url of the previous video>' },
    model: '{{LATEST_VIDEO_MODEL_NAME}}',
  }),
});
const data = await response.json();
console.log('Request ID:', data.request_id);
```

```bash
curl -X 'POST' https://api.x.ai/v1/videos/edits \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{
      "prompt": "Make the ball in the video larger.",
      "video": {"url": "<url of the previous video>"},
      "model": "{{LATEST_VIDEO_MODEL_NAME}}"
  }'
```

You will receive a `request_id` in the response body, which you can use to retrieve the edit generation result.

```bash
{"request_id":"a3d1008e-4544-40d4-d075-11527e794e4a"}
```

## Retrieving Video Generation/Edit Results

After making a video generation or edit requests and receiving the video generation `request_id`, you can retrieve
the results using the `request_id`.

```pythonXAI
# After sending the generation request and getting the request_id.

response = client.video.get(request_id)
print(f"Video URL: {response.url}")
```

```javascriptWithoutSDK
// After sending the generation request and getting the request_id.
const requestId = 'aa87081b-1a29-d8a6-e5bf-5807e3a7a561';

const response = await fetch(\`https://api.x.ai/v1/videos/\${requestId}\`, {
  headers: {
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
});
const data = await response.json();
console.log('Video URL:', data.url);
```

```bash
curl -X 'GET' https://api.x.ai/v1/videos/{request_id} \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>'
```

## Specifying Video Output Format

### Video Duration

You can specify the duration of the generated video in seconds. The allowed range is between 1 and 15 seconds.

Video editing doesn't support user-defined `duration`. The edited video will have the same duration of the original video.

Using xAI SDK auto-polling:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.generate(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    duration=10
)
print(f"Video URL: {response.url}")
print(f"Duration: {response.duration}")
```

Sending normal generation request:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.start(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    duration=10
)
print(f"Request ID: {response.request_id}")
```

```javascriptWithoutSDK
const response = await fetch('https://api.x.ai/v1/videos/generations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
  body: JSON.stringify({
    prompt: 'A cat playing with a ball',
    model: '{{LATEST_VIDEO_MODEL_NAME}}',
    duration: 10,
  }),
});
const data = await response.json();
console.log('Request ID:', data.request_id);
```

```bash
curl -X 'POST' https://api.x.ai/v1/videos/generations \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{
      "prompt": "A cat playing with a ball",
      "model": "{{LATEST_VIDEO_MODEL_NAME}}",
      "duration": 10
  }'
```

### Aspect Ratio

You can specify the aspect ratio of the video. The default aspect ratio is 16:9.

The following aspect ratios are supported:

* 16:9
* 4:3
* 1:1
* 9:16
* 3:4
* 3:2
* 2:3

Using xAI SDK auto-polling:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.generate(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    aspect_ratio="4:3"
)
print(f"Video URL: {response.url}")
```

Sending regular generation request:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.start(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    aspect_ratio="4:3"
)
print(f"Request ID: {response.request_id}")
```

```javascriptWithoutSDK
const response = await fetch('https://api.x.ai/v1/videos/generations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
  body: JSON.stringify({
    prompt: 'A cat playing with a ball',
    model: '{{LATEST_VIDEO_MODEL_NAME}}',
    aspect_ratio: '4:3',
  }),
});
const data = await response.json();
console.log('Request ID:', data.request_id);
```

```bash
curl -X 'POST' https://api.x.ai/v1/videos/generations \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{
      "prompt": "A cat playing with a ball",
      "model": "{{LATEST_VIDEO_MODEL_NAME}}",
      "aspect_ratio": "4:3"
  }'
```

### Resolution

You can select a resolution from a list of supported resolutions.

Supported resolutions:

* 720p
* 480p

Using xAI SDK auto-polling:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.generate(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    resolution="720p"
)
print(f"Video URL: {response.url}")
```

Sending regular generation request:

```pythonXAI
from xai_sdk import Client

client = Client()

response = client.video.start(
    prompt="A cat playing with a ball",
    model="{{LATEST_VIDEO_MODEL_NAME}}",
    resolution="720p"
)
print(f"Request ID: {response.request_id}")
```

```javascriptWithoutSDK
const response = await fetch('https://api.x.ai/v1/videos/generations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`,
  },
  body: JSON.stringify({
    prompt: 'A cat playing with a ball',
    model: '{{LATEST_VIDEO_MODEL_NAME}}',
    resolution: '720p',
  }),
});
const data = await response.json();
console.log('Request ID:', data.request_id);
```

```bash
curl -X 'POST' https://api.x.ai/v1/videos/generations \\
  -H 'accept: application/json' \\
  -H 'Authorization: Bearer <API_KEY>' \\
  -H 'Content-Type: application/json' \\
  -d '{
      "prompt": "A cat playing with a ball",
      "model": "{{LATEST_VIDEO_MODEL_NAME}}",
      "resolution": "720p"
  }'
```


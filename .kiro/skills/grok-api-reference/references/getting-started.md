# Grok API - Getting Started

**Sections:** 2

---

## Table of Contents

- developers/introduction
- developers/quickstart

---

===/developers/introduction===
#### Introduction

# What is Grok?

Grok is a family of Large Language Models (LLMs) developed by [xAI](https://x.ai).

Inspired by the Hitchhiker's Guide to the Galaxy, Grok is a maximally truth-seeking AI that provides insightful, unfiltered truths about the universe.

xAI offers an API for developers to programmatically interact with our Grok [models](/developers/models). The same models power our consumer facing services such as [Grok.com](https://grok.com), the [iOS](https://apps.apple.com/us/app/grok/id6670324846) and [Android](https://play.google.com/store/apps/details?id=ai.x.grok) apps, as well as [Grok in X experience](https://grok.x.com).

## What is the xAI API? How is it different from Grok in other services?

The xAI API is a toolkit for developers to integrate xAI's Grok models into their own applications, the xAI API provides the building blocks to create new AI experiences.

To get started building with the xAI API, please head to [The Hitchhiker's Guide to Grok](/developers/quickstart).

## xAI API vs Grok in other services

| Category                      | xAI API                          | Grok.com                          | Mobile Apps                  | Grok in 𝕏                          |
|-------------------------------|----------------------------------|-----------------------------------|----------------------------|------------------------------------|
| **Accessible**                | API (api.x.ai)                   | grok.com + PWA (Android)          | App Store / Play Store     | X.com + 𝕏 apps                     |
| **Billing**                   | xAI                              | xAI / 𝕏                           | xAI / 𝕏                    | 𝕏                                  |
| **Programming Required**      | Yes                              | No                                | No                         | No                                 |
| **Description**               | Programmatic access for developers | Full-featured web AI assistant   | Mobile AI assistant        | X-integrated AI (fewer features)   |

Because these are separate offerings, your purchase on X (e.g. X Premium) won't affect your service status on xAI API, and vice versa.

This documentation is intended for users using xAI API.

===/developers/quickstart===
#### Getting Started

# Getting Started

Welcome! In this guide, we'll walk you through the basics of using the xAI API.

## Step 1: Create an xAI Account

First, you'll need to create an xAI account to access xAI API. Sign up for an account [here](https://accounts.x.ai/sign-up?redirect=cloud-console).

Once you've created an account, you'll need to load it with credits to start using the API.

## Step 2: Generate an API Key

Create an API key via the [API Keys Page](https://console.x.ai/team/default/api-keys) in the xAI API Console.

After generating an API key, we need to save it somewhere safe! We recommend you export it as an environment variable in your terminal or save it to a `.env` file.

```bash
export XAI_API_KEY="your_api_key"
```

## Step 3: Make your first request

With your xAI API key exported as an environment variable, you're ready to make your first API request.

Let's test out the API using `curl`. Paste the following directly into your terminal.

```bash
curl https://api.x.ai/v1/responses \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer $XAI_API_KEY" \\
-m 3600 \\
-d '{
    "input": [
        {
            "role": "system",
            "content": "You are Grok, a highly intelligent, helpful AI assistant."
        },
        {
            "role": "user",
            "content": "What is the meaning of life, the universe, and everything?"
        }
    ],
    "model": "grok-4-1-fast-reasoning"
}'
```

## Step 4: Make a request from Python or Javascript

As well as a native xAI Python SDK, the majority of our APIs are fully compatible with the OpenAI SDK (and the Anthropic SDK, although this is now deprecated). For example, we can make the same request from Python or JavaScript like so:

**Anthropic SDK Deprecated**: The Anthropic SDK compatibility is fully deprecated. Please migrate to the [Responses API](/developers/api-reference#create-new-response) or [gRPC](/developers/grpc-reference).

```pythonXAI
# In your terminal, first run:
# pip install xai-sdk

import os

from xai_sdk import Client
from xai_sdk.chat import user, system

client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    timeout=3600, # Override default timeout with longer timeout for reasoning models
)

chat = client.chat.create(model="grok-4-1-fast-reasoning")
chat.append(system("You are Grok, a highly intelligent, helpful AI assistant."))
chat.append(user("What is the meaning of life, the universe, and everything?"))

response = chat.sample()
print(response.content)
```

```pythonOpenAISDK
# In your terminal, first run:

# pip install openai

import os
import httpx
from openai import OpenAI

XAI_API_KEY = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
    timeout=httpx.Timeout(3600.0), # Override default timeout with longer timeout for reasoning models
)

completion = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "system",
            "content": "You are Grok, a highly intelligent, helpful AI assistant."
        },
        {
            "role": "user",
            "content": "What is the meaning of life, the universe, and everything?"
        },
    ],
)

print(completion.output[0].content)
```

```javascriptAISDK
// In your terminal, first run:
// pnpm add ai @ai-sdk/xai

import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const result = await generateText({
    model: xai.responses('grok-4'),
    system: 'You are Grok, a highly intelligent, helpful AI assistant.',
    prompt: 'What is the meaning of life, the universe, and everything?',
});

console.log(result.text);
```

```javascriptOpenAISDK
// In your terminal, first run:
// npm install openai

import OpenAI from 'openai';

const client = new OpenAI({
    apiKey: "your_api_key",
    baseURL: "https://api.x.ai/v1",
    timeout: 360000, // Override default timeout with longer timeout for reasoning models
});

const response = await client.responses.create({
    model: "grok-4-1-fast-reasoning",
    input: [
        {
            role: "system",
            content:
            "You are Grok, a highly intelligent, helpful AI assistant.",
        },
        {
            role: "user",
            content:
            "What is the meaning of life, the universe, and everything?",
        },
    ],
});

console.log(response.output[0].content);
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
            "content": "You are Grok, a highly intelligent, helpful AI assistant."
        },
        {
            "role": "user",
            "content": "What is the meaning of life, the universe, and everything?"
        }
    ],
    "model": "grok-4-1-fast-reasoning"
}'
```

Certain models also support [Structured Outputs](/developers/model-capabilities/text/structured-outputs), which allows you to enforce a schema for the LLM output.

For an in-depth guide about using Grok for text responses, check out our [Text Generation Guide](/developers/model-capabilities/text/generate-text).

## Step 5: Use Grok to analyze images

Certain grok models can accept both text AND images as an input. For example:

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user, image

client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    timeout=3600, # Override default timeout with longer timeout for reasoning models
)

chat = client.chat.create(model="grok-4")
chat.append(
    user(
        "What's in this image?",
        image("https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png")
    )
)

response = chat.sample()
print(response.content)
```

```pythonOpenAISDK
import os
import httpx
from openai import OpenAI

XAI_API_KEY = os.getenv("XAI_API_KEY")
image_url = "https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png"

client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
    timeout=httpx.Timeout(3600.0), # Override default timeout with longer timeout for reasoning models
)

completion = client.responses.create(
    model="grok-4",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": image_url,
                    "detail": "high",
                },
                {
                    "type": "input_text",
                    "text": "What's in this image?",
                },
            ],
        },
    ],
)
print(completion.output[0].content)
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const imageUrl =
'https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png';

const result = await generateText({
    model: xai.responses('grok-4'),
    messages: [
        {
            role: 'user',
            content: [
                { type: 'image', image: imageUrl },
                { text: "What's in this image?", type: 'text' },
            ],
        },
    ],
});

console.log(result.text);
```

```javascriptOpenAISDK
import OpenAI from "openai";

const client = new OpenAI({
    apiKey: process.env.XAI_API_KEY,
    baseURL: "https://api.x.ai/v1",
    timeout: 360000, // Override default timeout with longer timeout for reasoning models
});

const image_url =
"https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png";

const completion = await client.responses.create({
    model: "grok-4",
    input: [
        {
            role: "user",
            content: [
                {
                    type: "input_image",
                    image_url: image_url,
                    detail: "high",
                },
                {
                    type: "input_text",
                    text: "What's in this image?",
                },
            ],
        },
    ],
});

console.log(completion.output[0].content);
```

```bash
curl https://api.x.ai/v1/responses \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer $XAI_API_KEY" \\
-m 3600 \\
-d '{
    "model": "grok-4",
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png",
                    "detail": "high"
                },
                {
                    "type": "input_text",
                    "text": "Describe this image"
                }
            ]
        }
    ]
}'
```

And voila! Grok will tell you exactly what's in the image:

> This image is a photograph of a region in space, specifically a part of the Carina Nebula, captured by the James Webb Space Telescope. It showcases a stunning view of interstellar gas and dust, illuminated by young, hot stars. The bright points of light are stars, and the colorful clouds are composed of various gases and dust particles. The image highlights the intricate details and beauty of star formation within a nebula.

To learn how to use Grok vision for more advanced use cases, check out our [Image Understanding](/developers/model-capabilities/images/understanding).


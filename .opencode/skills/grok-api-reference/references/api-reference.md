# Grok API - Api Reference

**Sections:** 16

---

## Table of Contents

- developers/api-reference
- developers/migration/models
- developers/models
- developers/rate-limits
- developers/regions
- developers/release-notes
- developers/tools/advanced-usage
- developers/tools/citations
- developers/tools/code-execution
- developers/tools/collections-search
- developers/tools/overview
- developers/tools/remote-mcp
- developers/tools/streaming-and-sync
- developers/tools/tool-usage-details
- developers/tools/web-search
- developers/tools/x-search

---

===/developers/api-reference===
# REST API Reference

The xAI Enterprise API is a robust, high-performance RESTful interface designed for seamless integration into existing systems.
It offers advanced AI capabilities with full compatibility with the OpenAI REST API.

The base for all routes is at `https://api.x.ai`. For all routes, you have to authenticate with the header `Authorization: Bearer <your xAI API key>`.

***

## POST /v1/chat/completions

API endpoint for POST requests to /v1/chat/completions.

```
Method: POST
Path: /v1/chat/completions
```

***

## POST /v1/responses

API endpoint for POST requests to /v1/responses.

```
Method: POST
Path: /v1/responses
```

***

## GET /v1/responses/\{response\_id}

API endpoint for GET requests to /v1/responses/\{response\_id}.

```
Method: GET
Path: /v1/responses/{response_id}
```

***

## DELETE /v1/responses/\{response\_id}

API endpoint for DELETE requests to /v1/responses/\{response\_id}.

```
Method: DELETE
Path: /v1/responses/{response_id}
```

***

**Deprecated**: The Anthropic SDK compatibility is fully deprecated. Please migrate to the [Responses API](#create-new-response) or [gRPC](/developers/grpc-reference).

## POST /v1/messages

API endpoint for POST requests to /v1/messages.

```
Method: POST
Path: /v1/messages
```

***

## POST /v1/images/generations

API endpoint for POST requests to /v1/images/generations.

```
Method: POST
Path: /v1/images/generations
```

***

## POST /v1/images/edits

API endpoint for POST requests to /v1/images/edits.

```
Method: POST
Path: /v1/images/edits
```

***

## POST /v1/videos/generations

API endpoint for POST requests to /v1/videos/generations.

```
Method: POST
Path: /v1/videos/generations
```

***

## POST /v1/videos/edits

API endpoint for POST requests to /v1/videos/edits.

```
Method: POST
Path: /v1/videos/edits
```

***

## GET /v1/videos/\{request\_id}

API endpoint for GET requests to /v1/videos/\{request\_id}.

```
Method: GET
Path: /v1/videos/{request_id}
```

***

## GET /v1/api-key

API endpoint for GET requests to /v1/api-key.

```
Method: GET
Path: /v1/api-key
```

***

## GET /v1/models

API endpoint for GET requests to /v1/models.

```
Method: GET
Path: /v1/models
```

***

## GET /v1/models/\{model\_id}

API endpoint for GET requests to /v1/models/\{model\_id}.

```
Method: GET
Path: /v1/models/{model_id}
```

***

## GET /v1/language-models

API endpoint for GET requests to /v1/language-models.

```
Method: GET
Path: /v1/language-models
```

***

## GET /v1/language-models/\{model\_id}

API endpoint for GET requests to /v1/language-models/\{model\_id}.

```
Method: GET
Path: /v1/language-models/{model_id}
```

***

## GET /v1/image-generation-models

API endpoint for GET requests to /v1/image-generation-models.

```
Method: GET
Path: /v1/image-generation-models
```

***

## GET /v1/image-generation-models/\{model\_id}

API endpoint for GET requests to /v1/image-generation-models/\{model\_id}.

```
Method: GET
Path: /v1/image-generation-models/{model_id}
```

***

## POST /v1/tokenize-text

API endpoint for POST requests to /v1/tokenize-text.

```
Method: POST
Path: /v1/tokenize-text
```

***

## GET /v1/chat/deferred-completion/\{request\_id}

API endpoint for GET requests to /v1/chat/deferred-completion/\{request\_id}.

```
Method: GET
Path: /v1/chat/deferred-completion/{request_id}
```

***

***

## POST /v1/completions

API endpoint for POST requests to /v1/completions.

```
Method: POST
Path: /v1/completions
```

***

**Deprecated**: The Anthropic SDK compatibility is fully deprecated. Please migrate to the [Responses API](#create-new-response) or [gRPC](/developers/grpc-reference).

## POST /v1/complete

API endpoint for POST requests to /v1/complete.

```
Method: POST
Path: /v1/complete
```

***

===/developers/migration/models===
#### Key Information

# Migrating to New Models

As we release newer, more advanced models, we are focusing resources on supporting customers with these models and will
be phasing out older versions.

You will see `deprecated` tag by the deprecated model names on [xAI Console](https://console.x.ai) models page. You
should consider moving to a newer model when the model of your choice is being deprecated.

We may transition a `deprecated` model to `obsolete` and discontinue serving the model across our services.
An `obsolete` model will be removed from our [Models and Pricing](../models) page as well as from [xAI Console](https://console.x.ai).

## Moving from an older generation model

When you move from an older model generation to a newer one, you usually won't need to make significant changes to
how you use the API. In your request body, you can switch the `"model"` field from the deprecating model to a current
model on [xAI Console](https://console.x.ai) models page.

The newer models are more performant, but you might want to check if your prompts and other parameters can work with the
new model and modify if necessary.

## Moving to the latest endpoints

When you are setting up to use new models, it might also be a good idea to ensure you're using the latest endpoints. The
latest endpoints have more stable supports for the model functionalities. Endpoints that are marked with `legacy`
might not receive any updates that support newer functionalities.

In general, the following endpoints are recommended: - Text and image input and text output: [Chat Completions](/developers/api-reference#chat-completions) - `/v1/chat/completions` - Text input and image output: [Image Generation](/developers/api-reference#image-generation) - `/v1/image/generations` - Tokenization: [Tokenize Text](/developers/api-reference#tokenize-text) - `/v1/tokenize-text`

===/developers/models===
#### Key Information

# Models and Pricing

An overview of our models' capabilities and their associated pricing.

## Model Pricing


When moving from `grok-3`/`grok-3-mini` to `grok-4`, please note the following differences:

## Tools Pricing

Requests which make use of xAI provided [server-side tools](/developers/tools/overview) are priced based on two components: **token usage** and **server-side tool invocations**. Since the agent autonomously decides how many tools to call, costs scale with query complexity.

### Token Costs

All standard token types are billed at the [rate](#model-pricing) for the model used in the request:

* **Input tokens**: Your query and conversation history
* **Reasoning tokens**: Agent's internal thinking and planning
* **Completion tokens**: The final response
* **Image tokens**: Visual content analysis (when applicable)
* **Cached prompt tokens**: Prompt tokens that were served from cache rather than recomputed

### Tool Invocation Costs

| Tool | Cost per 1,000 calls | Description |
|------|---------------------|-------------|
| **[Web Search](/developers/tools/web-search)** | $5 | Internet search and page browsing |
| **[X Search](/developers/tools/x-search)** | $5 | X posts, users, and threads |
| **[Code Execution](/developers/tools/code-execution)** | $5 | Python code execution environment |
| **[Document Search](/developers/files)** | $5 | Search through uploaded files and documents |
| **[View Image](/developers/tools/web-search#enable-image-understanding)** | Token-based only | Image analysis within search results |
| **[View X Video](/developers/tools/x-search#enable-video-understanding)** | Token-based only | Video analysis within X posts |
| **[Collections Search](/developers/tools/collections-search)** | $2.50 | Knowledge base search using xAI Collections |
| **[Remote MCP Tools](/developers/tools/remote-mcp)** | Token-based only | Custom MCP tools |

For the view image and view x video tools, you will not be charged for the tool invocation itself but will be charged for the image tokens used to process the image or video.

For Remote MCP tools, you will not be charged for the tool invocation but will be charged for any tokens used.

For more information on using Tools, please visit [our guide on Tools](/developers/tools/overview).

## Documents Search Pricing

For users using our Collections API and Documents Search, the following pricing applies:

## Usage Guidelines Violation Fee

A rare occurrence for most users, when your request is deemed to be in violation of our usage guideline by our system, we will charge a $0.05 per request usage guidelines violation fee.

## Additional Information Regarding Models

* **No access to realtime events without search tools enabled**
  * Grok has no knowledge of current events or data beyond what was present in its training data.
  * To incorporate realtime data with your request, enable server-side search tools (Web Search / X Search). See [Web Search](/developers/tools/web-search) and [X Search](/developers/tools/x-search).
* **Chat models**
  * No role order limitation: You can mix `system`, `user`, or `assistant` roles in any sequence for your conversation context.
* **Image input models**
  * Maximum image size: `20MiB`
  * Maximum number of images: No limit
  * Supported image file types: `jpg/jpeg` or `png`.
  * Any image/text input order is accepted (e.g. text prompt can precede image prompt)

The knowledge cut-off date of Grok 3 and Grok 4 is November, 2024.

## Model Aliases

Some models have aliases to help users automatically migrate to the next version of the same model. In general:

* `<modelname>` is aliased to the latest stable version.
* `<modelname>-latest` is aliased to the latest version. This is suitable for users who want to access the latest features.
* `<modelname>-<date>` refers directly to a specific model release. This will not be updated and is for workflows that demand consistency.

For most users, the aliased `<modelname>` or `<modelname>-latest` are recommended, as you would receive the latest features automatically.

## Billing and Availability

Your model access might vary depending on various factors such as geographical location, account limitations, etc.

For how the **bills are charged**, visit [Manage Billing](/console/billing) for more information.

For the most up-to-date information on **your team's model availability**, visit [Models Page](https://console.x.ai/team/default/models) on xAI Console.

## Model Input and Output

Each model can have one or multiple input and output capabilities.
The input capabilities refer to which type(s) of prompt can the model accept in the request message body.
The output capabilities refer to which type(s) of completion will the model generate in the response message body.

This is a prompt example for models with `text` input capability:

```json
[
  {
    "role": "system",
    "content": "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."
  },
  {
    "role": "user",
    "content": "What is the meaning of life, the universe, and everything?"
  }
]
```

This is a prompt example for models with `text` and `image` input capabilities:

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
        "text": "Describe what's in this image."
      }
    ]
  }
]
```

This is a prompt example for models with `text` input and `image` output capabilities:

```json
// The entire request body
{
  "model": "grok-4",
  "prompt": "A cat in a tree",
  "n": 4
}
```

## Context Window

The context window determines the maximum amount of tokens accepted by the model in the prompt.

For more information on how token is counted, visit [Consumption and Rate Limits](/developers/rate-limits).

If you are sending the entire conversation history in the prompt for use cases like chat assistant, the sum of all the prompts in your conversation history must be no greater than the context window.

## Cached prompt tokens

Trying to run the same prompt multiple times? You can now use cached prompt tokens to incur less cost on repeated prompts. By reusing stored prompt data, you save on processing expenses for identical requests. Enable caching in your settings and start saving today!

The caching is automatically enabled for all requests without user input. You can view the cached prompt token consumption in [the `"usage"` object](/developers/rate-limits#checking-token-consumption).

For details on the pricing, please refer to the pricing table above, or on [xAI Console](https://console.x.ai).

===/developers/rate-limits===
#### Key Information

# Consumption and Rate Limits

The cost of using our API is based on token consumption. We charge different prices based on token category:

* **Prompt text, audio and image tokens** - Charged at prompt token price
* **Cached prompt tokens** - Charged at cached prompt token price
* **Completion tokens** - Charged at completion token price
* **Reasoning tokens** - Charged at completion token price

Visit [Models and Pricing](../models) for general pricing, or [xAI Console](https://console.x.ai) for pricing applicable to your team.

Each `grok` model has different rate limits. To check your team's rate limits, you can visit [xAI Console Models Page](https://console.x.ai/team/default/models).

## Basic unit to calculate consumption — Tokens

A token is the basic unit of prompt size for model inference and pricing purposes. It consists of one or more character(s)/symbol(s).

When a Grok model handles your request, an input prompt will be decomposed into a list of tokens through a tokenizer.
The model will then make inference based on the prompt tokens, and generate completion tokens.
After the inference is completed, the completion tokens will be aggregated into a completion response sent back to you.

Our system will add additional formatting tokens to the input/output token, and if you selected a reasoning model, additional reasoning tokens will be added into the total token consumption as well.
Your actual consumption will be reflected either in the `usage` object returned in the API response, or in Usage Explorer on the [xAI Console](https://console.x.ai).

You can use [Tokenizer](https://console.x.ai/team/default/tokenizer) on xAI Console to visualize tokens a given text prompt, or use [Tokenize text](/developers/api-reference#tokenize-text) endpoint on the API.

### Text tokens

Tokens can be either of a whole word, or smaller chunks of character combinations. The more common a word is, the more likely it would be a whole token.

For example, Flint is broken down into two tokens, while Michigan is a whole token.

In another example, most words are tokens by themselves, but "drafter" is broken down into "dra" and "fter", and "postmaster" is broken down into "post" and "master".

For a given text/image/etc. prompt or completion sequence, different tokenizers may break it down into different lengths of lists.

Different Grok models may also share or use different tokenizers. Therefore, **the same prompt/completion sequence may not have the same amount of tokens across different models.**

The token count in a prompt/completion sequence should be approximately linear to the sequence length.

### Image prompt tokens

Each image prompt will take between 256 to 1792 tokens, depending on the size of the image. The image + text token count must be less than the overall context window of the model.

### Estimating consumption with tokenizer on xAI Console or through API

The tokenizer page or API might display less token count than the actual token consumption. The
inference endpoints would automatically add pre-defined tokens to help our system process the
request.

On xAI Console, you can use the [tokenizer page](https://console.x.ai/team/default/tokenizer) to estimate how many tokens your text prompt will consume. For example, the following message would consume 5 tokens (the actual consumption may vary because of additional special tokens added by the system).

Message body:

```json
[
  {
    "role": "user",
    "content": "How is the weather today?"
  }
]
```

Tokenize result on Tokenizer page:

You can also utilize the [Tokenize Text](/developers/api-reference#tokenize-text) API endpoint to tokenize the text, and count the output token array length.

### Cached prompt tokens

When you send the same prompt multiple times, we may cache your prompt tokens. This would result in reduced cost for these tokens at the cached token rate, and a quicker response.

The prompt is cached using prefix matching, using cache for the exact prefix matches in the subsequent requests. However, the cache size might be limited and distributed across different clusters.

You can also specify `x-grok-conv-id: <A constant uuid4 ID>` in the HTTP request header, to increase the likelihood of cache hit in the subsequent requests using the same header.

### Reasoning tokens

The model may use reasoning to process your request. The reasoning content is returned in the response's `reasoning_content` field. The reasoning token consumption will be counted separately from `completion_tokens`, but will be counted in the `total_tokens`.

The reasoning tokens will be charged at the same price as `completion_tokens`.

`grok-4` does not return `reasoning_content`

## Hitting rate limits

To request a higher rate limit, please email support@x.ai with your anticipated volume.

For each tier, there is a maximum amount of requests per minute and tokens per minute. This is to ensure fair usage by all users of the system.

Once your request frequency has reached the rate limit, you will receive error code `429` in response.

You can either:

* Upgrade your team to higher tiers
* Change your consumption pattern to send fewer requests

## Checking token consumption

In each completion response, there is a `usage` object detailing your prompt and completion token count. You might find it helpful to keep track of it, in order to avoid hitting rate limits or having cost surprises. You can view more details of the object on our [API Reference](/developers/api-reference).

```json
"usage": {
    "prompt_tokens": 199,
    "completion_tokens": 1,
    "total_tokens": 200,
    "prompt_tokens_details": {
        "text_tokens": 199,
        "audio_tokens": 0,
        "image_tokens": 0,
        "cached_tokens": 163
    },
    "completion_tokens_details": {
        "reasoning_tokens": 0,
        "audio_tokens": 0,
        "accepted_prediction_tokens": 0,
        "rejected_prediction_tokens": 0
    },
    "num_sources_used": 0,
    "cost_in_usd_ticks": 158500
}
```

The `cost_in_usd_ticks` field expresses the total cost to perform the inference, in 1/10,000,000,000 US dollar.

**Note:** The `usage.prompt_tokens_details.text_tokens` is the total text input token, which includes `cached_tokens` and non-cached text tokens.

You can also check with the xAI or OpenAI SDKs (Anthropic SDK is deprecated).

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import system, user

client = Client(api_key=os.getenv("XAI_API_KEY"))

chat = client.chat.create(
model="grok-4-1-fast-reasoning",
messages=[system("You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy.")]
)
chat.append(user("What is the meaning of life, the universe, and everything?"))

response = chat.sample()
print(response.usage)
```

```pythonOpenAISDK
import os
from openai import OpenAI

XAI_API_KEY = os.getenv("XAI_API_KEY")
client = OpenAI(base_url="https://api.x.ai/v1", api_key=XAI_API_KEY)

completion = client.chat.completions.create(
model="grok-4-1-fast-reasoning",
messages=[
{
"role": "system",
"content": "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy.",
},
{
"role": "user",
"content": "What is the meaning of life, the universe, and everything?",
},
],
)

if completion.usage:
print(completion.usage.to_json())
```

```javascriptOpenAISDK
import OpenAI from "openai";
const openai = new OpenAI({
apiKey: "<api key>",
baseURL: "https://api.x.ai/v1",
});

const completion = await openai.chat.completions.create({
model: "grok-4-1-fast-reasoning",
messages: [
{
role: "system",
content:
"You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy.",
},
{
role: "user",
content:
"What is the meaning of life, the universe, and everything?",
},
],
});

console.log(completion.usage);
```

===/developers/regions===
#### Key Information

# Regional Endpoints

By default, you can access our API at `https://api.x.ai`. This is the most suitable endpoint for most customers,
as the request will be automatically routed by us to be processed in the region with lowest latency for your request.

For example, if you are based in US East Coast and send your request to `https://api.x.ai`, your request will be forwarded
to our `us-east-1` region and we will try to process it there first. If there is not enough computing resource in `us-east-1`,
we will send your request to other regions that are geographically closest to you and can handle the request.

## Using a regional endpoint

If you have specific data privacy requirements that would require the request to be processed within a specified region,
you can leverage our regional endpoint.

You can send your request to `https://<region-name>.api.x.ai`. For the same example, to send request from US East Coast to `us-east-1`,
you will now send the request to `https://us-east-1.api.x.ai`. If for some reason, we cannot handle your request in `us-east-1`, the request will fail.

## Example of using regional endpoints

If you want to use a regional endpoint, you need to specify the endpoint url when making request with SDK. In xAI SDK, this is specified through the `api_host` parameter.

For example, to send request to `us-east-1`:

```pythonWithoutSDK
import os

from xai_sdk import Client
from xai_sdk.chat import user

client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    api_host="us-east-1.api.x.ai" # Without the https://
)

chat = client.chat.create(model="grok-4-1-fast-reasoning")
chat.append(user("What is the meaning of life?"))

completion = chat.sample()
```

```pythonOpenAISDK
from openai import OpenAI

client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://us-east-1.api.x.ai/v1",
)

completion = client.chat.completions.create(
    model="grok-4-1-fast-reasoning",
    messages=[
        {"role": "user", "content": "What is the meaning of life?"}
    ]
)
```

```javascriptOpenAISDK
import OpenAI from "openai";

const client = new OpenAI({
    apiKey: XAI_API_KEY,
    baseURL: "https://us-east-1.api.x.ai/v1",
});

const completion = await client.chat.completions.create({
    model: "grok-4-1-fast-reasoning",
    messages: [
        { role: "user", content: "What is the meaning of life?" }
    ]
});
```

```bash
curl https://us-east-1.api.x.ai/v1/chat/completions \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer $XAI_API_KEY" \\
-d '{
    "messages": [
        {
            "role": "user",
            "content": "What is the meaning of life, the universe, and everything?"
        }
    ],
    "model": "grok-4-1-fast-reasoning",
    "stream": false
}'
```

## Model availability across regions

While we strive to make every model available across all regions, there could be occasions where some models are not
available in some regions.

By using the global `https://api.x.ai` endpoint, you would have access to all models available to your team, since we
route your request automatically. If you're using a regional endpoint, please refer to [xAI Console](https://console.x.ai)
for the available models to your team in each region, or [Models and Pricing](../models) for the publicly available models.

===/developers/release-notes===
#### Release Notes

# Release Notes

Stay up to date with the latest changes to the xAI API.

# November 2025

### Grok 4.1 Fast is available in Enterprise API

You can now use Grok 4.1 Fast in the [xAI Enterprise API](https://x.ai/api). For more details, check out [our blogpost](https://x.ai/news/grok-4-1-fast).

### Agent tools adapt to Grok 4.1 Fast models and tool prices dropped

* You can now use Grok 4.1 Fast models with the agent tools, check out the [documentation of agent tools](/developers/tools/overview) to get started.
* The price of agent tools drops by up to 50% to no more than $5 per 1000 successful calls, see the new prices at [the pricing page](/developers/models#tools-pricing).

### Files API is generally available

You can now upload files and use them in chat conversations with the Files API. For more details, check out [our guide on Files](/developers/files).

### New Tools Available

* **Collections Search Tool**: You can now search through uploaded knowledge bases (collections) in chat conversations via the API. For more details, check out the [docs](/developers/tools/collections-search).
* **Remote MCP Tools**: You can now use tools from remote MCP servers in chat conversations via the API. For more details, check out the [docs](/developers/tools/remote-mcp).
* **Mixing client-side and server-side tools**: You can now mix client-side and server-side tools in the same chat conversation. For more details, check out the [docs](/developers/tools/advanced-usage#mixing-server-side-and-client-side-tools).

# October 2025

### Tools are now generally available

New agentic server-side tools including `web_search`, `x_search` and `code_execution` are available. For more details, check out [our guide on using Tools](/developers/tools/overview).

# September 2025

### Responses API is generally available

You can now use our stateful Responses API to process requests.

# August 2025

### Grok Code Fast 1 is released

We have released our first Code Model to be used with code editors.

### Collections API is released

You can upload files, create embeddings, and use them for inference with our Collections API.

# July 2025

### Grok 4 is released

You can now use Grok 4 via our API or on https://grok.com.

# June 2025

### Management API is released

You can manage your API keys via Management API at
`https://management-api.x.ai`.

# May 2025

### Cached prompt is now available

You can now use cached prompt to save on repeated prompts. For
more info, see [models](/developers/models).

### Live Search is available on API

Live search is now available on API. Users can generate
completions with queries on supported data sources.

# April 2025

### Grok 3 models launch on API

Our latest flagship `Grok 3` models are now generally available via
the API. For more info, see [models](/developers/models).

# March 2025

### Image Generation Model available on API

The image generation model is available on API. Visit
[Image Generations](/developers/model-capabilities/images/generation) for more details on using the model.

# February 2025

### Audit Logs

Team admins can now view audit logs on [console.x.ai](https://console.x.ai).

# January 2025

### Docs Dark Mode Released dark mode support on docs.x.ai

### Status Page Check service statuses across all xAI products at

[status.x.ai](https://status.x.ai/).

# December 2024

### Replit & xAI

Replit Agents can now integrate with xAI! Start empowering your agents with Grok.
Check out the [announcement](https://x.com/Replit/status/1874211039258333643) for more information.

### Tokenizer Playground Understanding tokens can be hard. Check out

[console.x.ai](https://console.x.ai) to get a better understanding of what counts as a token.

### Structured Outputs We're excited to announce that Grok now supports structured outputs. Grok can

now format responses in a predefined, organized format rather than free-form text. 1. Specify the
desired schema

```
{
    "name": "movie_response",
    "schema": {
        "type": "object",
        "properties": {
            "title": { "type": "string" },
            "rating": { "type": "number" },
        },
        "required": [ "title", "rating" ],
        "additionalProperties": false
    },
    "strict": true
}
```

2. Get the desired data

```
{
  "title": "Star Wars",
  "rating": 8.6
}
```

Start building more reliable applications. Check out the [docs](/developers/model-capabilities/text/structured-outputs) for more information.

### Released the new grok-2-1212 and grok-2-vision-1212 models A month ago, we launched the public

beta of our enterprise API with grok-beta and grok-vision-beta. We’re adding [grok-2-1212 and
grok-2-vision-1212](/developers/models), offering better accuracy, instruction-following,
and multilingual capabilities.

# November 2024

### LangChain & xAI Our API is now available through LangChain! - Python Docs:

http://python.langchain.com/integrations/providers/xai/ - Javascript Docs:
http://js.langchain.com/integrations/chat/xai/

What are you going to build?

### API Public Beta Released We are happy to announce the immediate availability of our API, which

gives developers programmatic access to our Grok series of foundation models. To get started, head
to [console.x.ai](https://console.x.ai/) and sign up to create an account. We are excited to see
what developers build using Grok.

===/developers/tools/advanced-usage===
#### Tools

# Advanced Usage

In this section, we explore advanced usage patterns for agentic tool calling, including:

* **[Use Client-side Tools](#mixing-server-side-and-client-side-tools)** - Combine server-side agentic tools with your own client-side tools for specialized functionality that requires local execution.
* **[Multi-turn Conversations](#multi-turn-conversations-with-preservation-of-agentic-state)** - Maintain context across multiple turns in agentic tool-enabled conversations, allowing the model to build upon previous research and tool results for more complex, iterative problem-solving
* **[Requests with Multiple Active Tools](#tool-combinations)** - Send requests with multiple server-side tools active simultaneously, enabling comprehensive analysis with web search, X search, and code execution tools working together
* **[Image Integration](#using-images-in-the-context)** - Include images in your tool-enabled conversations for visual analysis and context-aware searches

&#x20;Advanced tool usage patterns are not yet supported in the Vercel AI SDK. Please use the xAI SDK or OpenAI SDK for this functionality.

## Mixing Server-Side and Client-Side Tools

You can combine server-side agentic tools (like web search and code execution) with custom client-side tools to create powerful hybrid workflows. This approach lets you leverage the model's reasoning capabilities with server-side tools while adding specialized functionality that runs locally in your application.

### How It Works

The key difference when mixing server-side and client-side tools is that **server-side tools are executed automatically by xAI**, while **client-side tools require developer intervention**:

1. Define your client-side tools using [standard function calling patterns](/developers/tools/function-calling)
2. Include both server-side and client-side tools in your request
3. **xAI automatically executes any server-side tools** the model decides to use (web search, code execution, etc.)
4. **When the model calls client-side tools, execution pauses** - xAI returns the tool calls to you instead of executing them
5. **Detect and execute client-side tool calls yourself**, then append the results back to continue the conversation
6. **Repeat this process** until the model generates a final response with no additional client-side tool calls

### Understanding `max_turns` with Client-Side Tools

When using [the `max_turns` parameter](/developers/tools/tool-usage-details#limiting-tool-call-turns) with mixed server-side and client-side tools, it's important to understand that **`max_turns` only limits the assistant/server-side tool call turns within a single request**.

When the model decides to invoke a client-side tool, the agent execution **pauses and yields control back to your application**. This means:

* The current request completes, and you receive the client-side tool call(s) to execute
* After you execute the client-side tool and append the result, you make a **new follow-up request**
* This follow-up request starts with a fresh `max_turns` count

In other words, client-side tool invocations act as "checkpoints" that reset the turn counter. If you set `max_turns=5` and the agent performs 3 server-side tool calls before requesting a client-side tool, the subsequent request (after you provide the client-side tool result) will again allow up to 5 server-side tool turns.

### Practical Example

Given a local client-side function `get_weather` to get the weather of a specified city, the model can use this client-side tool and the web-search tool to determine the weather in the base city of the 2025 NBA champion.

### Using the xAI SDK

You can determine whether a tool call is a client-side tool call by using `xai_sdk.tools.get_tool_call_type` against a tool call from the `response.tool_calls` list.
For more details, check [Identifying Tool Call Types](/developers/tools/tool-usage-details#identifying-tool-call-types).

1. Import the dependencies, and define the client-side tool.

   ```pythonXAI
   import os
   import json

   from xai_sdk import Client
   from xai_sdk.chat import user, tool, tool_result
   from xai_sdk.tools import web_search, get_tool_call_type

   client = Client(api_key=os.getenv("XAI_API_KEY"))

   # Define client-side tool
   def get_weather(city: str) -> str:
       """Get the weather for a given city."""
       # In a real app, this would query your database
       return f"The weather in {city} is sunny."

   # Tools array with both server-side and client-side tools
   tools = [
       web_search(),
       tool(
           name="get_weather",
           description="Get the weather for a given city.",
           parameters={
               "type": "object",
               "properties": {
                   "city": {
                       "type": "string",
                       "description": "The name of the city",
                   }
               },
               "required": ["city"]
           },
       ),
   ]

   model = "grok-4-1-fast-reasoning"
   ```

2. Perform the tool loop with conversation continuation:
   * You can either use `previous_response_id` to continue the conversation from the last response.

     ```pythonXAI
     # Create chat with both server-side and client-side tools
     chat = client.chat.create(
         model=model,
         tools=tools,
         store_messages=True,
     )
     chat.append(
         user(
             "What is the weather in the base city of the team that won the "
             "2025 NBA championship?"
         )
     )

     while True:
         client_side_tool_calls = []
         for response, chunk in chat.stream():
             for tool_call in chunk.tool_calls:
                 if get_tool_call_type(tool_call) == "client_side_tool":
                     client_side_tool_calls.append(tool_call)
                 else:
                     print(
                         f"Server-side tool call: {tool_call.function.name} "
                         f"with arguments: {tool_call.function.arguments}"
                     )

         if not client_side_tool_calls:
             break

         chat = client.chat.create(
             model=model,
             tools=tools,
             store_messages=True,
             previous_response_id=response.id,
         )

         for tool_call in client_side_tool_calls:
             print(
                 f"Client-side tool call: {tool_call.function.name} "
                 f"with arguments: {tool_call.function.arguments}"
             )
             args = json.loads(tool_call.function.arguments)
             result = get_weather(args["city"])
             chat.append(tool_result(result))

     print(f"Final response: {response.content}")
     ```

   * Alternatively, you can use the encrypted content to continue the conversation.

     ```pythonXAI
     # Create chat with both server-side and client-side tools
     chat = client.chat.create(
         model=model,
         tools=tools,
         use_encrypted_content=True,
     )
     chat.append(
         user(
             "What is the weather in the base city of the team that won the "
             "2025 NBA championship?"
         )
     )

     while True:
         client_side_tool_calls = []
         for response, chunk in chat.stream():
             for tool_call in chunk.tool_calls:
                 if get_tool_call_type(tool_call) == "client_side_tool":
                     client_side_tool_calls.append(tool_call)
                 else:
                     print(
                         f"Server-side tool call: {tool_call.function.name} "
                         f"with arguments: {tool_call.function.arguments}"
                     )

         chat.append(response)

         if not client_side_tool_calls:
             break

         for tool_call in client_side_tool_calls:
             print(
                 f"Client-side tool call: {tool_call.function.name} "
                 f"with arguments: {tool_call.function.arguments}"
             )
             args = json.loads(tool_call.function.arguments)
             result = get_weather(args["city"])
             chat.append(tool_result(result))

     print(f"Final response: {response.content}")
     ```

You will see an output similar to the following:

```
Server-side tool call: web_search with arguments: {"query":"Who won the 2025 NBA championship?","num_results":5}
Client-side tool call: get_weather with arguments: {"city":"Oklahoma City"}
Final response: The Oklahoma City Thunder won the 2025 NBA championship. The current weather in Oklahoma City is sunny.
```

### Using the OpenAI SDK

You can determine whether a tool call is a client-side tool call by checking the `type` field of an output entry from the `response.output` list.
For more details, see [Identifying Tool Call Types](/developers/tools/tool-usage-details#identifying-tool-call-types).

1. Import the dependencies, and define the client-side tool.

   ```pythonOpenAISDK
   import os
   import json

   from openai import OpenAI

   client = OpenAI(
       api_key=os.getenv("XAI_API_KEY"),
       base_url="https://api.x.ai/v1",
   )

   # Define client-side tool
   def get_weather(city: str) -> str:
       """Get the weather for a given city."""
       # In a real app, this would query your database
       return f"The weather in {city} is sunny."

   model = "grok-4-1-fast-reasoning"
   tools = [
       {
           "type": "function",
           "name": "get_weather",
           "description": "Get the weather for a given city.",
           "parameters": {
               "type": "object",
               "properties": {
                   "city": {
                       "type": "string",
                       "description": "The name of the city",
                   },
               },
               "required": ["city"],
           },
       },
       {
           "type": "web_search",
       },
   ]
   ```

2. Perform the tool loop:

   * You can either use `previous_response_id`.

     ```pythonOpenAISDK
     response = client.responses.create(
         model=model,
         input=(
             "What is the weather in the base city of the team that won the "
             "2025 NBA championship?"
         ),
         tools=tools,
     )

     while True:
         tool_outputs = []
         for item in response.output:
             if item.type == "function_call":
                 print(f"Client-side tool call: {item.name} with arguments: {item.arguments}")
                 args = json.loads(item.arguments)
                 weather = get_weather(args["city"])
                 tool_outputs.append(
                     {
                         "type": "function_call_output",
                         "call_id": item.call_id,
                         "output": weather,
                     }
                 )
             elif item.type in (
                 "web_search_call",
                 "x_search_call", 
                 "code_interpreter_call",
                 "file_search_call",
                 "mcp_call"
             ):
                 print(
                     f"Server-side tool call: {item.name} with arguments: {item.arguments}"
                 )

         if not tool_outputs:
             break

         response = client.responses.create(
             model=model,
             tools=tools,
             input=tool_outputs,
             previous_response_id=response.id,
         )

     print("Final response:", response.output[-1].content[0].text)
     ```

   * or using the encrypted content

     ```pythonOpenAISDK
     input_list = [
         {
             "role": "user",
             "content": (
                 "What is the weather in the base city of the team that won the "
                 "2025 NBA championship?"
             ),
         }
     ]

     response = client.responses.create(
         model=model,
         input=input_list,
         tools=tools,
         include=["reasoning.encrypted_content"],
     )

     while True:
         input_list.extend(response.output)
         tool_outputs = []
         for item in response.output:
             if item.type == "function_call":
                 print(f"Client-side tool call: {item.name} with arguments: {item.arguments}")
                 args = json.loads(item.arguments)
                 weather = get_weather(args["city"])
                 tool_outputs.append(
                     {
                         "type": "function_call_output",
                         "call_id": item.call_id,
                         "output": weather,
                     }
                 )
             elif item.type in (
                 "web_search_call",
                 "x_search_call", 
                 "code_interpreter_call",
                 "file_search_call",
                 "mcp_call"
             ):
                 print(
                     f"Server-side tool call: {item.name} with arguments: {item.arguments}"
                 )

         if not tool_outputs:
             break

         input_list.extend(tool_outputs)
         response = client.responses.create(
             model=model,
             input=input_list,
             tools=tools,
             include=["reasoning.encrypted_content"],
         )

     print("Final response:", response.output[-1].content[0].text)
     ```

## Multi-turn Conversations with Preservation of Agentic State

When using agentic tools, you may want to have multi-turn conversations where follow-up prompts maintain all agentic state, including the full history of reasoning, tool calls, and tool responses. This is possible using the stateful API, which provides seamless integration for preserving conversation context across multiple interactions. There are two options to achieve this outlined below.

### Store the Conversation History Remotely

You can choose to store the conversation history remotely on the xAI server, and every time you want to continue the conversation, you can pick up from the last response where you want to resume from.

There are only 2 extra steps:

1. Add the parameter `store_messages=True` when making the first agentic request. This tells the service to store the entire conversation history on xAI servers, including the model's reasoning, server-side tool calls, and corresponding responses.
2. Pass `previous_response_id=response.id` when creating the follow-up conversation, where `response` is the response returned by `chat.sample()` or `chat.stream()` from the conversation that you wish to continue.

Note that the follow-up conversation does not need to use the same tools, model parameters, or any other configuration as the initial conversation—it will still be fully hydrated with the complete agentic state from the previous interaction.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search
client = Client(api_key=os.getenv("XAI_API_KEY"))
# First turn.
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[web_search(), x_search()],
    store_messages=True,
)
chat.append(user("What is xAI?"))
print("\\n\\n##### First turn #####\\n")
for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True)
print("\\n\\nUsage for first turn:", response.server_side_tool_usage)

# Second turn.
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[web_search(), x_search()],
    # pass the response id of the first turn to continue the conversation
    previous_response_id=response.id,
)

chat.append(user("What is its latest mission?"))
print("\\n\\n##### Second turn #####\\n")
for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True)
print("\\n\\nUsage for second turn:", response.server_side_tool_usage)
```

### Append the Encrypted Agentic Tool Calling States

There is another option for the ZDR (Zero Data Retention) users, or the users who don't want to use the above option, that is to let the xAI server also return
the encrypted reasoning and the encrypted tool output besides the final content to the client side, and those encrypted contents can be included as a part of the context
in the next turn conversation.

Here are the extra steps you need to take for this option:

1. Add the parameter `use_encrypted_content=True` when making the first agentic request. This tells the service to return the entire conversation history to the client side, including the model's reasoning (encrypted), server-side tool calls, and corresponding responses (encrypted).
2. Append the response to the conversation you wish to continue before making the call to `chat.sample()` or `chat.stream()`.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search
client = Client(api_key=os.getenv("XAI_API_KEY"))
# First turn.
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[web_search(), x_search()],
    use_encrypted_content=True,
)
chat.append(user("What is xAI?"))
print("\\n\\n##### First turn #####\\n")
for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True)
print("\\n\\nUsage for first turn:", response.server_side_tool_usage)

chat.append(response)

print("\\n\\n##### Second turn #####\\n")
chat.append(user("What is its latest mission?"))
# Second turn.
for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True)
print("\\n\\nUsage for second turn:", response.server_side_tool_usage)
```

For more details about stateful responses, please check out [this guide](/developers/model-capabilities/text/generate-text).

## Tool Combinations

Equipping your requests with multiple tools is straightforward—simply include the tools you want to activate in the `tools` array of your request. The model will intelligently orchestrate between them based on the task at hand.

### Suggested Tool Combinations

Here are some common patterns for combining tools, depending on your use case:

| If you're trying to... | Consider activating... | Because... |
|------------------------|----------------------|------------|
| **Research & analyze data** | Web Search + Code Execution | Web search gathers information, code execution analyzes and visualizes it |
| **Aggregate news & social media** | Web Search + X Search | Get comprehensive coverage from both traditional web and social platforms |
| **Extract insights from multiple sources** | Web Search + X Search + Code Execution | Collect data from various sources then compute correlations and trends |
| **Monitor real-time discussions** | X Search + Web Search | Track social sentiment alongside authoritative information |

```pythonXAI
from xai_sdk.tools import web_search, x_search, code_execution

# Example tool combinations for different scenarios
research_setup = [web_search(), code_execution()]
news_setup = [web_search(), x_search()]
comprehensive_setup = [web_search(), x_search(), code_execution()]
```

```pythonWithoutSDK
research_setup = {
  "tools": [
    {"type": "web_search"},
    {"type": "code_interpreter"}
  ]
}

news_setup = {
  "tools": [
    {"type": "web_search"},
    {"type": "x_search"}
  ]
}

comprehensive_setup = {
  "tools": [
    {"type": "web_search"},
    {"type": "x_search"},
    {"type": "code_interpreter"}
  ]
}
```

### Using Tool Combinations in Different Scenarios

1. When you want to search for news on the Internet, you can activate all search tools:
   * Web search tool
   * X search tool

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[
        web_search(),
        x_search(),
    ],
    include=["verbose_streaming"],
)

chat.append(user("what is the latest update from xAI?"))

is_thinking = True
for response, chunk in chat.stream():
    # View the server-side tool calls as they are being made in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
print("\\n\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)
print("\\n\\nServer Side Tool Calls:")
print(response.tool_calls)
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "what is the latest update from xAI?",
        },
    ],
    tools=[
        {
            "type": "web_search",
        },
        {
            "type": "x_search",
        },
    ],
)

print(response)
```

```pythonRequests
import os
import requests

url = "https://api.x.ai/v1/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}
payload = {
    "model": "grok-4-1-fast-reasoning",
    "input": [
        {
            "role": "user",
            "content": "what is the latest update from xAI?"
        }
    ],
    "tools": [
        {
            "type": "web_search",
        },
        {
            "type": "x_search",
        }
    ]
}
response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "What is the latest update from xAI?"
    }
  ],
  "tools": [
    {
      "type": "web_search"
    },
    {
      "type": "x_search"
    }
  ]
}'
```

2. When you want to collect up-to-date data from the Internet and perform calculations based on the Internet data, you can choose to activate:
   * Web search tool
   * Code execution tool

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    # research_tools
    tools=[
        web_search(),
        code_execution(),
    ],
    include=["verbose_streaming"],
)

chat.append(user("What is the average market cap of the companies with the top 5 market cap in the US stock market today?"))

# sample or stream the response...
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "What is the average market cap of the companies with the top 5 market cap in the US stock market today?",
        },
    ],
    # research_tools
    tools=[
        {
            "type": "web_search",
        },
        {
            "type": "code_interpreter",
        },
    ],
)

print(response)
```

```pythonRequests
import os
import requests

url = "https://api.x.ai/v1/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}
payload = {
    "model": "grok-4-1-fast-reasoning",
    "input": [
        {
            "role": "user",
            "content": "What is the average market cap of the companies with the top 5 market cap in the US stock market today?"
        }
    ],
    # research_tools
    "tools": [
        {
            "type": "web_search",
        },
        {
            "type": "code_interpreter",
        },
    ]
}
response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "What is the average market cap of the companies with the top 5 market cap in the US stock market today?"
    }
  ],
  "tools": [
    {
      "type": "web_search"
    },
    {
      "type": "code_interpreter"
    }
  ]
}'
```

## Using Images in the Context

You can bootstrap your requests with an initial conversation context that includes images.

In the code sample below, we pass an image into the context of the conversation before initiating an agentic request.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import image, user
from xai_sdk.tools import web_search, x_search

# Create the client and define the server-side tools to use
client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[web_search(), x_search()],
    include=["verbose_streaming"],
)

# Add an image to the conversation
chat.append(
    user(
        "Search the internet and tell me what kind of dog is in the image below.",
        "And what is the typical lifespan of this dog breed?",
        image(
            "https://pbs.twimg.com/media/G3B7SweXsAAgv5N?format=jpg&name=900x900"
        ),
    )
)

is_thinking = True
for response, chunk in chat.stream():
    # View the server-side tool calls as they are being made in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
print("\\n\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)
print("\\n\\nServer Side Tool Calls:")
print(response.tool_calls)
```

===/developers/tools/citations===
#### Tools

# Citations

The agent tools API provides two types of citation information: **All Citations** (a complete list of all sources encountered) and **Inline Citations** (markdown-style links embedded directly in the response text).

## All Citations

The `citations` attribute on the `response` object provides a comprehensive list of URLs for all sources the agent encountered during its search process. This list is **always returned by default** — no additional configuration is required.

Citations are automatically collected from successful tool executions and provide full traceability of the agent's information sources. They are returned when the agentic request completes.

Note that not every URL in this list will necessarily be directly referenced in the final answer. The agent may examine a source during its research process and determine it is not sufficiently relevant to the user's query, but the URL will still appear in this list for transparency.

```pythonWithoutSDK
response.citations
```

```output
[
'https://x.com/i/user/1912644073896206336',
'https://x.com/i/status/1975607901571199086',
'https://x.ai/news',
'https://docs.x.ai/developers/release-notes',
...
]
```

## Inline Citations

Inline citations are **markdown-style links** (e.g., `[[1]](https://x.ai/news)`) inserted directly into the response text at the points where the model references sources. In addition to these visible links, **structured metadata** is available on the response object with precise positional information.

**Important**: Enabling inline citations does not guarantee that the model will cite sources on every answer. The model decides when and where to include citations based on the context and nature of the query.

### Enabling Inline Citations

Inline citations are returned by default with the Responses API. For the xAI SDK, you can explicitly request them with `include=["inline_citations"]`:

### Markdown Citation Format

When inline citations are enabled, the model will insert markdown-style citation links directly into the response text:

```output
The latest announcements from xAI, primarily from their official X account (@xai) and website (x.ai/news), date back to November 19, 2025.[[1]](https://x.ai/news/)[[2]](https://x.ai/)[[3]](https://x.com/i/status/1991284813727474073)
```

When rendered as markdown, this displays as clickable links:

> The latest announcements from xAI, primarily from their official X account (@xai) and website (x.ai/news), date back to November 19, 2025.[\[1\]](https://x.ai/news/)[\[2\]](https://x.ai/)[\[3\]](https://x.com/i/status/1991284813727474073)

The format is `[[N]](url)` where:

* `N` is the sequential display number for the citation **starting from 1**
* `url` is the source URL

**Citation numbering**: Citation numbers always start from 1 and increment sequentially. If the same source is cited again later in the response, the original citation number will be reused.

## Accessing Structured Inline Citation Data

Structured inline citation data provides precise positional information about each citation in the response text.

### Response Format

Each citation annotation contains:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"url_citation"` |
| `url` | string | The source URL |
| `start_index` | int | Character position where the citation starts in the response text |
| `end_index` | int | Character position where the citation ends (exclusive) |
| `title` | string | The citation number (e.g., "1", "2") |

```output
Citation [1]:
  Position: 37 to 76
  Web URL: https://x.ai/news/grok-4-fast
Citation [2]:
  Position: 124 to 171
  X URL: https://x.com/xai/status/1234567890
```

### Using Position Indices

The `start_index` and `end_index` values follow Python slice convention:

* **`start_index`**: Character position of the first `[` of the citation
* **`end_index`**: Character position immediately *after* the closing `)` (exclusive)

Extract the exact citation markdown from the response text using a simple slice:

```python customLanguage="pythonXAI"
content = response.content

for citation in response.inline_citations:
    # Extract the markdown link from the response text
    citation_text = content[citation.start_index:citation.end_index]
    print(f"Citation text: {citation_text}")
```

## Streaming Inline Citations

During streaming, inline citations are accumulated and available on the final response. The markdown links appear in real-time in the `chunk.content` as the model generates text:

```python customLanguage="pythonXAI"
for response, chunk in chat.stream():
    # Markdown links appear in chunk.content in real-time
    if chunk.content:
        print(chunk.content, end="", flush=True)
    
    # Inline citations can also be accessed per-chunk during streaming
    for citation in chunk.inline_citations:
        print(f"\nNew citation: [{citation.id}]")

# After streaming, access all accumulated inline citations
print("\n\nAll inline citations:")
for citation in response.inline_citations:
    url = ""
    if citation.HasField("web_citation"):
        url = citation.web_citation.url
    elif citation.HasField("x_citation"):
        url = citation.x_citation.url
    print(f"  [{citation.id}] {url}")
```

===/developers/tools/code-execution===
#### Tools

# Code Execution Tool

The code execution tool enables Grok to write and execute Python code in real-time, dramatically expanding its capabilities beyond text generation. This powerful feature allows Grok to perform precise calculations, complex data analysis, statistical computations, and solve mathematical problems that would be impossible through text alone.

## Key Capabilities

* **Mathematical Computations**: Solve complex equations, perform statistical analysis, and handle numerical calculations with precision
* **Data Analysis**: Process datasets, and extract insights from the prompt
* **Financial Modeling**: Build financial models, calculate risk metrics, and perform quantitative analysis
* **Scientific Computing**: Handle scientific calculations, simulations, and data transformations
* **Code Generation & Testing**: Write, test, and debug Python code snippets in real-time

## When to Use Code Execution

The code execution tool is particularly valuable for:

* **Numerical Problems**: When you need exact calculations rather than approximations
* **Data Processing**: Analyzing complex data from the prompt
* **Complex Logic**: Multi-step calculations that require intermediate results
* **Verification**: Double-checking mathematical results or validating assumptions

## SDK Support

The code execution tool is available across multiple SDKs and APIs with different naming conventions:

| SDK/API | Tool Name | Description |
|---------|-----------|-------------|
| xAI SDK | `code_execution` | Native xAI SDK implementation |
| OpenAI Responses API | `code_interpreter` | Compatible with OpenAI's API format |
| Vercel AI SDK | `xai.tools.codeExecution()` | Vercel AI SDK integration |

This tool is also supported in all Responses API compatible SDKs.

## Implementation Example

Below are comprehensive examples showing how to integrate the code execution tool across different platforms and use cases.

### Basic Calculations

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[code_execution()],
    include=["verbose_streaming"],
)

# Ask for a mathematical calculation
chat.append(user("Calculate the compound interest for $10,000 at 5% annually for 10 years"))

is_thinking = True
for response, chunk in chat.stream():
    # View the server-side tool calls as they are being made in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
print("\\n\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)
print("\\n\\nServer Side Tool Calls:")
print(response.tool_calls)
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "Calculate the compound interest for $10,000 at 5% annually for 10 years",
        },
    ],
    tools=[
        {
            "type": "code_interpreter",
        },
    ],
)

print(response)
```

```pythonRequests
import os
import requests

url = "https://api.x.ai/v1/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}
payload = {
    "model": "grok-4-1-fast-reasoning",
    "input": [
        {
            "role": "user",
            "content": "Calculate the compound interest for $10,000 at 5% annually for 10 years"
        }
    ],
    "tools": [
        {
            "type": "code_interpreter",
        }
    ]
}
response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "Calculate the compound interest for $10,000 at 5% annually for 10 years"
    }
  ],
  "tools": [
    {
      "type": "code_interpreter"
    }
  ]
}'
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'Calculate the compound interest for $10,000 at 5% annually for 10 years',
  tools: {
    code_execution: xai.tools.codeExecution(),
  },
});

console.log(text);
```

### Data Analysis

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Multi-turn conversation with data analysis
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[code_execution()],
    include=["verbose_streaming"],
)

# Step 1: Load and analyze data
chat.append(user("""
I have sales data for Q1-Q4: [120000, 135000, 98000, 156000].
Please analyze this data and create a visualization showing:
1. Quarterly trends
2. Growth rates
3. Statistical summary
"""))

print("##### Step 1: Data Analysis #####\\n")

is_thinking = True
for response, chunk in chat.stream():
    # View the server-side tool calls as they are being made in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nAnalysis Results:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
print("\\n\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)

chat.append(response)

# Step 2: Follow-up analysis
chat.append(user("Now predict Q1 next year using linear regression"))

print("\\n\\n##### Step 2: Prediction Analysis #####\\n")

is_thinking = True
for response, chunk in chat.stream():
    # View the server-side tool calls as they are being made in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nPrediction Results:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
print("\\n\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)
print("\\n\\nServer Side Tool Calls:")
print(response.tool_calls)
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

// Step 1: Load and analyze data
const step1 = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: \`I have sales data for Q1-Q4: [120000, 135000, 98000, 156000].
Please analyze this data and create a visualization showing:
1. Quarterly trends
2. Growth rates
3. Statistical summary\`,
  tools: {
    code_execution: xai.tools.codeExecution(),
  },
});

console.log('##### Step 1: Data Analysis #####');
console.log(step1.text);

// Step 2: Follow-up analysis using previousResponseId
const step2 = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'Now predict Q1 next year using linear regression',
  tools: {
    code_execution: xai.tools.codeExecution(),
  },
  providerOptions: {
    xai: {
      previousResponseId: step1.response.id,
    },
  },
});

console.log('##### Step 2: Prediction Analysis #####');
console.log(step2.text);
```

## Best Practices

### 1. **Be Specific in Requests**

Provide clear, detailed instructions about what you want the code to accomplish:

```pythonWithoutSDK
# Good: Specific and clear
"Calculate the correlation matrix for these variables and highlight correlations above 0.7"

# Avoid: Vague requests  
"Analyze this data"
```

### 2. **Provide Context and Data Format**

Always specify the data format and any constraints on the data, and provide as much context as possible:

```pythonWithoutSDK
# Good: Includes data format and requirements
"""
Here's my CSV data with columns: date, revenue, costs
Please calculate monthly profit margins and identify the best-performing month.
Data: [['2024-01', 50000, 35000], ['2024-02', 55000, 38000], ...]
"""
```

### 3. **Use Appropriate Model Settings**

* **Temperature**: Use lower values (0.0-0.3) for mathematical calculations
* **Model**: Use reasoning models like `grok-4-1-fast-reasoning` for better code generation

## Common Use Cases

### Financial Analysis

```pythonWithoutSDK
# Portfolio optimization, risk calculations, option pricing
"Calculate the Sharpe ratio for a portfolio with returns [0.12, 0.08, -0.03, 0.15] and risk-free rate 0.02"
```

### Statistical Analysis

```pythonWithoutSDK
# Hypothesis testing, regression analysis, probability distributions
"Perform a t-test to compare these two groups and interpret the p-value: Group A: [23, 25, 28, 30], Group B: [20, 22, 24, 26]"
```

### Scientific Computing

```pythonWithoutSDK
# Simulations, numerical methods, equation solving
"Solve this differential equation using numerical methods: dy/dx = x^2 + y, with initial condition y(0) = 1"
```

## Limitations and Considerations

* **Execution Environment**: Code runs in a sandboxed Python environment with common libraries pre-installed
* **Time Limits**: Complex computations may have execution time constraints
* **Memory Usage**: Large datasets might hit memory limitations
* **Package Availability**: Most popular Python packages (NumPy, Pandas, Matplotlib, SciPy) are available
* **File I/O**: Limited file system access for security reasons

## Security Notes

* Code execution happens in a secure, isolated environment
* No access to external networks or file systems
* Temporary execution context that doesn't persist between requests
* All computations are stateless and secure

===/developers/tools/collections-search===
#### Tools

# Collections Search Tool

The collections search tool enables Grok to search through your uploaded knowledge bases (collections), allowing it to retrieve relevant information from your documents to provide more accurate and contextually relevant responses. This tool is particularly powerful for analyzing complex documents like financial reports, legal contracts, or technical documentation, where Grok can autonomously search through multiple documents and synthesize information to answer sophisticated analytical questions.

For an introduction to Collections, please check out the [Collections documentation](/developers/files/collections).

## Key Capabilities

* **Document Retrieval**: Search across uploaded files and collections to find relevant information
* **Semantic Search**: Find documents based on meaning and context, not just keywords
* **Knowledge Base Integration**: Seamlessly integrate your proprietary data with Grok's reasoning
* **RAG Applications**: Power retrieval-augmented generation workflows
* **Multi-format Support**: Search across PDFs, text files, CSVs, and other supported formats

## When to Use Collections Search

The collections search tool is particularly valuable for:

* **Enterprise Knowledge Bases**: When you need Grok to reference internal documents and policies
* **Financial Analysis**: Analyzing SEC filings, earnings reports, and financial statements across multiple documents
* **Customer Support**: Building chatbots that can answer questions based on your product documentation
* **Research & Due Diligence**: Synthesizing information from academic papers, technical reports, or industry analyses
* **Compliance & Legal**: Ensuring responses are grounded in your official guidelines and regulations
* **Personal Knowledge Management**: Organizing and querying your personal document collections

## SDK Support

The collections search tool is available across multiple SDKs and APIs with different naming conventions:

| SDK/API | Tool Name | Description |
|---------|-----------|-------------|
| xAI SDK | `collections_search` | Native xAI SDK implementation |
| OpenAI Responses API | `file_search` | Compatible with OpenAI's API format |

This tool is also supported in all Responses API compatible SDKs.

## Implementation Example

### End-to-End Financial Analysis Example

This comprehensive example demonstrates analyzing Tesla's SEC filings using the collections search tool. It covers:

1. Creating a collection for document storage
2. Uploading multiple financial documents concurrently (10-Q and 10-K filings)
3. Using Grok with collections search to analyze and synthesize information across documents in an agentic manner
4. Enabling code execution to allow the model to perform calculations and mathematical analysis effectively should it be needed.
5. Receiving cited responses and tool usage information

This pattern is applicable to any document analysis workflow where you need to search through and reason over multiple documents.

```pythonXAI
import asyncio
import os

import httpx

from xai_sdk import AsyncClient
from xai_sdk.chat import user
from xai_sdk.proto import collections_pb2
from xai_sdk.tools import code_execution, collections_search

TESLA_10_Q_PDF_URL = "https://ir.tesla.com/_flysystem/s3/sec/000162828025045968/tsla-20250930-gen.pdf"
TESLA_10_K_PDF_URL = "https://ir.tesla.com/_flysystem/s3/sec/000162828025003063/tsla-20241231-gen.pdf"


async def main():
    client = AsyncClient(api_key=os.getenv("XAI_API_KEY"))

    # Step 1: Create a collection for Tesla SEC filings
    response = await client.collections.create("tesla-sec-filings")
    print(f"Created collection: {response.collection_id}")

    # Step 2: Upload documents to the collection concurrently
    async def upload_document(
        url: str, name: str, collection_id: str, http_client: httpx.AsyncClient
    ) -> None:
        pdf_response = await http_client.get(url, timeout=30.0)
        pdf_content = pdf_response.content

        print(f"Uploading {name} document to collection")
        response = await client.collections.upload_document(
            collection_id=collection_id,
            name=name,
            data=pdf_content,
            content_type="application/pdf",
        )

        # Poll until document is processed and ready for search
        response = await client.collections.get_document(response.file_metadata.file_id, collection_id)
        print(f"Waiting for document {name} to be processed")
        while response.status != collections_pb2.DOCUMENT_STATUS_PROCESSED:
            await asyncio.sleep(3)
            response = await client.collections.get_document(response.file_metadata.file_id, collection_id)

        print(f"Document {name} processed")

    # Upload both documents concurrently
    async with httpx.AsyncClient() as http_client:
        await asyncio.gather(
            upload_document(TESLA_10_Q_PDF_URL, "tesla-10-Q-2024.pdf", response.collection_id, http_client),
            upload_document(TESLA_10_K_PDF_URL, "tesla-10-K-2024.pdf", response.collection_id, http_client),
        )

    # Step 3: Create a chat with collections search enabled
    chat = client.chat.create(
        model="grok-4-1-fast-reasoning",  # Use a reasoning model for better analysis
        tools=[
            collections_search(
                collection_ids=[response.collection_id],
            ),
            code_execution(),
        ],
        include=["verbose_streaming"],
    )

    # Step 4: Ask a complex analytical question that requires searching multiple documents
    chat.append(
        user(
            "How many consumer vehicles did Tesla produce in total in 2024 and 2025? "
            "Show your working and cite your sources."
        )
    )

    # Step 5: Stream the response and display reasoning progress
    is_thinking = True
    async for response, chunk in chat.stream():
        # View server-side tool calls as they happen
        for tool_call in chunk.tool_calls:
            print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
        if response.usage.reasoning_tokens and is_thinking:
            print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
        if chunk.content and is_thinking:
            print("\\n\\nFinal Response:")
            is_thinking = False
        if chunk.content and not is_thinking:
            print(chunk.content, end="", flush=True)
        latest_response = response

    # Step 6: Review citations and tool usage
    print("\\n\\nCitations:")
    print(latest_response.citations)
    print("\\n\\nUsage:")
    print(latest_response.usage)
    print(latest_response.server_side_tool_usage)
    print("\\n\\nTool Calls:")
    print(latest_response.tool_calls)


if __name__ == "__main__":
    asyncio.run(main())
```

```pythonOpenAISDK
import os
from openai import OpenAI

# Using OpenAI SDK with xAI API (requires pre-created collection)
api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

# Note: You must create the collection and upload documents first using either the xAI console (console.x.ai) or the xAI SDK
# The collection_id below should be replaced with your actual collection ID
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "How many consumer vehicles did Tesla produce in total in 2024 and 2025? Show your working and cite your sources.",
        },
    ],
    tools=[
        {
            "type": "file_search",
            "vector_store_ids": ["your_collection_id_here"],  # Replace with actual collection ID
            "max_num_results": 10
        },
        {"type": "code_interpreter"},  # Enable code execution for calculations
    ],
)

print(response)
```

```javascriptAISDK
import { createOpenAI } from '@ai-sdk/openai';
import { streamText } from 'ai';

const openai = createOpenAI({
  baseURL: 'https://api.x.ai/v1',
  apiKey: process.env.XAI_API_KEY,
});

const result = streamText({
  model: openai('grok-4-1-fast-reasoning'),
  prompt: 'What documents do you have access to?',
  tools: {
    file_search: openai.tools.fileSearch({
      vectorStoreIds: ['your-vector-store-id'],
      maxNumResults: 5,
    }),
  },
});
```

```pythonRequests
import os
import requests

# Using raw requests (requires pre-created collection)
url = "https://api.x.ai/v1/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}
payload = {
    "model": "grok-4-1-fast-reasoning",
    "input": [
        {
            "role": "user",
            "content": "How many consumer vehicles did Tesla produce in total in 2024 and 2025? Show your working and cite your sources."
        }
    ],
    "tools": [
        {
            "type": "file_search",
            "vector_store_ids": ["your_collection_id_here"],  # Replace with actual collection ID
            "max_num_results": 10,
        },
        {"type": "code_interpreter"}  # Enable code execution for calculations
    ]
}
response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

```bash
# Using curl (requires pre-created collection)
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "How many consumer vehicles did Tesla produce in total in 2024 and 2025? Show your working and cite your sources."
    }
  ],
  "tools": [
    {
      "type": "file_search",
      "vector_store_ids": ["your_collection_id_here"],
      "max_num_results": 10
    },
    {
      "type": "code_interpreter"
    }
  ]
}'
```

## Example Output

When you run the Python xAI SDK example above, you'll see output like this showing the complete workflow from collection creation to the final analyzed response:

```output
Created collection: collection_3be0eec8-ee8e-4a18-a9d4-fb70a3150d64
Uploading tesla-10-K-2024.pdf document to collection
Uploading tesla-10-Q-2024.pdf document to collection
Waiting for document tesla-10-K-2024.pdf to be processed
Waiting for document tesla-10-Q-2024.pdf to be processed
Document tesla-10-Q-2024.pdf processed
Document tesla-10-K-2024.pdf processed

Thinking... (199 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla total vehicle production 2024","limit":10}
Thinking... (370 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla total vehicles produced 2024","limit":5}
Thinking... (370 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla vehicles produced 2025 Q1 Q2 Q3","limit":5}
Thinking... (477 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla production and deliveries 2024 all quarters","limit":10}
Thinking... (477 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla production and deliveries 2025 Q1 Q2 Q3","limit":10}
Thinking... (569 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla total production 2024 full year consumer vehicles","limit":5}
Thinking... (776 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla annual vehicle production 2024 total","limit":5}
Thinking... (1148 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla Q4 2024 production and deliveries","limit":5}
Thinking... (1240 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla Q1 2024 vehicle production","limit":3}
Thinking... (1240 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla Q2 2024 vehicle production","limit":3}
Thinking... (1240 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla Q3 2024 vehicle production","limit":3}
Thinking... (1240 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla Q4 2024 vehicle production","limit":3}
Thinking... (2804 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla vehicle production nine months 2024","limit":5}
Thinking... (3352 tokens)

Final Response:
### Working

To answer this question, I used the collections_search tool to query Tesla's official 
financial filings (10-K and 10-Q reports) for production numbers. Tesla reports vehicle 
production and deliveries quarterly, and consumer vehicles refer to passenger vehicles 
like Model 3, Model Y, Model S, Model X, and Cybertruck (excluding Tesla Semi or other 
non-consumer products).

#### Step 1: 2024 Production
Based on Tesla's official quarterly production and delivery reports (aggregated from SEC 
filings and press releases referenced in the collections), Tesla produced **1,773,443 
consumer vehicles in 2024**.
  - Q1 2024: 433,371 produced
  - Q2 2024: 410,831 produced
  - Q3 2024: 469,796 produced
  - Q4 2024: 459,445 produced

#### Step 2: 2025 Production
The Q3 2025 10-Q filing explicitly states: "In 2025, we produced approximately 1,220,000 
consumer vehicles [...] through the third quarter."
  - This is the sum of Q1, Q2, and Q3 2025 production
  - Q4 2025 data is not available as of November 13, 2025

#### Step 3: Total for 2024 and 2025
- 2024 full year: 1,773,443
- 2025 (through Q3): 1,220,000
- **Total: 2,993,443 consumer vehicles**

Citations:
['collections://collection_3be0eec8-ee8e-4a18-a9d4-fb70a3150d64/files/file_d4d1a968-9037-4caa-8eca-47a1563f28ab', 
 'collections://collection_3be0eec8-ee8e-4a18-a9d4-fb70a3150d64/files/file_ff41a42e-6cdc-4ca1-918a-160644d52704']

Usage:
completion_tokens: 1306
prompt_tokens: 383265
total_tokens: 387923
prompt_text_tokens: 383265
reasoning_tokens: 3352
cached_prompt_text_tokens: 177518

{'SERVER_SIDE_TOOL_COLLECTIONS_SEARCH': 13}


Tool Calls:
... (omitted for brevity)
```

### Understanding Collections Citations

When using the collections search tool, citations follow a special URI format that uniquely identifies the source documents:

```
collections://collection_id/files/file_id
```

For example:

```
collections://collection_3be0eec8-ee8e-4a18-a9d4-fb70a3150d64/files/file_d4d1a968-9037-4caa-8eca-47a1563f28ab
```

**Format Breakdown:**

* **`collections://`**: Protocol identifier indicating this is a collection-based citation
* **`collection_id`**: The unique identifier of the collection that was searched (e.g., `collection_3be0eec8-ee8e-4a18-a9d4-fb70a3150d64`)
* **`files/`**: Path segment indicating file-level reference
* **`file_id`**: The unique identifier of the specific document file that was referenced (e.g., `file_d4d1a968-9037-4caa-8eca-47a1563f28ab`)

These citations represent all the documents from your collections that Grok referenced during its search and analysis. Each citation points to a specific file within a collection, allowing you to trace back exactly which uploaded documents contributed to the final response.

### Key Observations

1. **Autonomous Search Strategy**: Grok autonomously performs 13 different searches across the documents, progressively refining queries to find specific quarterly and annual production data.

2. **Reasoning Process**: The output shows reasoning tokens accumulating (199 → 3,352 tokens), demonstrating how the model thinks through the problem before generating the final response.

3. **Cited Sources**: All information is grounded in the uploaded documents with specific file citations, ensuring transparency and verifiability.

4. **Structured Analysis**: The final response breaks down the methodology, shows calculations, and clearly states assumptions and limitations (e.g., Q4 2025 data not yet available).

5. **Token Efficiency**: Notice the high number of cached prompt tokens (177,518) - this demonstrates how the collections search tool efficiently reuses context across multiple queries.

## Combining Collections Search with Web Search/X-Search

One of the most powerful patterns is combining the collections search tool with web search/x-search to answer questions that require both your internal knowledge base and real-time external information. This enables sophisticated analysis that grounds responses in your proprietary data while incorporating current market intelligence, news, and public sentiment.

### Example: Internal Data + Market Intelligence

Building on the Tesla example above, let's analyze how market analysts view Tesla's performance based on the production numbers from our internal documents:

```pythonXAI
import asyncio

import httpx

from xai_sdk import AsyncClient
from xai_sdk.chat import user
from xai_sdk.proto import collections_pb2
from xai_sdk.tools import code_execution, collections_search, web_search, x_search

# ... (collection creation and document upload same as before)

async def hybrid_analysis(client: AsyncClient, collection_id: str, model: str) -> None:
    # Enable collections search, web search, and code execution
    chat = client.chat.create(
        model=model,
        tools=[
            collections_search(
                collection_ids=[collection_id],
            ),
            web_search(),  # Enable web search for external data
            x_search(),  # Enable x-search for external data
            code_execution(),  # Enable code execution for calculations
        ],
        include=["verbose_streaming"],
    )

    # Ask a question that requires both internal and external information
    chat.append(
        user(
            "Based on Tesla's actual production figures in my documents (collection), what is the "
            "current market and analyst sentiment on their 2024-2025 vehicle production performance?"
        )
    )

    is_thinking = True
    async for response, chunk in chat.stream():
        for tool_call in chunk.tool_calls:
            print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
        if response.usage.reasoning_tokens and is_thinking:
            print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
        if chunk.content and is_thinking:
            print("\\n\\nFinal Response:")
            is_thinking = False
        if chunk.content and not is_thinking:
            print(chunk.content, end="", flush=True)
        latest_response = response

    print("\\n\\nCitations:")
    print(latest_response.citations)
    print("\\n\\nTool Usage:")
    print(latest_response.server_side_tool_usage)
```

### How It Works

When you provide both `collections_search()` and `web_search()`/`x_search()` tools, Grok autonomously determines the optimal search strategy:

1. **Internal Analysis First**: Searches your uploaded Tesla SEC filings to extract actual production numbers
2. **External Context Gathering**: Performs web/x-search searches to find analyst reports, market sentiment, and production expectations
3. **Synthesis**: Combines both data sources to provide a comprehensive analysis comparing actual performance against market expectations
4. **Cited Sources**: Returns citations from both your internal documents (using `collections://` URIs) and external web sources (using `https://` URLs)

### Example Output Pattern

```output
Thinking... (201 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla vehicle production figures 2024 2025","limit":20}
Thinking... (498 tokens)
Calling tool: collections_search with arguments: {"query":"Tesla quarterly vehicle production and deliveries 2024 2025","limit":20}
Thinking... (738 tokens)
Calling tool: web_search with arguments: {"query":"Tesla quarterly vehicle production and deliveries 2024 2025","num_results":10}
Thinking... (738 tokens)
Calling tool: web_search with arguments: {"query":"market and analyst sentiment Tesla vehicle production performance 2024 2025","num_results":10}
Thinking... (1280 tokens)

Final Response 
... (omitted for brevity)
```

### Use Cases for Hybrid Search

This pattern is valuable for:

* **Market Analysis**: Compare internal financial data with external market sentiment and competitor performance
* **Competitive Intelligence**: Analyze your product performance against industry reports and competitor announcements
* **Compliance Verification**: Cross-reference internal policies with current regulatory requirements and industry standards
* **Strategic Planning**: Ground business decisions in both proprietary data and real-time market conditions
* **Customer Research**: Combine internal customer data with external reviews, social sentiment, and market trends

===/developers/tools/overview===
#### Tools

# Overview

The xAI API supports **tool calling**, enabling Grok to perform actions beyond generating text—like searching the web, executing code, querying your data, or calling your own custom functions. Tools extend what's possible with the API and let you build powerful, interactive applications.

## Types of Tools

The xAI API offers two categories of tools:

| Type | Description | Examples |
|------|-------------|----------|
| **Built-in Tools** | Server-side tools managed by xAI that execute automatically | Web Search, X Search, Code Interpreter, Collections Search |
| **Function Calling** | Custom functions you define that the model can invoke | Database queries, API calls, custom business logic |

Built-in tools run on xAI's servers—you provide the tool configuration, and the API handles execution and returns results. Function calling lets you define your own tools that the model can request, giving you full control over what happens when they're invoked.

## Pricing

Tool requests are priced based on two components: **token usage** and **tool invocations**. Since the model may call multiple tools to answer a query, costs scale with complexity.

For more details on Tools pricing, please check out [the pricing page](/developers/models#tools-pricing).

## How It Works

When you provide tools to a request, the xAI API can use them to gather information or perform actions:

1. **Analyzes the query** and determines what information or actions are needed
2. **Decides what to do next**: Make a tool call, or provide a final answer
3. **Executes the tool** (for built-in tools) or returns a tool call request (for function calling)
4. **Processes results** and continues until sufficient information is gathered
5. **Returns the final response** with citations where applicable

## Quick Start

## Citations

The API automatically returns source URLs for information gathered via tools. See [Citations](/developers/tools/citations) for details on accessing and using citation data.

## Next Steps

* **[Function Calling](/developers/tools/function-calling)** - Define custom tools the model can call
* **[Web Search](/developers/tools/web-search)** - Search the web and browse pages
* **[X Search](/developers/tools/x-search)** - Search X posts, users, and threads
* **[Code Execution](/developers/tools/code-execution)** - Execute Python code in a sandbox
* **[Collections Search](/developers/tools/collections-search)** - Query your uploaded documents
* **[Citations](/developers/tools/citations)** - Access source URLs and inline citations

===/developers/tools/remote-mcp===
#### Tools

# Remote MCP Tools

Remote MCP Tools allow Grok to connect to external MCP (Model Context Protocol) servers, extending its capabilities with custom tools from third parties or your own implementations. Simply specify a server URL and optional configuration - xAI manages the MCP server connection and interaction on your behalf.

## SDK Support

Remote MCP tools are supported in the xAI native SDK and the OpenAI compatible Responses API.

The `require_approval` and `connector_id` parameters in the OpenAI Responses API are not currently supported.

## Configuration

To use remote MCP tools, you need to configure the connection to your MCP server in the tools array of your request.

| Parameter | Required | Description |
|-----------|-------------------|-------------|
| `server_url` | Yes | The URL of the MCP server to connect to. Only Streaming HTTP and SSE transports are supported. |
| `server_label` | No | A label to identify the server (used for tool call prefixing) |
| `server_description` | No | A description of what the server provides |
| `allowed_tool_names` | No | List of specific tool names to allow (empty allows all) |
| `authorization` | No | A token that will be set in the Authorization header on requests to the MCP server |
| `extra_headers` | No | Additional headers to include in requests |

### Basic MCP Tool Usage

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import mcp

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        mcp(server_url="https://mcp.deepwiki.com/mcp"),
    ],
    include=["verbose_streaming"],
)

chat.append(user("What can you do with https://github.com/xai-org/xai-sdk-python?"))

is_thinking = True
for response, chunk in chat.stream():
    # View the server-side tool calls as they are being made in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)
print("\\n\\nServer Side Tool Calls:")
print(response.tool_calls)
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "What can you do with https://github.com/xai-org/xai-sdk-python?",
        },
    ],
    tools=[
        {
            "type": "mcp",
            "server_url": "https://mcp.deepwiki.com/mcp",
            "server_label": "deepwiki",
        }
    ],
)

print(response)
```

```pythonRequests
import os
import requests

url = "https://api.x.ai/v1/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}
payload = {
    "model": "grok-4-1-fast-reasoning",
    "input": [
        {
            "role": "user",
            "content": "What can you do with https://github.com/xai-org/xai-sdk-python?"
        }
    ],
    "tools": [
        {
            "type": "mcp",
            "server_url": "https://mcp.deepwiki.com/mcp",
            "server_label": "deepwiki",
        }
    ]
}
response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "What can you do with https://github.com/xai-org/xai-sdk-python?"
    }
  ],
  "tools": [
    {
        "type": "mcp",
        "server_url": "https://mcp.deepwiki.com/mcp",
        "server_label": "deepwiki"
    }
  ]
}'
```

## Tool Enablement and Access Control

When you configure a Remote MCP Tool without specifying `allowed_tool_names`, all tool definitions exposed by the MCP server are automatically injected into the model's context. This means the model gains access to every tool that the MCP server provides, allowing it to use any of them during the conversation.

For example, if an MCP server exposes 10 different tools and you don't specify `allowed_tool_names`, all 10 tool definitions will be available to the model. The model can then choose to call any of these tools based on the user's request and the tool descriptions.

Use the `allowed_tool_names` parameter to selectively enable only specific tools from an MCP server. This can give you several key benefits:

* **Better Performance**: Reduce context overhead by limiting tool definitions the model needs to consider
* **Reduced Risk**: For example, restrict access to tools that only perform read-only operations to prevent the model from modifying data

```pythonXAI
# Enable only specific tools from a server with many available tools
mcp(
    server_url="https://comprehensive-tools.example.com/mcp",
    allowed_tool_names=["search_database", "format_data"]
)
```

Instead of giving the model access to every tool the server offers, this approach keeps Grok focused and efficient while ensuring it has exactly the capabilities it needs.

## Multi-Server Support

Enable multiple MCP servers simultaneously to create a rich ecosystem of specialized tools:

```pythonXAI
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        mcp(server_url="https://mcp.deepwiki.com/mcp", server_label="deepwiki"),
        mcp(server_url="https://your-custom-tools.com/mcp", server_label="custom"),
        mcp(server_url="https://api.example.com/tools", server_label="api-tools"),
    ],
)
```

Each server can provide different capabilities - documentation tools, API integrations, custom business logic, or specialized data processing - all accessible within a single conversation.

## Best Practices

* **Provide clear server metadata**: Use descriptive `server_label` and `server_description` when configuring multiple MCP servers to help the model understand each server's purpose and select the right tools
* **Filter tools appropriately**: Use `allowed_tool_names` to restrict access to only necessary tools, especially when servers have many tools since the model must keep all available tool definitions in context
* **Use secure connections**: Always use HTTPS URLs and implement proper authentication mechanisms on your MCP server
* **Provide Examples**: While the model can generally figure out what tools to use based on the tool descriptions and the user request it may help to provide examples in the prompt

===/developers/tools/streaming-and-sync===
#### Tools

# Streaming & Synchronous Requests

Agentic requests can be executed in either streaming or synchronous mode. This page covers both approaches and how to use them effectively.

## Streaming Mode (Recommended)

We strongly recommend using streaming mode when using agentic tool calling. It provides:

* **Real-time observability** of tool calls as they happen
* **Immediate feedback** during potentially long-running requests
* **Reasoning token counts** as the model thinks

### Streaming Example

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import code_execution, web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        web_search(),
        x_search(),
        code_execution(),
    ],
    include=["verbose_streaming"],
)

chat.append(user("What are the latest updates from xAI?"))

is_thinking = True
for response, chunk in chat.stream():
    # View server-side tool calls in real-time
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\nCitations:", response.citations)
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { streamText } from 'ai';

const { fullStream } = streamText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What are the latest updates from xAI?',
  tools: {
    web_search: xai.tools.webSearch(),
    x_search: xai.tools.xSearch(),
    code_execution: xai.tools.codeExecution(),
  },
});

for await (const part of fullStream) {
  if (part.type === 'tool-call') {
    console.log(\`Calling tool: \${part.toolName}\`);
  } else if (part.type === 'text-delta') {
    process.stdout.write(part.text);
  } else if (part.type === 'source' && part.sourceType === 'url') {
    console.log(\`Citation: \${part.url}\`);
  }
}
```

## Synchronous Mode

For simpler use cases or when you want to wait for the complete agentic workflow to finish before processing the response, you can use synchronous requests:

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import code_execution, web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        web_search(),
        x_search(),
        code_execution(),
    ],
)

chat.append(user("What is the latest update from xAI?"))

# Get the final response in one go once it's ready
response = chat.sample()

print("Final Response:")
print(response.content)

print("\\nCitations:")
print(response.citations)

print("\\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

// Synchronous request - waits for complete response
const { text, sources } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What is the latest update from xAI?',
  tools: {
    web_search: xai.tools.webSearch(),
    x_search: xai.tools.xSearch(),
    code_execution: xai.tools.codeExecution(),
  },
});

console.log('Final Response:');
console.log(text);

console.log('\\nCitations:');
console.log(sources);
```

Synchronous requests will wait for the entire agentic process to complete before returning. This is simpler for basic use cases but provides less visibility into intermediate steps.

## Using Tools with Responses API

We also support using the Responses API in both streaming and non-streaming modes:

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    store_messages=True,  # Enable Responses API
    tools=[
        web_search(),
        x_search(),
    ],
)

chat.append(user("What is the latest update from xAI?"))
response = chat.sample()

print(response.content)
print(response.citations)

# The response id can be used to continue the conversation
print(response.id)
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "what is the latest update from xAI?",
        },
    ],
    tools=[
        {
            "type": "web_search",
        },
        {
            "type": "x_search",
        },
    ],
)

print(response)
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "what is the latest update from xAI?"
    }
  ],
  "tools": [
    {
      "type": "web_search"
    },
    {
      "type": "x_search"
    }
  ]
}'
```

## Accessing Tool Outputs

By default, server-side tool call outputs are not returned since they can be large. However, you can opt-in to receive them:

### xAI SDK

| Tool | Value for `include` field |
|------|---------------------------|
| `"web_search"` | `"web_search_call_output"` |
| `"x_search"` | `"x_search_call_output"` |
| `"code_execution"` | `"code_execution_call_output"` |
| `"collections_search"` | `"collections_search_call_output"` |
| `"attachment_search"` | `"attachment_search_call_output"` |
| `"mcp"` | `"mcp_call_output"` |

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        code_execution(),
    ],
    include=["code_execution_call_output"],
)
chat.append(user("What is the 100th Fibonacci number?"))

# stream or sample the response...
```

### Responses API

| Tool | Responses API tool name | Value for `include` field |
|------|-------------------------|---------------------------|
| `"web_search"` | `"web_search"` | `"web_search_call.action.sources"` |
| `"code_execution"` | `"code_interpreter"` | `"code_interpreter_call.outputs"` |
| `"collections_search"` | `"file_search"` | `"file_search_call.results"` |
| `"mcp"` | `"mcp"` | Always returned in Responses API |

===/developers/tools/tool-usage-details===
#### Tools

# Tool Usage Details

This page covers the technical details of how tool calls are tracked, billed, and how to understand token usage in agentic requests.

## Real-time Server-side Tool Calls

When streaming agentic requests, you can observe **every tool call decision** the model makes in real-time via the `tool_calls` attribute on the `chunk` object:

```pythonWithoutSDK
for tool_call in chunk.tool_calls:
    print(f"\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
```

**Note**: Only the tool call invocations are shown — **server-side tool call outputs are not returned** in the API response. The agent uses these outputs internally to formulate its final response.

## Server-side Tool Calls vs Tool Usage

The API provides two related but distinct metrics for server-side tool executions:

### `tool_calls` - All Attempted Calls

```pythonWithoutSDK
response.tool_calls
```

Returns a list of all **attempted** tool calls made during the agentic process. Each entry contains:

* `id`: Unique identifier for the tool call
* `function.name`: The name of the specific server-side tool called
* `function.arguments`: The parameters passed to the server-side tool

This includes **every tool call attempt**, even if some fail.

### `server_side_tool_usage` - Successful Calls (Billable)

```pythonWithoutSDK
response.server_side_tool_usage
```

Returns a map of successfully executed tools and their invocation counts. This represents only the tool calls that returned meaningful responses and **determines your billing**.

```output
{'SERVER_SIDE_TOOL_X_SEARCH': 3, 'SERVER_SIDE_TOOL_WEB_SEARCH': 2}
```

## Tool Call Function Names vs Usage Categories

The function names in `tool_calls` represent the precise name of the tool invoked, while the entries in `server_side_tool_usage` provide a high-level categorization that aligns with the original tool passed in the `tools` array.

| Usage Category | Function Name(s) |
|----------------|------------------|
| `SERVER_SIDE_TOOL_WEB_SEARCH` | `web_search`, `web_search_with_snippets`, `browse_page` |
| `SERVER_SIDE_TOOL_X_SEARCH` | `x_user_search`, `x_keyword_search`, `x_semantic_search`, `x_thread_fetch` |
| `SERVER_SIDE_TOOL_CODE_EXECUTION` | `code_execution` |
| `SERVER_SIDE_TOOL_VIEW_X_VIDEO` | `view_x_video` |
| `SERVER_SIDE_TOOL_VIEW_IMAGE` | `view_image` |
| `SERVER_SIDE_TOOL_COLLECTIONS_SEARCH` | `collections_search` |
| `SERVER_SIDE_TOOL_MCP` | `{server_label}.{tool_name}` if `server_label` provided, otherwise `{tool_name}` |

## When Tool Calls and Usage Differ

In most cases, `tool_calls` and `server_side_tool_usage` will show the same tools. However, they can differ when:

* **Failed tool executions**: The model attempts to browse a non-existent webpage, fetch a deleted X post, or encounters other execution errors
* **Invalid parameters**: Tool calls with malformed arguments that can't be processed
* **Network or service issues**: Temporary failures in the tool execution pipeline

The agentic system handles these failures gracefully, updating its trajectory and continuing with alternative approaches when needed.

**Billing Note**: Only successful tool executions (`server_side_tool_usage`) are billed. Failed attempts are not charged.

## Understanding Token Usage

Agentic requests have unique token usage patterns compared to standard chat completions:

### `completion_tokens`

Represents **only the final text output** of the model. This is typically much smaller than you might expect, as the agent performs all its intermediate reasoning and tool orchestration internally.

### `prompt_tokens`

Represents the **cumulative input tokens** across all inference requests made during the agentic process. Each request includes the full conversation history up to that point, which grows as the agent progresses.

While this can result in higher `prompt_tokens` counts, agentic requests benefit significantly from **prompt caching**. The majority of the prompt remains unchanged between steps, allowing for efficient caching.

### `reasoning_tokens`

Represents the tokens used for the model's internal reasoning process. This includes planning tool calls, analyzing results, and formulating responses, but excludes the final output tokens.

### `cached_prompt_text_tokens`

Indicates how many prompt tokens were served from cache rather than recomputed. Higher values indicate better cache utilization and lower costs.

### `prompt_image_tokens`

Represents tokens from visual content that the agent processes. These are counted separately from text tokens. If no images or videos are processed, this value will be zero.

## Limiting Tool Call Turns

The `max_turns` parameter allows you to control the maximum number of assistant/tool-call turns the agent can perform during a single request.

### Understanding Turns vs Tool Calls

**Important**: `max_turns` does **not** directly limit the number of individual tool calls. Instead, it limits the number of assistant turns in the agentic loop. During a single turn, the model may invoke multiple tools in parallel.

A "turn" represents one iteration of the agentic reasoning loop:

1. The model analyzes the current context
2. The model decides to call one or more tools (potentially in parallel)
3. Tools execute and return results
4. The model processes the results

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        web_search(),
        x_search(),
    ],
    max_turns=3,  # Limit to 3 assistant/tool-call turns
)

chat.append(user("What is the latest news from xAI?"))
response = chat.sample()
print(response.content)
```

### When to Use `max_turns`

| Use Case | Recommended `max_turns` | Tradeoff |
|----------|------------------------|----------|
| **Quick lookups** | 1-2 | Fastest response, may miss deeper insights |
| **Balanced research** | 3-5 | Good balance of speed and thoroughness |
| **Deep research** | 10+ or unset | Most comprehensive, longer latency and higher cost |

### Default Behavior

If `max_turns` is not specified, the server applies a global default cap. When the agent reaches the limit, it will stop making additional tool calls and generate a final response based on information gathered so far.

## Identifying Tool Call Types

To determine whether a returned tool call is a client-side tool that needs local execution:

### Using xAI SDK

Use the `get_tool_call_type` function:

```pythonXAI
from xai_sdk.tools import get_tool_call_type

for tool_call in response.tool_calls:
    print(get_tool_call_type(tool_call))
```

| Tool call types | Description |
|---------------|-------------|
| `"client_side_tool"` | Client-side tool call - requires local execution |
| `"web_search_tool"` | Web-search tool - handled by xAI server |
| `"x_search_tool"` | X-search tool - handled by xAI server |
| `"code_execution_tool"` | Code-execution tool - handled by xAI server |
| `"collections_search_tool"` | Collections-search tool - handled by xAI server |
| `"mcp_tool"` | MCP tool - handled by xAI server |

### Using Responses API

Check the `type` field of output entries (`response.output[].type`):

| Types | Description |
|-------|-------------|
| `"function_call"` | Client-side tool - requires local execution |
| `"web_search_call"` | Web-search tool - handled by xAI server |
| `"x_search_call"` | X-search tool - handled by xAI server |
| `"code_interpreter_call"` | Code-execution tool - handled by xAI server |
| `"file_search_call"` | Collections-search tool - handled by xAI server |
| `"mcp_call"` | MCP tool - handled by xAI server |

===/developers/tools/web-search===
#### Tools

# Web Search

The Web Search tool enables Grok to search the web in real-time and browse web pages to find information. This powerful tool allows the model to search the internet, access web pages, and extract relevant information to answer queries with up-to-date content.

## SDK Support

| SDK/API | Tool Name |
|---------|-----------|
| xAI SDK | `web_search` |
| OpenAI Responses API | `web_search` |
| Vercel AI SDK | `xai.tools.webSearch()` |

This tool is also supported in all Responses API compatible SDKs.

## Basic Usage

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[web_search()],
    include=["verbose_streaming"],
)

chat.append(user("What is xAI?"))

is_thinking = True
for response, chunk in chat.stream():
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "What is xAI?",
        },
    ],
    tools=[
        {
            "type": "web_search",
        },
    ],
)

print(response)
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const { text, sources } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What is xAI?',
  tools: {
    web_search: xai.tools.webSearch(),
  },
});

console.log(text);
console.log('Citations:', sources);
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "What is xAI?"
    }
  ],
  "tools": [
    {
      "type": "web_search"
    }
  ]
}'
```

## Web Search Parameters

| Parameter | Description |
|-----------|-------------|
| `allowed_domains` | Only search within specific domains (max 5) |
| `excluded_domains` | Exclude specific domains from search (max 5) |
| `enable_image_understanding` | Enable analysis of images found during browsing |

### Only Search in Specific Domains

Use `allowed_domains` to make the web search **only** perform the search and web browsing on web pages that fall within the specified domains.

`allowed_domains` cannot be set together with `excluded_domains` in the same request.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        web_search(allowed_domains=["wikipedia.org"]),
    ],
)

chat.append(user("What is xAI?"))
# stream or sample the response...
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "What is xAI?"}],
    tools=[
        {
            "type": "web_search",
            "filters": {"allowed_domains": ["wikipedia.org"]},
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What is xAI?',
  tools: {
    web_search: xai.tools.webSearch({
      allowedDomains: ['wikipedia.org'],
    }),
  },
});
```

### Exclude Specific Domains

Use `excluded_domains` to prevent the model from including the specified domains in any web search tool invocations.

```pythonXAI
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        web_search(excluded_domains=["wikipedia.org"]),
    ],
)
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "What is xAI?"}],
    tools=[
        {
            "type": "web_search",
            "filters": {"excluded_domains": ["wikipedia.org"]},
        },
    ],
)
```

### Enable Image Understanding

Setting `enable_image_understanding` to true equips the agent with access to the `view_image` tool, allowing it to analyze images encountered during the search process.

When enabled, you will see `SERVER_SIDE_TOOL_VIEW_IMAGE` in `response.server_side_tool_usage` along with the number of times it was called.

Enabling this parameter for Web Search will also enable the image understanding for X Search tool if it's also included in the request.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        web_search(enable_image_understanding=True),
    ],
)

chat.append(user("What is included in the image in xAI's official website?"))
# stream or sample the response...
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "What is included in the image in xAI's official website?",
        },
    ],
    tools=[
        {
            "type": "web_search",
            "enable_image_understanding": True,
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: "What is included in the image in xAI's official website?",
  tools: {
    web_search: xai.tools.webSearch({
      enableImageUnderstanding: true,
    }),
  },
});
```

## Citations

For details on how to retrieve and use citations from search results, see the [Citations](/developers/tools/citations) page.

===/developers/tools/x-search===
#### Tools

# X Search

The X Search tool enables Grok to perform keyword search, semantic search, user search, and thread fetch on X (formerly Twitter). This powerful tool allows the model to access real-time social media content, analyze posts, and gather insights from X's vast data.

## SDK Support

| SDK/API | Tool Name |
|---------|-----------|
| xAI SDK | `x_search` |
| OpenAI Responses API | `x_search` |
| Vercel AI SDK | `xai.tools.xSearch()` |

This tool is also supported in all Responses API compatible SDKs.

## Basic Usage

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",  # reasoning model
    tools=[x_search()],
    include=["verbose_streaming"],
)

chat.append(user("What are people saying about xAI on X?"))

is_thinking = True
for response, chunk in chat.stream():
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[
        {
            "role": "user",
            "content": "What are people saying about xAI on X?",
        },
    ],
    tools=[
        {
            "type": "x_search",
        },
    ],
)

print(response)
```

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const { text, sources } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What are people saying about xAI on X?',
  tools: {
    x_search: xai.tools.xSearch(),
  },
});

console.log(text);
console.log('Citations:', sources);
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4-1-fast-reasoning",
  "input": [
    {
      "role": "user",
      "content": "What are people saying about xAI on X?"
    }
  ],
  "tools": [
    {
      "type": "x_search"
    }
  ]
}'
```

## X Search Parameters

| Parameter | Description |
|-----------|-------------|
| `allowed_x_handles` | Only consider posts from specific X handles (max 10) |
| `excluded_x_handles` | Exclude posts from specific X handles (max 10) |
| `from_date` | Start date for search range (ISO8601 format) |
| `to_date` | End date for search range (ISO8601 format) |
| `enable_image_understanding` | Enable analysis of images in posts |
| `enable_video_understanding` | Enable analysis of videos in posts |

### Only Consider Posts from Specific Handles

Use `allowed_x_handles` to consider X posts only from a given list of X handles. The maximum number of handles you can include is 10.

`allowed_x_handles` cannot be set together with `excluded_x_handles` in the same request.

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        x_search(allowed_x_handles=["elonmusk"]),
    ],
)

chat.append(user("What is the current status of xAI?"))
# stream or sample the response...
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "What is the current status of xAI?"}],
    tools=[
        {
            "type": "x_search",
            "allowed_x_handles": ["elonmusk"],
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What is the current status of xAI?',
  tools: {
    x_search: xai.tools.xSearch({
      allowedXHandles: ['elonmusk'],
    }),
  },
});
```

### Exclude Posts from Specific Handles

Use `excluded_x_handles` to prevent the model from including X posts from the specified handles in any X search tool invocations. The maximum number of handles you can exclude is 10.

```pythonXAI
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        x_search(excluded_x_handles=["elonmusk"]),
    ],
)
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "What is the current status of xAI?"}],
    tools=[
        {
            "type": "x_search",
            "excluded_x_handles": ["elonmusk"],
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What is the current status of xAI?',
  tools: {
    x_search: xai.tools.xSearch({
      excludedXHandles: ['elonmusk'],
    }),
  },
});
```

### Date Range

You can restrict the date range of search data used by specifying `from_date` and `to_date`. This limits the data to the period from `from_date` to `to_date`, including both dates.

Both fields need to be in ISO8601 format, e.g., "YYYY-MM-DD". If you're using the xAI Python SDK, the `from_date` and `to_date` fields can be passed as `datetime.datetime` objects.

```pythonXAI
import os
from datetime import datetime

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        x_search(
            from_date=datetime(2025, 10, 1),
            to_date=datetime(2025, 10, 10),
        ),
    ],
)

chat.append(user("What is the current status of xAI?"))
# stream or sample the response...
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "What is the current status of xAI?"}],
    tools=[
        {
            "type": "x_search",
            "from_date": "2025-10-01",
            "to_date": "2025-10-10",
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'What is the current status of xAI?',
  tools: {
    x_search: xai.tools.xSearch({
      fromDate: '2025-10-01',
      toDate: '2025-10-10',
    }),
  },
});
```

### Enable Image Understanding

Setting `enable_image_understanding` to true allows the agent to analyze images in X posts encountered during the search process.

```pythonXAI
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        x_search(enable_image_understanding=True),
    ],
)
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "Find X posts with images about AI"}],
    tools=[
        {
            "type": "x_search",
            "enable_image_understanding": True,
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'Find X posts with images about AI',
  tools: {
    x_search: xai.tools.xSearch({
      enableImageUnderstanding: true,
    }),
  },
});
```

### Enable Video Understanding

Setting `enable_video_understanding` to true allows the agent to analyze videos in X posts. This is only available for X Search (not Web Search).

```pythonXAI
chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    tools=[
        x_search(enable_video_understanding=True),
    ],
)
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "Find X posts with videos about AI"}],
    tools=[
        {
            "type": "x_search",
            "enable_video_understanding": True,
        },
    ],
)
```

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4-1-fast-reasoning'),
  prompt: 'Find X posts with videos about AI',
  tools: {
    x_search: xai.tools.xSearch({
      enableVideoUnderstanding: true,
    }),
  },
});
```

## Citations

For details on how to retrieve and use citations from search results, see the [Citations](/developers/tools/citations) page.


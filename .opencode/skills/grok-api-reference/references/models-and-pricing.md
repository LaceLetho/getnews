# Grok API - Models

**Sections:** 2

---

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


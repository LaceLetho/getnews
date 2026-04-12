# LLM Provider Reference

This document catalogs all supported LLM providers, their available models, and configurable options. Use this reference when configuring `llm_config` in `config.json`.

## Supported Providers

| Provider | Environment Variable | Base URL |
|----------|---------------------|----------|
| Kimi | `KIMI_API_KEY` | `https://api.kimi.com/coding/v1` |
| Grok | `GROK_API_KEY` | `https://api.x.ai/v1` |
| OpenCode Go | `OPENCODE_API_KEY` | `https://opencode.ai/zen/go/v1` |

**Important:** Set the appropriate API key in your `.env` file before using a provider. The system validates these credentials at startup.

## Model Matrix

### Kimi Models

| Model | Web Search | X/Twitter Search | Thinking Level | Responses API |
|-------|-----------|------------------|----------------|---------------|
| `kimi-k2.5` | Yes | No | Yes | No |
| `kimi-k2-turbo-preview` | Yes | No | No | No |
| `kimi-k2-thinking-turbo` | Yes | No | No | No |

### Grok Models

| Model | Web Search | X/Twitter Search | Thinking Level | Responses API |
|-------|-----------|------------------|----------------|---------------|
| `grok-4-1-fast-reasoning` | Yes | Yes | No | Yes |
| `grok-4-1-fast-non-reasoning` | Yes | Yes | No | Yes |
| `grok-4.20-reasoning` | Yes | Yes | No | Yes |
| `grok-4.20-non-reasoning` | Yes | Yes | No | Yes |

### OpenCode Go Models

| Model | Web Search | X/Twitter Search | Thinking Level | Responses API |
|-------|-----------|------------------|----------------|---------------|
| `glm-5.1` | No | No | No | No |
| `kimi-k2.5` | No | No | No | No |
| `mimo-v2-pro` | No | No | No | No |

**Note:** OpenCode Go models are NOT supported for `market_model` in phase 1. Use Kimi or Grok for market snapshots.

**Phase-1 scope lock:** only the OpenAI-compatible snapshot is supported here: `glm-5.1`, `kimi-k2.5`, and `mimo-v2-pro`. Models such as `glm-5`, `mimo-v2-omni`, `minimax-m2.5`, and `minimax-m2.7` are intentionally unsupported in this project.

## Model Capabilities Explained

### Web Search

Enables the model to search the general web for current information beyond its training data. Kimi and Grok models support this feature; OpenCode Go models do not.

### X/Twitter Search

Allows the model to query X (formerly Twitter) for social media content. Only Grok models support this feature.

### Thinking Level

Controls the depth of reasoning for supported models. Only `kimi-k2.5` supports request-level thinking configuration.

**Available values:**
- `disabled` - Minimal reasoning, fastest response
- `low` - Light reasoning
- `medium` - Balanced reasoning (default if not specified)
- `high` - Deep reasoning
- `xhigh` - Maximum reasoning depth, slowest but most thorough

**Configuration example:**
```json
{
  "model": {
    "provider": "kimi",
    "name": "kimi-k2.5",
    "options": {"thinking_level": "medium"}
  }
}
```

**Note:** The `kimi-k2-thinking-turbo` model has thinking always enabled at the model level. Setting `thinking_level` for this model will fail validation. Use this model when you want guaranteed reasoning without per-request configuration.

### Responses API

Indicates support for the provider's streaming/conversational response format. Grok models support this; Kimi models use standard completion APIs.

## Unsupported Providers

The following consumer subscription services are **not valid API providers** for this system:

- **ChatGPT Plus** - This is a consumer subscription, not an API service
- **ChatGPT Go** - Mobile app subscription with no API access

To use OpenAI models, you need an OpenAI API key with pay-as-you-go billing enabled, not a ChatGPT Plus subscription.

## Configuration Examples

### Using Kimi as Primary with Grok Fallback

```json
{
  "llm_config": {
    "model": {
      "provider": "kimi",
      "name": "kimi-k2.5",
      "options": {"thinking_level": "medium"}
    },
    "fallback_models": [
      {
        "provider": "grok",
        "name": "grok-4-1-fast-reasoning",
        "options": {}
      }
    ],
    "market_model": {
      "provider": "grok",
      "name": "grok-4-1-fast-reasoning",
      "options": {}
    }
  }
}
```

### Using Grok for Everything

```json
{
  "llm_config": {
    "model": {
      "provider": "grok",
      "name": "grok-4.20-reasoning",
      "options": {}
    },
    "fallback_models": [
      {
        "provider": "grok",
        "name": "grok-4-1-fast-non-reasoning",
        "options": {}
      }
    ],
    "market_model": {
      "provider": "grok",
      "name": "grok-4.20-reasoning",
      "options": {}
    }
  }
}
```

### Using Kimi Thinking-Turbo (Always-On Reasoning)

```json
{
  "llm_config": {
    "model": {
      "provider": "kimi",
      "name": "kimi-k2-thinking-turbo",
      "options": {}
    },
    "fallback_models": [
      {
        "provider": "kimi",
        "name": "kimi-k2.5",
        "options": {"thinking_level": "high"}
      }
    ],
  }
}
```

### Using OpenCode Go as Primary Model

```json
{
  "llm_config": {
    "model": {
      "provider": "opencode-go",
      "name": "kimi-k2.5",
      "options": {}
    },
    "fallback_models": [
      {
        "provider": "opencode-go",
        "name": "glm-5.1",
        "options": {}
      }
    ],
  }
}
```

**Note:** OpenCode Go models do not support advanced capabilities (web search, x_search, thinking level, responses API, tooling, etc.). For `market_model`, you must use Kimi or Grok.

## Legacy Model Migrations

The following models have been removed and require migration:

- `kimi-for-coding` - Replace with `kimi-k2.5`, `kimi-k2-turbo-preview`, or `kimi-k2-thinking-turbo`

## See Also

- `crypto_news_analyzer/config/llm_registry.py` - Source of truth for provider/model definitions
- `config.json` - Runtime configuration location
- `.env.template` - Environment variable reference

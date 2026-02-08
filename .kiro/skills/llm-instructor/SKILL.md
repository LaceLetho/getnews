---
name: llm-instructor
description: Use when working with instructor
---

# Instructor: Structured Outputs for LLMs

Get reliable, validated JSON from any LLM using Pydantic models. Instructor transforms natural language into type-safe, structured data with automatic validation, retries, and IDE support.

**Repository:** [567-labs/instructor](https://github.com/567-labs/instructor)
**Language:** Python
**Stars:** 12,338
**License:** MIT License
**Homepage:** https://python.useinstructor.com/

## What is Instructor?

Instructor is a Python library that simplifies extracting structured data from LLM responses. Instead of dealing with JSON parsing, error handling, and validation manually, you define a Pydantic model and Instructor handles everything else—including automatic retries when validation fails.

### Key Benefits
- **Type Safety**: Full IDE autocomplete and type checking with Pydantic
- **Automatic Validation**: Built-in validation with clear error messages
- **Smart Retries**: Failed validations are automatically retried with error feedback
- **Multi-Provider**: Works with OpenAI, Anthropic, Google, Groq, Ollama, and more
- **Production Ready**: Streaming support, parallel tool calls, and custom validators

## When to Use This Skill

Use this skill when you need to:

### Core Use Cases
- **Extract structured data** from natural language (names, dates, entities, etc.)
- **Build type-safe LLM applications** with Pydantic validation
- **Parse and validate JSON** responses from any LLM provider
- **Implement retry logic** for failed LLM extractions
- **Stream partial results** while maintaining type safety
- **Work with multiple LLM providers** using a unified interface

### Specific Scenarios
- Creating chatbots that return structured responses
- Building data extraction pipelines from unstructured text
- Implementing form filling from natural language
- Generating structured analytics or reports
- Validating LLM outputs against business rules
- Converting natural language to database queries or API calls

### Technical Questions
- How to use `response_model` with different providers
- Configuring retry behavior with `max_retries`
- Streaming partial responses with `Partial[T]`
- Using validators (`@field_validator`, `@model_validator`)
- Handling different modes (TOOLS, JSON, MD_JSON, etc.)
- Debugging validation errors and failed extractions

## ⚡ Quick Reference

### Basic Usage - Simple Extraction

```python
import instructor
from pydantic import BaseModel

# Define your data model
class User(BaseModel):
    name: str
    age: int

# Create a client (works with any provider)
client = instructor.from_provider("openai/gpt-4o-mini")

# Extract structured data
user = client.chat.completions.create(
    response_model=User,
    messages=[{"role": "user", "content": "John is 25 years old"}],
)

print(user)  # User(name='John', age=25)
```

### Multi-Provider Support

```python
# OpenAI
client = instructor.from_provider("openai/gpt-4o")

# Anthropic Claude
client = instructor.from_provider("anthropic/claude-3-5-sonnet")

# Google Gemini
client = instructor.from_provider("google/gemini-pro")

# Groq
client = instructor.from_provider("groq/llama-3.1-8b-instant")

# Ollama (local)
client = instructor.from_provider("ollama/llama3")

# With API keys directly (no environment variables needed)
client = instructor.from_provider("openai/gpt-4o", api_key="sk-...")
```

### Automatic Retries on Validation Failure

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    age: int

    @field_validator('age')
    def validate_age(cls, v):
        if v < 0 or v > 150:
            raise ValueError('Age must be between 0 and 150')
        return v

# Instructor will automatically retry if validation fails
# The error message is sent back to the LLM for correction
user = client.chat.completions.create(
    response_model=User,
    max_retries=3,  # Try up to 3 times
    messages=[{"role": "user", "content": "Extract user info"}],
)
```

### Streaming Partial Results

```python
from instructor import Partial

class User(BaseModel):
    name: str
    age: int
    bio: str

# Stream partial results as they arrive
user_stream = client.chat.completions.create(
    response_model=Partial[User],
    stream=True,
    messages=[{"role": "user", "content": "Tell me about John, age 25"}],
)

for partial_user in user_stream:
    print(partial_user)
    # Prints progressively complete User objects
    # User(name='John', age=None, bio=None)
    # User(name='John', age=25, bio=None)
    # User(name='John', age=25, bio='John is...')
```

### Complex Nested Models

```python
from typing import List
from pydantic import BaseModel

class Address(BaseModel):
    street: str
    city: str
    country: str

class User(BaseModel):
    name: str
    age: int
    addresses: List[Address]

# Instructor handles nested validation automatically
user = client.chat.completions.create(
    response_model=User,
    messages=[{
        "role": "user",
        "content": "John, 25, lives at 123 Main St, NYC, USA and 456 Oak Ave, LA, USA"
    }],
)
```

### Using with Native Provider Clients

```python
from openai import OpenAI

# Patch an existing client
client = instructor.from_openai(OpenAI())

# Or with Anthropic
from anthropic import Anthropic
client = instructor.from_anthropic(Anthropic())

# Now use it with response_model
user = client.chat.completions.create(
    model="gpt-4o",
    response_model=User,
    messages=[{"role": "user", "content": "John is 25"}],
)
```

### Custom Validators

```python
from pydantic import BaseModel, field_validator, model_validator

class User(BaseModel):
    name: str
    email: str
    age: int

    @field_validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email address')
        return v

    @model_validator(mode='after')
    def validate_model(self):
        if self.age < 13 and '@' in self.email:
            raise ValueError('Users under 13 cannot have email addresses')
        return self
```

### Parallel Tool Calls

```python
from typing import List

# Extract multiple entities in parallel
users = client.chat.completions.create(
    response_model=List[User],
    messages=[{
        "role": "user",
        "content": "John is 25, Sarah is 30, and Mike is 22"
    }],
)
# Returns: [User(name='John', age=25), User(name='Sarah', age=30), ...]
```

## 📖 Available References

This skill synthesizes information from multiple reference sources:

### Primary Documentation
- **`references/README.md`** - Official README with quick start, examples, and core concepts
  - Source: GitHub repository
  - Confidence: Medium
  - Contains: Installation, basic usage, provider setup, feature overview

### Version History
- **`references/CHANGELOG.md`** - Detailed version history following semantic versioning
  - Source: Repository changelog
  - Confidence: Medium
  - Contains: Breaking changes, new features, bug fixes, deprecations
  - Recent focus: Streaming improvements, validation enhancements, provider updates

### Issue Tracking
- **`references/issues.md`** - Recent GitHub issues (64 total, 10 open)
  - Source: GitHub Issues API
  - Confidence: Medium
  - Contains: Bug reports, feature requests, real-world usage problems
  - Notable: Security issues (#2056), streaming bugs, provider-specific issues

### Release Notes
- **`references/releases.md`** - Release history (106 releases)
  - Source: GitHub Releases
  - Confidence: Medium
  - Contains: Version summaries, contributor acknowledgments, changelog links
  - Latest: v1.14.5 (2026-01-29)

### Repository Structure
- **`references/file_structure.md`** - Complete file tree (947 items)
  - Source: Repository file listing
  - Confidence: Medium
  - Contains: Core modules, examples, tests, documentation structure
  - Key directories: `instructor/`, `examples/`, `docs/`, `tests/`

## 🔑 Key Concepts

### Response Models
The `response_model` parameter defines the expected structure. Instructor converts LLM outputs into validated instances of this model.

```python
# Simple model
response_model=User

# List of models
response_model=List[User]

# Streaming with partial models
response_model=Partial[User]
```

### Modes
Different providers support different extraction modes:

- **`Mode.TOOLS`** (default): Uses function calling/tools API (OpenAI, Anthropic, etc.)
- **`Mode.JSON`**: Uses JSON mode (OpenAI, some providers)
- **`Mode.MD_JSON`**: Extracts JSON from markdown code blocks
- **`Mode.JSON_SCHEMA`**: Uses JSON schema for validation

Provider-specific modes are automatically selected via `from_provider()`.

### Validation Flow
1. LLM generates response
2. Instructor parses response into Pydantic model
3. Pydantic validators run (field validators, model validators)
4. If validation fails and `max_retries > 0`:
   - Error message is sent back to LLM
   - LLM tries again with error context
   - Repeat until success or max retries reached
5. Return validated model instance

### Streaming with Partial
The `Partial[T]` wrapper allows streaming incomplete models:
- Fields are Optional during streaming
- Validates completed JSON structures only (v1.14.3+)
- Final result is validated against original model
- Deprecated: `PartialLiteralMixin` (use completeness-based validation)

## 🏗️ Working with This Skill

### For Beginners
Start with:
1. Read `references/README.md` for installation and basic examples
2. Try the simple extraction example above
3. Experiment with different Pydantic models
4. Learn about field validators for custom validation

### For Intermediate Users
Explore:
1. Multi-provider support in `references/README.md`
2. Streaming examples in `examples/` directory
3. Different modes and when to use them
4. Complex nested models and List responses
5. Check `references/issues.md` for known limitations

### For Advanced Users
Deep dive into:
1. `references/file_structure.md` to understand architecture
2. Custom validators and model validators
3. Batch processing examples (`examples/batch_api/`)
4. Hook system (`instructor/hooks.py`)
5. Provider-specific implementations in `instructor/providers/`
6. Recent changes in `references/CHANGELOG.md`

### Debugging Tips
- Enable logging to see validation errors
- Check `references/issues.md` for similar problems
- Try `Mode.MD_JSON` if function calling fails
- Use `max_retries=0` to see raw validation errors
- Read recent release notes for bug fixes

## ⚠️ Known Issues

*Based on GitHub issues as of 2026-02-07*

### Critical Security Issues
- **#2056**: Retry amplification and LLM validator injection vulnerabilities [`priority:critical`]
  - Use caution with untrusted inputs and high retry counts

### Common Bugs
- **#1871**: Batch CLI truncates batch IDs
- **#1514**: System prompt issues with `Mode.JSON`
- **#2054**: Streaming problems with `Literal["Value"] = "value"`
- **#2049**: ParallelTools bug with Qwen3-VL models
- **#1954**: Bedrock caching broken in v1.13.0 (fixed in later versions)

### Provider-Specific Issues
- **#1303**: Gemini - `create_with_completion` fails with `List[Object]` response models
- **#1489**: Gemini modes don't work with LiteLLM
- **#1925**: Moonshot 'kimi-k2-thinking' model incompatibility
- **#1764**: OpenRouter retry logic not working correctly

### Documentation Issues
- **#2063**: MLflow integration documentation needed
- **#1764**: Some documentation is outdated

See `references/issues.md` for the complete list of 64 tracked issues.

## 📊 Recent Updates

### v1.14.5 (2026-01-29)
- Fixed PyPI metadata for better package statistics

### v1.14.4 (2026-01-16)
- Simplified JSON completeness tracking with `jiter` parsing
- Fixed validation errors in Responses API
- Fixed crashes with List objects

### v1.14.3 (2026-01-13)
- **Major improvement**: Completeness-based validation for streaming
  - Only validates structurally complete JSON
  - Field constraints (`min_length`, `max_length`, etc.) now work during streaming
- Fixed Stream objects crashing with `max_retries > 1`
- Deprecated `PartialLiteralMixin` (automatic handling now)

### v1.14.2 (2026-01-13)
- Fixed model validators crashing during streaming
- Fixed infinite recursion with self-referential models
- Added final validation after streaming completes

### v1.14.1 (2026-01-08)
- Added Google Gemini context caching support

### v1.14.0 (2026-01-08)
- Standardized provider factory methods across codebase
- Comprehensive documentation improvements and SEO optimization
- Enhanced README with PydanticAI comparison

See `references/CHANGELOG.md` and `references/releases.md` for complete history.

## 🔗 Related Tools

### PydanticAI
For agent-based workflows with richer observability and tool support, consider [PydanticAI](https://ai.pydantic.dev/):
- **Use Instructor for**: Fast, schema-first extraction; simple, cheap workflows
- **Use PydanticAI for**: Agent runs with tools, observability, shareable traces, evals

Both use Pydantic models for type safety, but PydanticAI adds:
- Typed tools and multi-step agent flows
- Built-in observability and production dashboards
- Replayable datasets for testing and evaluation

### Integration Examples
The repository includes extensive examples in `examples/`:
- Anthropic web tools (`anthropic-web-tool/`)
- Batch processing (`batch_api/`, `batch-classification/`)
- Streaming (`partial_streaming/`, `stream_action_items/`)
- Knowledge graphs (`knowledge-graph/`)
- Vision models (`vision/`, `openai-audio/`)
- FastAPI integration (`fastapi_app/`, `logfire-fastapi/`)
- And 40+ more real-world patterns

## 🎯 Best Practices

### 1. Start with Simple Models
Begin with basic models and add complexity gradually:
```python
# Good: Simple, clear model
class User(BaseModel):
    name: str
    age: int

# Complex models can come later
class DetailedUser(User):
    email: str
    addresses: List[Address]
    preferences: dict
```

### 2. Use Validators Wisely
Add validators for business logic, not format parsing:
```python
# Good: Business rule validation
@field_validator('age')
def validate_age(cls, v):
    if v < 18:
        raise ValueError('Must be 18 or older')
    return v

# Let Pydantic handle format validation automatically
email: str  # Pydantic handles basic format
```

### 3. Handle Provider Differences
Use `from_provider()` for automatic mode selection:
```python
# Good: Automatic provider handling
client = instructor.from_provider("anthropic/claude-3-5-sonnet")

# Avoid: Manual mode configuration (unless necessary)
client = instructor.patch(Anthropic(), mode=instructor.Mode.ANTHROPIC_TOOLS)
```

### 4. Set Appropriate Retry Limits
Balance reliability with cost:
```python
# For critical extractions
max_retries=3

# For experimental/dev work
max_retries=1

# To debug validation errors
max_retries=0  # See raw errors immediately
```

### 5. Use Streaming for Long Responses
Stream when generating long-form content:
```python
# Good for: Essays, reports, detailed descriptions
response_model=Partial[Article]
stream=True

# Not needed for: Simple extractions, short responses
response_model=User
stream=False
```

## 🆘 Getting Help

1. **Check the documentation**: Start with `references/README.md`
2. **Search issues**: Look in `references/issues.md` for similar problems
3. **Review examples**: Browse `examples/` directory (see `references/file_structure.md`)
4. **Check recent changes**: Review `references/CHANGELOG.md` for bug fixes
5. **GitHub Issues**: [Report new issues](https://github.com/567-labs/instructor/issues)
6. **Discord**: Join the community at https://discord.gg/bD9YE9JArw
7. **Twitter**: Follow [@jxnlco](https://twitter.com/jxnlco) for updates

## 📦 Repository Structure

Key directories (see `references/file_structure.md` for complete tree):

```
instructor/
├── instructor/          # Core library code
│   ├── providers/       # Provider-specific implementations
│   ├── dsl/            # Domain-specific language utilities
│   ├── batch/          # Batch processing support
│   ├── cli/            # Command-line interface
│   └── validation/     # Validation utilities
├── examples/           # 40+ real-world examples
├── docs/              # Documentation source
├── tests/             # Test suite
└── references/        # Generated reference docs (this skill)
```

## 🔖 Quick Links

- **Homepage**: https://python.useinstructor.com/
- **Repository**: https://github.com/567-labs/instructor
- **PyPI**: https://pypi.org/project/instructor/
- **Discord**: https://discord.gg/bD9YE9JArw
- **PydanticAI** (related): https://ai.pydantic.dev/

---

**Last Updated**: 2026-02-07
**Generated by Skill Seeker** | Multi-Source GitHub Repository Scraper
**Sources**: README.md, CHANGELOG.md, issues.md, releases.md, file_structure.md

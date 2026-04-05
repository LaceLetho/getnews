# Grok API - Files Api

**Sections:** 5

---

## Table of Contents

- developers/files-api
- developers/files/collections/metadata
- developers/files/collections
- developers/files/managing-files
- developers/files

---

===/developers/files-api===
#### Files API Reference

# Files API Reference

***

## GET /v1/files

API endpoint for GET requests to /v1/files.

```
Method: GET
Path: /v1/files
```

***

## POST /v1/files

API endpoint for POST requests to /v1/files.

```
Method: POST
Path: /v1/files
```

***

## POST /v1/files/batch\_upload

API endpoint for POST requests to /v1/files/batch\_upload.

```
Method: POST
Path: /v1/files/batch_upload
```

***

## POST /v1/files/batch\_upload/\{batch\_job\_id}:complete

API endpoint for POST requests to /v1/files/batch\_upload/\{batch\_job\_id}:complete.

```
Method: POST
Path: /v1/files/batch_upload/{batch_job_id}:complete
```

***

## GET /v1/files/\{file\_id}

API endpoint for GET requests to /v1/files/\{file\_id}.

```
Method: GET
Path: /v1/files/{file_id}
```

***

## DELETE /v1/files/\{file\_id}

API endpoint for DELETE requests to /v1/files/\{file\_id}.

```
Method: DELETE
Path: /v1/files/{file_id}
```

***

## PUT /v1/files/\{file\_id}

API endpoint for PUT requests to /v1/files/\{file\_id}.

```
Method: PUT
Path: /v1/files/{file_id}
```

***

## POST /v1/files:download

API endpoint for POST requests to /v1/files:download.

```
Method: POST
Path: /v1/files:download
```

***

## POST /v1/files:initialize

API endpoint for POST requests to /v1/files:initialize.

```
Method: POST
Path: /v1/files:initialize
```

***

## POST /v1/files:uploadChunks

API endpoint for POST requests to /v1/files:uploadChunks.

```
Method: POST
Path: /v1/files:uploadChunks
```

===/developers/files/collections/metadata===
#### Files & Collections

# Metadata Fields

Metadata fields allow you to attach structured attributes to documents in a collection. These fields enable:

* **Filtered retrieval** — Narrow search results to documents matching specific criteria (e.g., `author="Sandra Kim"`)
* **Contextual embeddings** — Inject metadata into chunks to improve retrieval accuracy (e.g., prepending document title to each chunk)
* **Data integrity constraints** — Enforce required fields or uniqueness across documents

## Creating a Collection with Metadata Fields

Define metadata fields using `field_definitions` when creating a collection:

### Field Definition Options

| Option | Description |
|--------|-------------|
| `required` | Document uploads must include this field. Defaults to `false`. |
| `unique` | Only one document in the collection can have a given value for this field. Defaults to `false`. |
| `inject_into_chunk` | Prepends this field's value to every embedding chunk, improving retrieval by providing context. Defaults to `false`. |

## Uploading Documents with Metadata

Include metadata as a JSON object in the `fields` parameter:

## Filtering Documents in Search

Use the `filter` parameter to restrict search results based on metadata values. The filter uses AIP-160 syntax:

### Supported Filter Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `=` | `author="Jane"` | Equals |
| `!=` | `status!="draft"` | Not equals |
| `<`, `>`, `<=`, `>=` | `year>=2020` | Numeric/lexical comparison |
| `AND` | `a="x" AND b="y"` | Both conditions must match |
| `OR` | `a="x" OR a="y"` | Either condition matches |

`OR` has higher precedence than `AND`. Use parentheses for clarity: `a="x" AND (b="y" OR b="z")`.

Wildcard matching (e.g., `author="E*"`) is not supported. All string comparisons are exact matches.

Filtering on fields that don't exist in your documents returns no results. Double-check that field names match your collection's `field_definitions`.

## AIP-160 Filter String Examples

### Basic Examples

```bash
# Equality (double or single quotes for strings with spaces)
author="Sandra Kim"
author='Sandra Kim'

# Equality (no quotes needed for simple values)
year=2024
status=active

# Not equal
status!="archived"
status!='archived'
```

### Comparison Operators

```bash
# Numeric comparisons
year>=2020
year>2019
score<=0.95
price<100

# Combined comparisons (range)
year>=2020 AND year<=2024
```

### Logical Operators

```bash
# AND - both conditions must match
author="Sandra Kim" AND year=2024

# OR - either condition matches
status="pending" OR status="in_progress"

# Combined (OR has higher precedence than AND)
department="Engineering" AND status="active" OR status="pending"

# Use parentheses for clarity
department="Engineering" AND (status="active" OR status="pending")
```

### Complex Examples

```bash
# Multiple conditions
author="Sandra Kim" AND year>=2020 AND status!="draft"

# Nested logic with parentheses
(author="Sandra Kim" OR author="John Doe") AND year>=2020

# Multiple fields with mixed operators
category="finance" AND (year=2023 OR year=2024) AND status!="archived"
```

## Quick Reference

| Use Case | Filter String |
|----------|---------------|
| Exact match | `author="Sandra Kim"` |
| Numeric comparison | `year>=2020` |
| Not equal | `status!="archived"` |
| Multiple conditions | `author="Sandra Kim" AND year=2024` |
| Either condition | `status="pending" OR status="draft"` |
| Grouped logic | `(status="active" OR status="pending") AND year>=2020` |
| Complex filter | `category="finance" AND year>=2020 AND status!="archived"` |

===/developers/files/collections===
#### Files & Collections

# Collections

Collections offers xAI API users a robust set of tools and methods to seamlessly integrate their enterprise requirements and internal knowledge bases with the xAI API. Whether you're building a RAG application or need to search across large document sets, Collections provides the infrastructure to manage and query your content.

**Looking for Files?** If you want to attach files directly to chat messages for conversation context, see [Files](/developers/files). Collections are different—they provide persistent document storage with semantic search across many documents.

## Core Concepts

There are two entities that users can create within the Collections service:

* **File** — A single entity of a user-uploaded file.
* **Collection** — A group of files linked together, with an embedding index for efficient retrieval.
  * When you create a collection you have the option to automatically generate embeddings for any files uploaded to that collection. You can then perform semantic search across files in multiple collections.
  * A single file can belong to multiple collections but must be part of at least one collection.

## What You Can Do

With Collections, you can:

* **Create collections** to organize your documents
* **Upload documents** in various formats (HTML, PDF, text, etc.)
* **Search semantically** across your documents using natural language queries
* **Configure chunking and embeddings** to optimize retrieval
* **Manage documents** by listing, updating, and deleting them

## Getting Started

Choose how you want to work with Collections:

* [Using the Console →](/console/collections) - Create collections and upload documents through the xAI Console interface
* [Using the API →](/developers/files/collections/api) - Programmatically manage collections with the SDK and REST API

## Metadata Fields

Collections support **metadata fields** — structured attributes you can attach to documents for enhanced retrieval and data integrity:

* **Filtered retrieval** — Narrow search results to documents matching specific criteria (e.g., `author="Sandra Kim"`)
* **Contextual embeddings** — Inject metadata into chunks to improve retrieval accuracy (e.g., prepending document title to each chunk)
* **Data integrity constraints** — Enforce required fields or uniqueness across documents

When creating a collection, define metadata fields with options like `required`, `unique`, and `inject_into_chunk` to control how metadata is validated and used during search.

[Learn more about metadata fields →](/developers/files/collections/metadata)

## Usage Limits

To be able to upload files and add to a collections you must have credits in your account.

**Maximum file size**: 100MB**Maximum number of files**: 100,000 files uploaded globally.**Maximum total size**: 100GB

Please [contact us](https://x.ai/contact) to increase any of these limits.

## Data Privacy

We do not use user data stored on Collections for model training purposes.

## Supported MIME Types

While we support any `UTF-8` encoded text file, we also have special file conversion and chunking techniques for certain MIME types.

The following would be a non-exhaustive list for the MIME types that we support:

* application/csv
* application/dart
* application/ecmascript
* application/epub
* application/epub+zip
* application/json
* application/ms-java
* application/msword
* application/pdf
* application/typescript
* application/vnd.adobe.pdf
* application/vnd.curl
* application/vnd.dart
* application/vnd.jupyter
* application/vnd.ms-excel
* application/vnd.ms-outlook
* application/vnd.oasis.opendocument.text
* application/vnd.openxmlformats-officedocument.presentationml.presentation
* application/vnd.openxmlformats-officedocument.presentationml.slide
* application/vnd.openxmlformats-officedocument.presentationml.slideshow
* application/vnd.openxmlformats-officedocument.presentationml.template
* application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
* application/vnd.openxmlformats-officedocument.spreadsheetml.template
* application/vnd.openxmlformats-officedocument.wordprocessingml.document
* application/x-csh
* application/x-epub+zip
* application/x-hwp
* application/x-hwp-v5
* application/x-latex
* application/x-pdf
* application/x-php
* application/x-powershell
* application/x-sh
* application/x-shellscript
* application/x-tex
* application/x-zsh
* application/xhtml
* application/xml
* application/zip
* text/cache-manifest
* text/calendar
* text/css
* text/csv
* text/html
* text/javascript
* text/jsx
* text/markdown
* text/n3
* text/php
* text/plain
* text/rtf
* text/tab-separated-values
* text/troff
* text/tsv
* text/tsx
* text/turtle
* text/uri-list
* text/vcard
* text/vtt
* text/x-asm
* text/x-bibtex
* text/x-c
* text/x-c++hdr
* text/x-c++src
* text/x-chdr
* text/x-coffeescript
* text/x-csh
* text/x-csharp
* text/x-csrc
* text/x-d
* text/x-diff
* text/x-emacs-lisp
* text/x-erlang
* text/x-go
* text/x-haskell
* text/x-java
* text/x-java-properties
* text/x-java-source
* text/x-kotlin
* text/x-lisp
* text/x-lua
* text/x-objcsrc
* text/x-pascal
* text/x-perl
* text/x-perl-script
* text/x-python
* text/x-python-script
* text/x-r-markdown
* text/x-rst
* text/x-ruby-script
* text/x-rust
* text/x-sass
* text/x-scala
* text/x-scheme
* text/x-script.python
* text/x-scss
* text/x-sh
* text/x-sql
* text/x-swift
* text/x-tcl
* text/x-tex
* text/x-vbasic
* text/x-vcalendar
* text/xml
* text/xml-dtd
* text/yaml

===/developers/files/managing-files===
#### Files & Collections

# Managing Files

The Files API provides a complete set of operations for managing your files. Before using files in chat conversations, you need to upload them using one of the methods described below.

## Uploading Files

You can upload files in several ways: from a file path, raw bytes, BytesIO object, or an open file handle.

### Upload from File Path

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload a file from disk
file = client.files.upload("/path/to/your/document.pdf")

print(f"File ID: {file.id}")
print(f"Filename: {file.filename}")
print(f"Size: {file.size} bytes")
print(f"Created at: {file.created_at}")
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Upload a file
with open("/path/to/your/document.pdf", "rb") as f:
    file = client.files.create(
        file=f,
        purpose="assistants"
    )

print(f"File ID: {file.id}")
print(f"Filename: {file.filename}")
```

```pythonRequests
import os
import requests

url = "https://api.x.ai/v1/files"
headers = {
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}

with open("/path/to/your/document.pdf", "rb") as f:
    files = {"file": f}
    data = {"purpose": "assistants"}
    response = requests.post(url, headers=headers, files=files, data=data)

file_data = response.json()
print(f"File ID: {file_data['id']}")
print(f"Filename: {file_data['filename']}")
```

```bash
curl https://api.x.ai/v1/files \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -F file=@/path/to/your/document.pdf \\
  -F purpose=assistants
```

### Upload from Bytes

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload file content directly from bytes
content = b"This is my document content.\\nIt can span multiple lines."
file = client.files.upload(content, filename="document.txt")

print(f"File ID: {file.id}")
print(f"Filename: {file.filename}")
```

### Upload from file object

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Upload a file directly from disk
file = client.files.upload(open("document.pdf", "rb"), filename="document.pdf")

print(f"File ID: {file.id}")
print(f"Filename: {file.filename}")
```

## Upload with Progress Tracking

Track upload progress for large files using callbacks or progress bars.

### Custom Progress Callback

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Define a custom progress callback
def progress_callback(bytes_uploaded: int, total_bytes: int):
    percentage = (bytes_uploaded / total_bytes) * 100 if total_bytes else 0
    mb_uploaded = bytes_uploaded / (1024 * 1024)
    mb_total = total_bytes / (1024 * 1024)
    print(f"Progress: {mb_uploaded:.2f}/{mb_total:.2f} MB ({percentage:.1f}%)")

# Upload with progress tracking
file = client.files.upload(
    "/path/to/large-file.pdf",
    on_progress=progress_callback
)

print(f"Successfully uploaded: {file.filename}")
```

### Progress Bar with tqdm

```pythonXAI
import os
from xai_sdk import Client
from tqdm import tqdm

client = Client(api_key=os.getenv("XAI_API_KEY"))

file_path = "/path/to/large-file.pdf"
total_bytes = os.path.getsize(file_path)

# Upload with tqdm progress bar
with tqdm(total=total_bytes, unit="B", unit_scale=True, desc="Uploading") as pbar:
    file = client.files.upload(
        file_path,
        on_progress=pbar.update
    )

print(f"Successfully uploaded: {file.filename}")
```

## Listing Files

Retrieve a list of your uploaded files with pagination and sorting options.

### Available Options

* **`limit`**: Maximum number of files to return. If not specified, uses server default of 100.
* **`order`**: Sort order for the files. Either `"asc"` (ascending) or `"desc"` (descending).
* **`sort_by`**: Field to sort by. Options: `"created_at"`, `"filename"`, or `"size"`.
* **`pagination_token`**: Token for fetching the next page of results.

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# List files with pagination and sorting
response = client.files.list(
    limit=10,
    order="desc",
    sort_by="created_at"
)

for file in response.data:
    print(f"File: {file.filename} (ID: {file.id}, Size: {file.size} bytes)")
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# List files
files = client.files.list()

for file in files.data:
    print(f"File: {file.filename} (ID: {file.id})")
```

```pythonRequests
import os
import requests

url = "https://api.x.ai/v1/files"
headers = {
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}

response = requests.get(url, headers=headers)
files = response.json()

for file in files.get("data", []):
    print(f"File: {file['filename']} (ID: {file['id']})")
```

```bash
curl https://api.x.ai/v1/files \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

## Getting File Metadata

Retrieve detailed information about a specific file.

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Get file metadata by ID
file = client.files.get("file-abc123")

print(f"Filename: {file.filename}")
print(f"Size: {file.size} bytes")
print(f"Created: {file.created_at}")
print(f"Team ID: {file.team_id}")
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Get file metadata
file = client.files.retrieve("file-abc123")

print(f"Filename: {file.filename}")
print(f"Size: {file.bytes} bytes")
```

```pythonRequests
import os
import requests

file_id = "file-abc123"
url = f"https://api.x.ai/v1/files/{file_id}"
headers = {
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}

response = requests.get(url, headers=headers)
file = response.json()

print(f"Filename: {file['filename']}")
print(f"Size: {file['bytes']} bytes")
```

```bash
curl https://api.x.ai/v1/files/file-abc123 \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

## Getting File Content

Download the actual content of a file.

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Get file content
content = client.files.content("file-abc123")

# Content is returned as bytes
print(f"Content length: {len(content)} bytes")
print(f"Content preview: {content[:100]}")
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Get file content
content = client.files.content("file-abc123")

print(f"Content: {content.text}")
```

```pythonRequests
import os
import requests

file_id = "file-abc123"
url = f"https://api.x.ai/v1/files/{file_id}/content"
headers = {
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}

response = requests.get(url, headers=headers)
content = response.content

print(f"Content length: {len(content)} bytes")
```

```bash
curl https://api.x.ai/v1/files/file-abc123/content \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

## Deleting Files

Remove files when they're no longer needed.

```pythonXAI
import os
from xai_sdk import Client

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Delete a file
delete_response = client.files.delete("file-abc123")

print(f"Deleted: {delete_response.deleted}")
print(f"File ID: {delete_response.id}")
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Delete a file
delete_response = client.files.delete("file-abc123")

print(f"Deleted: {delete_response.deleted}")
print(f"File ID: {delete_response.id}")
```

```pythonRequests
import os
import requests

file_id = "file-abc123"
url = f"https://api.x.ai/v1/files/{file_id}"
headers = {
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}

response = requests.delete(url, headers=headers)
result = response.json()

print(f"Deleted: {result['deleted']}")
print(f"File ID: {result['id']}")
```

```bash
curl -X DELETE https://api.x.ai/v1/files/file-abc123 \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

## Limitations and Considerations

### File Size Limits

* **Maximum file size**: 48 MB per file
* **Processing time**: Larger files may take longer to process

### File Retention

* **Cleanup**: Delete files when no longer needed to manage storage
* **Access**: Files are scoped to your team/organization

### Supported Formats

While many text-based formats are supported, the system works best with:

* Structured documents (with clear sections, headings)
* Plain text and markdown
* Documents with clear information hierarchy

Supported file types include:

* Plain text files (.txt)
* Markdown files (.md)
* Code files (.py, .js, .java, etc.)
* CSV files (.csv)
* JSON files (.json)
* PDF documents (.pdf)
* And many other text-based formats

## Next Steps

Now that you know how to manage files, learn how to use them in chat conversations:

===/developers/files===
#### Files & Collections

# Files

The Files API enables you to upload documents and use them in chat conversations with Grok. When you attach files to a chat message, the system automatically activates the `attachment_search` tool, transforming your request into an agentic workflow where Grok can intelligently search through and reason over your documents to answer questions.

You can view more information at [Files API Reference](/developers/files-api).

**Looking for Collections?** If you need persistent document storage with semantic search across many documents, see [Collections](/developers/files/collections). Files are different—they're for attaching documents to chat conversations for immediate context.

## How Files Work with Chat

Behind the scenes, when you attach files to a chat message, the xAI API implicitly adds the `attachment_search` server-side tool to your request. This means:

1. **Automatic Agentic Behavior**: Your chat request becomes an agentic request, where Grok autonomously searches through your documents
2. **Intelligent Document Analysis**: The model can reason over document content, extract relevant information, and synthesize answers
3. **Multi-Document Support**: You can attach multiple files, and Grok will search across all of them

This seamless integration allows you to simply attach files and ask questions—the complexity of document search and retrieval is handled automatically by the agentic workflow.

## Understanding Document Search

When you attach files to a chat message, the xAI API automatically activates the `attachment_search` [server-side tool](/developers/tools/overview). This transforms your request into an [agentic workflow](/developers/tools/overview#how-it-works) where Grok:

1. **Analyzes your query** to understand what information you're seeking
2. **Searches the documents** intelligently, finding relevant sections across all attached files
3. **Extracts and synthesizes information** from multiple sources if needed
4. **Provides a comprehensive answer** with the context from your documents

### Agentic Workflow

Just like other agentic tools (web search, X search, code execution), document search operates autonomously:

* **Multiple searches**: The model may search documents multiple times with different queries to find comprehensive information
* **Reasoning**: The model uses its reasoning capabilities to decide what to search for and how to interpret the results
* **Streaming visibility**: In streaming mode, you can see when the model is searching your documents via tool call notifications

### Token Usage with Files

File-based chats follow similar token patterns to other agentic requests:

* **Prompt tokens**: Include the conversation history and internal processing. Document content is processed efficiently
* **Reasoning tokens**: Used for planning searches and analyzing document content
* **Completion tokens**: The final answer text
* **Cached tokens**: Repeated document content benefits from prompt caching for efficiency

The actual document content is processed by the server-side tool and doesn't directly appear in the message history, keeping token usage optimized.

### Pricing

Document search is billed per tool invocation, in addition to standard token costs. Each time the model searches your documents, it counts as one tool invocation. For complete pricing details, see the [Tools Pricing](/developers/models#tools-pricing) table.

## Getting Started

To use files with Grok, you'll need to:

1. **[Upload and manage files](/developers/files/managing-files)** - Learn how to upload, list, retrieve, and delete files using the Files API
2. **[Chat with files](/developers/model-capabilities/files/chat-with-files)** - Discover how to attach files to chat messages and ask questions about your documents

## Quick Example

Here's a quick example of the complete workflow:

```pythonXAI
import os
from xai_sdk import Client
from xai_sdk.chat import user, file

client = Client(api_key=os.getenv("XAI_API_KEY"))

# 1. Upload a document
document_content = b"""Quarterly Sales Report - Q4 2024
Total Revenue: $5.2M
Growth: +18% YoY
"""

uploaded_file = client.files.upload(document_content, filename="sales.txt")

# 2. Chat with the file
chat = client.chat.create(model="grok-4-fast")
chat.append(user("What was the total revenue?", file(uploaded_file.id)))

# 3. Get the answer
response = chat.sample()
print(response.content)  # "The total revenue was $5.2M"

# 4. Clean up
client.files.delete(uploaded_file.id)
```

## Key Features

### Multiple File Support

Attach [multiple documents](/developers/model-capabilities/files/chat-with-files#multiple-file-attachments) to a single query and Grok will search across all of them to find relevant information.

### Multi-Turn Conversations

File context persists across [conversation turns](/developers/model-capabilities/files/chat-with-files#multi-turn-conversations-with-files), allowing you to ask follow-up questions without re-attaching files.

### Code Execution Integration

Combine files with the [code execution tool](/developers/model-capabilities/files/chat-with-files#combining-files-with-code-execution) to perform advanced data analysis, statistical computations, and transformations on your uploaded data. The model can write and execute Python code that processes your files directly.

## Limitations

* **File size**: Maximum 48 MB per file
* **No batch requests**: File attachments with document search are agentic requests and do not support batch mode (`n > 1`)
* **Agentic models only**: Requires models that support agentic tool calling (e.g., `grok-4-fast`, `grok-4`)
* **Supported file formats**:
  * Plain text files (.txt)
  * Markdown files (.md)
  * Code files (.py, .js, .java, etc.)
  * CSV files (.csv)
  * JSON files (.json)
  * PDF documents (.pdf)
  * And many other text-based formats

## Next Steps


# Grok API - Advanced Api Usage

**Sections:** 7

---

## Table of Contents

- developers/advanced-api-usage/async
- developers/advanced-api-usage/batch-api
- developers/advanced-api-usage/deferred-chat-completions
- developers/advanced-api-usage/fingerprint
- developers/advanced-api-usage/grok-code-prompt-engineering
- developers/advanced-api-usage
- developers/advanced-api-usage/use-with-code-editors

---

===/developers/advanced-api-usage/async===
#### Advanced API Usage

# Asynchronous Requests

When working with the xAI API, you may need to process hundreds or even thousands of requests. Sending these requests sequentially can be extremely time-consuming.

To improve efficiency, you can use `AsyncClient` from `xai_sdk` or `AsyncOpenAI` from `openai`, which allows you to send multiple requests concurrently. The example below is a Python script demonstrating how to use `AsyncClient` to batch and process requests asynchronously, significantly reducing the overall execution time:

You can also use our Batch API to queue the requests and fetch them later. Please visit [Batch API](/developers/advanced-api-usage/batch-api) for more information.

## Rate Limits

Adjust the `max_concurrent` param to control the maximum number of parallel requests.

You are unable to concurrently run your requests beyond the rate limits shown in the API console.

```pythonXAI
import asyncio
import os

from xai_sdk import AsyncClient
from xai_sdk.chat import Response, user

async def main():
    client = AsyncClient(
        api_key=os.getenv("XAI_API_KEY"),
        timeout=3600, # Override default timeout with longer timeout for reasoning models
    )

    model = "grok-4-1-fast-reasoning"
    requests = [
        "Tell me a joke",
        "Write a funny haiku",
        "Generate a funny X post",
        "Say something unhinged",
    ]


    # Define a semaphore to limit concurrent requests (e.g., max 2 concurrent requests at a time)
    max_in_flight_requests = 2
    semaphore = asyncio.Semaphore(max_in_flight_requests)

    async def process_request(request) -> Response:
        async with semaphore:
            print(f"Processing request: {request}")
            chat = client.chat.create(model=model, max_tokens=100)
            chat.append(user(request))
            return await chat.sample()

    tasks = []
    for request in requests:
        tasks.append(process_request(request))

    responses = await asyncio.gather(*tasks)
    for i, response in enumerate(responses):
        print(f"Total tokens used for response {i}: {response.usage.total_tokens}")

if __name__ == "__main__":
    asyncio.run(main())
```

```pythonOpenAISDK
import asyncio
import os
import httpx
from asyncio import Semaphore

from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
    timeout=httpx.Timeout(3600.0) # Override default timeout with longer timeout for reasoning models
)

async def send_request(sem: Semaphore, request: str) -> dict:
    """Send a single request to xAI with semaphore control."""
    # The 'async with sem' ensures only a limited number of requests run at once
    async with sem:
        return await client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            messages=[{"role": "user", "content": request}]
        )

async def process_requests(requests: list[str], max_concurrent: int = 2) -> list[dict]:
    """Process multiple requests with controlled concurrency."""
    # Create a semaphore that limits how many requests can run at the same time # Think of it like having only 2 "passes" to make requests simultaneously
    sem = Semaphore(max_concurrent)

    # Create a list of tasks (requests) that will run using the semaphore
    tasks = [send_request(sem, request) for request in requests]

    # asyncio.gather runs all tasks in parallel but respects the semaphore limit
    # It waits for all tasks to complete and returns their results
    return await asyncio.gather(*tasks)

async def main() -> None:
    """Main function to handle requests and display responses."""
    requests = [
        "Tell me a joke",
        "Write a funny haiku",
        "Generate a funny X post",
        "Say something unhinged"
    ]

    # This starts processing all asynchronously, but only 2 at a time
    # Instead of waiting for each request to finish before starting the next,
    # we can have 2 requests running at once, making it faster overall
    responses = await process_requests(requests)

    # Print each response in order
    for i, response in enumerate(responses):
        print(f"# Response {i}:")
        print(response.choices[0].message.content)

if __name__ == "__main__":
    asyncio.run(main())
```

===/developers/advanced-api-usage/batch-api===
#### Advanced API Usage

# Batch API

The Batch API lets you process large volumes of requests asynchronously at **50% off** compared to real-time API calls.

## What is the Batch API?

When you make a standard API call to Grok, you send a request and wait for an immediate response. This approach is perfect for interactive applications like chatbots, real-time assistants, or any use case where users are waiting for a response.

The Batch API takes a different approach. Instead of processing requests immediately, you submit them to a queue where they're processed in the background. You don't get an instant response—instead, you check back later to retrieve your results.

**Key differences from real-time API requests:**

| | Real-time API | Batch API |
|---|---|---|
| **Response time** | Immediate (seconds) | Typically within 24 hours |
| **Cost** | Standard pricing | **50% off** standard pricing |
| **Rate limits** | Per-minute limits apply | Requests don't count towards rate limits |
| **Use case** | Interactive, real-time | Background processing, bulk jobs |

**Processing time:** Most batch requests complete within **24 hours**, though processing time may vary depending on system load and batch size.

You can also create, monitor, and manage batches through the [xAI Console](https://console.x.ai/team/default/batches). The Console provides a visual interface for tracking batch progress and viewing results.

## When to use the Batch API

The Batch API is ideal when you don't need immediate results and want to **cut your API costs in half**:

* **Running evaluations and benchmarks** - Test model performance across thousands of prompts
* **Processing large datasets** - Analyze customer feedback, classify support tickets, extract entities
* **Content moderation at scale** - Review backlogs of user-generated content
* **Document summarization** - Process reports, research papers, or legal documents in bulk
* **Data enrichment pipelines** - Add AI-generated insights to database records
* **Scheduled overnight jobs** - Generate daily reports or prepare data for dashboards

## How it works

The Batch API workflow consists of four main steps:

1. **Create a batch** - A batch is a container that groups related requests together
2. **Add requests** - Submit your inference requests to the batch queue
3. **Monitor progress** - Poll the batch status to track completion
4. **Retrieve results** - Fetch responses for all processed requests

Let's walk through each step.

## Step 1: Create a batch

A batch acts as a container for your requests. Think of it as a folder that groups related work together—you might create separate batches for different datasets, experiments, or job types.

When you create a batch, you receive a `batch_id` that you'll use to add requests and retrieve results.

```bash
curl -X POST https://api.x.ai/v1/batches \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
    "name": "customer_feedback_analysis"
  }'
```

```pythonXAI
from xai_sdk import Client

client = Client()

# Create a batch with a descriptive name
batch = client.batch.create(batch_name="customer_feedback_analysis")
print(f"Created batch: {batch.batch_id}")

# Store the batch_id for later use
batch_id = batch.batch_id
```

## Step 2: Add requests to the batch

With your batch created, you can now add requests to it. Each request is a standard chat completion that will be processed asynchronously.

**With the xAI SDK, adding batch requests is simple:** create `Chat` objects the same way you would for regular chat completions, then pass them as a list. You don't need to construct JSONL files or deal with complex request formats. Just use the familiar `chat.create()` and `chat.append()` pattern you already know.

**Important:** Assign a unique `batch_request_id` to each request. This ID lets you match results back to their original requests, which becomes important when you're processing hundreds or thousands of items. If you don't provide an ID, we generate a UUID for you. Using your own IDs is useful for idempotency (ensuring a request is only processed once) and for linking batch requests to records in your own system.

```pythonXAI
from xai_sdk import Client
from xai_sdk.chat import system, user

client = Client()

# Sample data to process
feedback_items = [
    {"id": "feedback_001", "text": "The product exceeded my expectations!"},
    {"id": "feedback_002", "text": "Shipping took way too long."},
    {"id": "feedback_003", "text": "It works as described, nothing special."},
]

# Build batch requests using familiar Chat objects
batch_requests = []
for item in feedback_items:
    # Create a Chat exactly like you would for a regular request
    chat = client.chat.create(
        model="grok-4-1-fast-reasoning",
        batch_request_id=item["id"],  # Add an ID to track this request
    )
    # Append messages the same way as always
    chat.append(system("Classify the sentiment as positive, negative, or neutral."))
    chat.append(user(item["text"]))
    
    batch_requests.append(chat)

# Pass the list of Chat objects to the batch
client.batch.add(batch_id=batch.batch_id, batch_requests=batch_requests)
print(f"Added {len(batch_requests)} requests to batch")
```

```bash
curl -X POST https://api.x.ai/v1/batches/{batch_id}/requests \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
    "batch_requests": [
      {
        "batch_request_id": "feedback_001",
        "batch_request": {
          "chat_get_completion": {
            "messages": [
              {"role": "system", "content": "Classify the sentiment as positive, negative, or neutral."},
              {"role": "user", "content": "The product exceeded my expectations!"}
            ],
            "model": "grok-4-1-fast-reasoning"
          }
        }
      },
      {
        "batch_request_id": "feedback_002",
        "batch_request": {
          "chat_get_completion": {
            "messages": [
              {"role": "system", "content": "Classify the sentiment as positive, negative, or neutral."},
              {"role": "user", "content": "Shipping took way too long."}
            ],
            "model": "grok-4-1-fast-reasoning"
          }
        }
      }
    ]
  }'
```

## Step 3: Monitor batch progress

After adding requests, they begin processing in the background. Since batch processing is asynchronous, you need to poll the batch status to know when results are ready.

The batch state includes counters for pending, successful, and failed requests. Poll periodically until `num_pending` reaches zero, which indicates all requests have been processed (either successfully or with errors).

```bash
# Check batch status
curl https://api.x.ai/v1/batches/{batch_id} \\
  -H "Authorization: Bearer $XAI_API_KEY"

# Response includes state with request counts:
# {
#   "state": {
#     "num_requests": 100,
#     "num_pending": 25,
#     "num_success": 70,
#     "num_error": 5
#   }
# }
```

```pythonXAI
import time
from xai_sdk import Client

client = Client()

# Poll until all requests are processed
print("Waiting for batch to complete...")
while True:
    batch = client.batch.get(batch_id=batch.batch_id)
    
    pending = batch.state.num_pending
    completed = batch.state.num_success + batch.state.num_error
    total = batch.state.num_requests
    
    print(f"Progress: {completed}/{total} complete, {pending} pending")
    
    if pending == 0:
        print("Batch processing complete!")
        break
    
    # Wait before polling again (avoid hammering the API)
    time.sleep(5)
```

### Understanding batch states

The Batch API tracks state at two levels: the **batch level** and the **individual request level**.

**Batch-level state** shows aggregate progress across all requests in a given batch,
accessible through the `batch.state` object returned by the `client.batch.get()` method:

| Counter | Description |
|---|---|
| `num_requests` | Total number of requests added to the batch |
| `num_pending` | Requests waiting to be processed |
| `num_success` | Requests that completed successfully |
| `num_error` | Requests that failed with an error |
| `num_cancelled` | Requests that were cancelled |

When `num_pending` reaches zero, all requests have been processed (either successfully, with errors, or cancelled).

**Individual request states** describe where each request is in its lifecycle, accessible through the `batch_request_metadata` object returned by the `client.batch.list_batch_requests()` [method](#check-individual-request-status):

| State | Description |
|---|---|
| `pending` | Request is queued and waiting to be processed |
| `succeeded` | Request completed successfully, result is available |
| `failed` | Request encountered an error during processing |
| `cancelled` | Request was cancelled (e.g., when the batch was cancelled before this request was processed) |

**Batch lifecycle:** A batch can also be cancelled or expire. [If you cancel a batch](#cancel-a-batch), pending requests won't be processed, but already-completed results remain available. Batches have an expiration time after which results are no longer accessible—check the `expires_at` field when retrieving batch details.

## Step 4: Retrieve results

You can retrieve results at any time, even before the entire batch completes. Results are available as soon as individual requests finish processing, so you can start consuming completed results while other requests are still in progress.

Each result is linked to its original request via the `batch_request_id` you assigned earlier. The `result.response` object is the same SDK `Response` you'd get from a regular chat completion, with all the familiar fields: `.content`, `.usage`, `.finish_reason`, and more.

The SDK provides convenient `.succeeded` and `.failed` properties to separate successful responses from errors.

**Pagination:** Results are returned in pages. Use the `limit` parameter to control page size and `pagination_token` to fetch subsequent pages. When `pagination_token` is `None`, you've reached the end.

```pythonXAI
from xai_sdk import Client

client = Client()

# Paginate through all results
all_succeeded = []
all_failed = []
pagination_token = None

while True:
    # Fetch a page of results (limit controls page size)
    page = client.batch.list_batch_results(
        batch_id=batch.batch_id,
        limit=100,
        pagination_token=pagination_token,
    )
    
    # Collect results from this page
    all_succeeded.extend(page.succeeded)
    all_failed.extend(page.failed)
    
    # Check if there are more pages
    if page.pagination_token is None:
        break
    pagination_token = page.pagination_token

# Process all results
print(f"Successfully processed: {len(all_succeeded)} requests")
for result in all_succeeded:
    # Access the full Response object
    print(f"[{result.batch_request_id}] {result.response.content}")
    print(f"  Tokens used: {result.response.usage.total_tokens}")

if all_failed:
    print(f"\\nFailed: {len(all_failed)} requests")
    for result in all_failed:
        print(f"[{result.batch_request_id}] Error: {result.error_message}")
```

```bash
# Fetch first page
curl "https://api.x.ai/v1/batches/{batch_id}/results?page_size=100" \\
  -H "Authorization: Bearer $XAI_API_KEY"

# Use pagination_token from response to fetch next page
curl "https://api.x.ai/v1/batches/{batch_id}/results?page_size=100&pagination_token={token}" \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

## Additional operations

Beyond the core workflow, the Batch API provides additional operations for managing your batches.

### Cancel a batch

You can cancel a batch before all requests complete. Already-processed requests remain available in the results, but pending requests will not be processed. You cannot add more requests to a cancelled batch.

```bash
curl -X POST https://api.x.ai/v1/batches/{batch_id}:cancel \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

```pythonXAI
from xai_sdk import Client

client = Client()

# Cancel processing
cancelled_batch = client.batch.cancel(batch_id=batch.batch_id)
print(f"Cancelled batch: {cancelled_batch.batch_id}")
print(f"Completed before cancellation: {cancelled_batch.state.num_success} requests")
```

### List all batches

View all batches belonging to your team. Batches are retained until they expire (check the `expires_at` field). This endpoint supports the same `limit` and `pagination_token` parameters for paginating through large lists.

```bash
curl "https://api.x.ai/v1/batches?page_size=20" \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

```pythonXAI
from xai_sdk import Client

client = Client()

# List recent batches
response = client.batch.list(limit=20)

for batch in response.batches:
    status = "complete" if batch.state.num_pending == 0 else "processing"
    print(f"{batch.name} ({batch.batch_id}): {status}")
```

### Check individual request status

For detailed tracking, you can inspect the metadata for each request in a batch. This shows the status, timing, and other details for individual requests. This endpoint supports the same `limit` and `pagination_token` parameters for paginating through large batches.

```bash
curl "https://api.x.ai/v1/batches/{batch_id}/requests?page_size=50" \\
  -H "Authorization: Bearer $XAI_API_KEY"
```

```pythonXAI
from xai_sdk import Client

client = Client()

# Get metadata for individual requests
metadata = client.batch.list_batch_requests(batch_id=batch.batch_id)

for request in metadata.batch_request_metadata:
    print(f"Request {request.batch_request_id}: {request.state}")
```

### Track costs

Each batch tracks the total processing cost. Access the cost breakdown after processing to understand your spending. Batch requests are billed at **50% of standard API pricing**, so you'll see significant savings compared to real-time requests.

```pythonXAI
from xai_sdk import Client

client = Client()

# Get batch with cost information
batch = client.batch.get(batch_id=batch.batch_id)

# Cost is returned in ticks (1e-10 USD) for precision
total_cost_usd = batch.cost_breakdown.total_cost_usd_ticks / 1e10
print("Total cost: $%.4f" % total_cost_usd)
```

## Complete example

This end-to-end example demonstrates a realistic batch workflow: analyzing customer feedback at scale. It creates a batch, submits feedback items for sentiment analysis, waits for processing, and outputs the results. For simplicity, this example doesn't paginate results—see [Step 4](#step-4-retrieve-results) for pagination when processing larger batches.

```pythonXAI
import time
from xai_sdk import Client
from xai_sdk.chat import system, user

client = Client()

# Sample dataset: customer feedback to analyze
feedback_data = [
    {"id": "fb_001", "text": "Absolutely love this product! Best purchase ever."},
    {"id": "fb_002", "text": "Delivery was late and the packaging was damaged."},
    {"id": "fb_003", "text": "Works fine, nothing special to report."},
    {"id": "fb_004", "text": "Customer support was incredibly helpful!"},
    {"id": "fb_005", "text": "The app keeps crashing on my phone."},
]

# Step 1: Create a batch
print("Creating batch...")
batch = client.batch.create(batch_name="feedback_sentiment_analysis")
print(f"Batch created: {batch.batch_id}")

# Step 2: Build and add requests
print("\\nAdding requests...")
batch_requests = []
for item in feedback_data:
    chat = client.chat.create(
        model="grok-4-1-fast-reasoning",
        batch_request_id=item["id"],
    )
    chat.append(system(
        "Analyze the sentiment of the customer feedback. "
        "Respond with exactly one word: positive, negative, or neutral."
    ))
    chat.append(user(item["text"]))
    batch_requests.append(chat)

client.batch.add(batch_id=batch.batch_id, batch_requests=batch_requests)
print(f"Added {len(batch_requests)} requests")

# Step 3: Wait for completion
print("\\nProcessing...")
while True:
    batch = client.batch.get(batch_id=batch.batch_id)
    pending = batch.state.num_pending
    completed = batch.state.num_success + batch.state.num_error
    
    print(f"  {completed}/{batch.state.num_requests} complete")
    
    if pending == 0:
        break
    time.sleep(2)

# Step 4: Retrieve and display results
print("\\n--- Results ---")
results = client.batch.list_batch_results(batch_id=batch.batch_id)

# Create a lookup for original feedback text
feedback_lookup = {item["id"]: item["text"] for item in feedback_data}

for result in results.succeeded:
    original_text = feedback_lookup.get(result.batch_request_id, "")
    sentiment = result.response.content.strip().lower()
    print(f"[{sentiment.upper()}] {original_text[:50]}...")

# Report any failures
if results.failed:
    print("\\n--- Errors ---")
    for result in results.failed:
        print(f"[{result.batch_request_id}] {result.error_message}")

# Display cost
cost_usd = batch.cost_breakdown.total_cost_usd_ticks / 1e10
print("\\nTotal cost: $%.4f" % cost_usd)
```

## Limitations

**Batches**

* A team can have an **unlimited** number of batches.
* Maximum batch creation rate: **1** batch creation per second per team.

**Batch Requests**

* A batch can contain an **unlimited** number of requests in theory, but extremely large batches (>1,000,000 requests) may be throttled for processing stability.
* Each individual request that can be added to a batch has a maximum payload size of **25MB**.
* A team can send up to **100** add-batch-requests API calls every **30 seconds** (this is a rolling limit shared across all batches in the team).

**Unsupported Features**

* **Agentic requests** using [server-side tools](/developers/guides/tools/overview) (such as web search, code execution, or MCP tools) are not supported in batch requests.
* **Client-side tools** (function calling) are not supported in batch requests.

## Related

* [API Reference: Batch endpoints](/developers/api-reference#batches)
* [gRPC Reference: Batch management](/developers/grpc-reference#batch-management)
* [Models and pricing](/developers/models)
* [xAI Python SDK](https://github.com/xai-org/xai-sdk-python)

===/developers/advanced-api-usage/deferred-chat-completions===
#### Advanced API Usage

# Deferred Chat Completions

Deferred Chat Completions are currently available only via REST requests or xAI SDK.

Deferred Chat Completions allow you to create a chat completion, get a `response_id`, and retrieve the response at a later time. The result would be available to be requested exactly once within 24 hours, after which it would be discarded.

Your deferred completion rate limit is the same as your chat completions rate limit. To view your rate limit, please visit [xAI Console](https://console.x.ai).

After sending the request to the xAI API, the chat completion result will be available at `https://api.x.ai/v1/chat/deferred-completion/{request_id}`. The response body will contain `{'request_id': 'f15c114e-f47d-40ca-8d5c-8c23d656eeb6'}`, and the `request_id` value can be inserted into the `deferred-completion` endpoint path. Then, we send this GET request to retrieve the deferred completion result.

When the completion result is not ready, the request will return `202 Accepted` with an empty response body.

You can access the model's raw thinking trace via the `message.reasoning_content` of the chat completion response.



## Example

A code example is provided below, where we retry retrieving the result until it has been processed:

```pythonXAI
import os
from datetime import timedelta

from xai_sdk import Client
from xai_sdk.chat import user, system

client = Client(api_key=os.getenv('XAI_API_KEY'))

chat = client.chat.create(
    model="grok-4-1-fast-reasoning",
    messages=[system("You are Zaphod Beeblebrox.")]
)
chat.append(user("126/3=?"))

# Poll the result every 10 seconds for a maximum of 10 minutes

response = chat.defer(
    timeout=timedelta(minutes=10), interval=timedelta(seconds=10)
)

# Print the result when it is ready

print(response.content)
```

```pythonRequests
import json
import os
import requests

from tenacity import retry, wait_exponential

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}"
}

payload = {
    "messages": [
        {"role": "system", "content": "You are Zaphod Beeblebrox."},
        {"role": "user", "content": "126/3=?"}
    ],
    "model": "grok-4-1-fast-reasoning",
    "deferred": True
}

response = requests.post(
    "https://api.x.ai/v1/chat/completions",
    headers=headers,
    json=payload
)
request_id = response.json()["request_id"]
print(f"Request ID: {request_id}")

@retry(wait=wait_exponential(multiplier=1, min=1, max=60),)
def get_deferred_completion():
    response = requests.get(f"https://api.x.ai/v1/chat/deferred-completion/{request_id}", headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 202:
        raise Exception("Response not ready yet")
    else:
        raise Exception(f"{response.status_code} Error: {response.text}")

completion_data = get_deferred_completion()
print(json.dumps(completion_data, indent=4))
```

```javascriptWithoutSDK
const axios = require('axios');
const retry = require('retry');

const headers = {
    'Content-Type': 'application/json',
    'Authorization': \`Bearer \${process.env.XAI_API_KEY}\`
};

const payload = {
    messages: [
        { role: 'system', content: 'You are Zaphod Beeblebrox.' },
        { role: 'user', content: '126/3=?' }
    ],
    model: 'grok-4-1-fast-reasoning',
    deferred: true
};

async function main() {
    const requestId = (await axios.post('https://api.x.ai/v1/chat/completions', payload, { headers })).data.request_id;
    console.log(\`Request ID: \${requestId}\`);

    const operation = retry.operation({
        minTimeout: 1000,
        maxTimeout: 60000,
        factor: 2
    });

    const completion = await new Promise((resolve, reject) => {
        operation.attempt(async () => {
            const res = await axios.get(\`https://api.x.ai/v1/chat/deferred-completion/\${requestId}\`, { headers });
            if (res.status === 200) resolve(res.data);
            else if (res.status === 202) operation.retry(new Error('Not ready'));
            else reject(new Error(\`\${res.status}: \${res.statusText}\`));
        });
    });

    console.log(JSON.stringify(completion, null, 4));
}

main().catch(console.error);
```

```bash
RESPONSE=$(curl -s https://api.x.ai/v1/chat/completions \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer $XAI_API_KEY" \\
-d '{
    "messages": [
        {"role": "system", "content": "You are Zaphod Beeblebrox."},
        {"role": "user", "content": "126/3=?"}
    ],
    "model": "grok-4-1-fast-reasoning",
    "deferred": true
}')

REQUEST_ID=$(echo "$RESPONSE" | jq -r '.request_id')
echo "Request ID: $REQUEST_ID"

sleep 10

curl -s https://api.x.ai/v1/chat/deferred-completion/$REQUEST_ID \\
-H "Authorization: Bearer $XAI_API_KEY"
```

The response body will be the same as what you would expect with non-deferred chat completions:

```json
{
  "id": "3f4ddfca-b997-3bd4-80d4-8112278a1508",
  "object": "chat.completion",
  "created": 1752077400,
  "model": "grok-4-1-fast-reasoning",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Whoa, hold onto your improbability drives, kid! This is Zaphod Beeblebrox here, the two-headed, three-armed ex-President of the Galaxy, and you're asking me about 126 divided by 3? Pfft, that's kid stuff for a guy who's stolen starships and outwitted the universe itself.\n\nBut get this\u2014126 slashed by 3 equals... **42**! Yeah, that's right, the Ultimate Answer to Life, the Universe, and Everything! Deep Thought didn't compute that for seven and a half million years just for fun, you know. My left head's grinning like a Vogon poet on happy pills, and my right one's already planning a party. If you need more cosmic math or a lift on the Heart of Gold, just holler. Zaphod out! \ud83d\ude80",
        "refusal": null
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 26,
    "completion_tokens": 168,
    "total_tokens": 498,
    "prompt_tokens_details": {
      "text_tokens": 26,
      "audio_tokens": 0,
      "image_tokens": 0,
      "cached_tokens": 4
    },
    "completion_tokens_details": {
      "reasoning_tokens": 304,
      "audio_tokens": 0,
      "accepted_prediction_tokens": 0,
      "rejected_prediction_tokens": 0
    },
    "num_sources_used": 0
  },
  "system_fingerprint": "fp_44e53da025"
}
```

For more details, refer to [Chat completions](/developers/api-reference#chat-completions) and [Get deferred chat completions](/developers/api-reference#get-deferred-chat-completions) in our REST API Reference.

===/developers/advanced-api-usage/fingerprint===
#### Advanced API Usage

# Fingerprint

For each request to the xAI API, the response body will include a unique `system_fingerprint` value. This fingerprint serves as an identifier for the current state of the backend system's configuration.

Example:

```bash
curl https://api.x.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
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
        "stream": false,
        "temperature": 0
      }'
```

Response:

```json
{..., "system_fingerprint":"fp_6ca29cf396"}
```

You can automate your system to keep track of the `system_fingerprint` along with token consumption and other metrics.

## Usage of fingerprint

* **Monitoring System Changes:** The system fingerprint acts as a version control for the backend configuration. If any part of the backend system—such as model parameters, server settings, or even the underlying infrastructure—changes, the fingerprint will also change. This allows developers to track when and how the system has evolved over time. This is crucial for debugging, performance optimization, and ensuring consistency in API responses.
* **Security and Integrity:** The fingerprint can be used to ensure the integrity of the response. If a response's fingerprint matches the expected one based on a recent system configuration, it helps in verifying that the data hasn't been tampered with during transmission or that the service hasn't been compromised. **The fingerprint will change over time and it is expected.**
* **Compliance and Auditing:** For regulated environments, this fingerprint can serve as part of an audit trail, showing when specific configurations were in use for compliance purposes.

===/developers/advanced-api-usage/grok-code-prompt-engineering===
#### Advanced API Usage

# Prompt Engineering for Grok Code Fast 1

## For developers using agentic coding tools

`grok-code-fast-1` is a lightweight agentic model which is designed to excel as your pair-programmer inside most common coding tools. To optimize your experience, we present a few guidelines so that you can fly through your day-to-day coding tasks.

### Provide the necessary context

Most coding tools will gather the necessary context for you on their own. However, it is oftentimes better to be specific by selecting the specific code you want to use as context. This allows `grok-code-fast-1` to focus on your task and prevent unnecessary deviations. Try to specify relevant file paths, project structures, or dependencies and avoid providing irrelevant context.

* No-context prompt to avoid
  > Make error handling better
* Good prompt with specified context
  > My error codes are defined in @errors.ts, can you use that as reference to add proper error handling and error codes to @sql.ts where I am making queries

### Set explicit goals and requirements

Clearly define your goals and the specific problem you want `grok-code-fast-1` to solve. Detailed and concrete queries can lead to better performance. Try to avoid vague or underspecified prompts, as they can result in suboptimal results.

* Vague prompt to avoid
  > Create a food tracker
* Good, detailed prompt
  > Create a food tracker which shows the breakdown of calorie consumption per day divided by different nutrients when I enter a food item. Make it such that I can see an overview as well as get high level trends.

### Continually refine your prompts

`grok-code-fast-1` is a highly efficient model, delivering up to 4x the speed and 1/10th the cost of other leading agentic models. This enables you to test your complex ideas at an unprecedented speed and affordability. Even if the initial output isn’t perfect, we strongly suggest taking advantage of the uniquely rapid and cost-effective iteration to refine your query—using the suggestions above (e.g., adding more context) or by referencing the specific failures from the first attempt.

* Good prompt example with refinement
  > The previous approach didn’t consider the IO heavy process which can block the main thread, we might want to run it in its own threadloop such that it does not block the event loop instead of just using the async lib version

### Assign agentic tasks

We encourage users to try `grok-code-fast-1` for agentic-style tasks rather than one-shot queries. Our Grok 4 models are more suited for one-shot Q\&A while `grok-code-fast-1` is your ideal companion for navigating large mountains of code with tools to deliver you precise answers.

A good way to think about this is:

* `grok-code-fast-1` is great at working quickly and tirelessly to find you the answer or implement the required change.
* Grok 4 is best for diving deep into complex concepts and tough debugging when you provide all the necessary context upfront.

## For developers building coding agents via the xAI API

With `grok-code-fast-1`, we wanted to bring an agentic coding model into the hands of developers. Outside of our launch partners, we welcome all developers to try out `grok-code-fast-1` in tool-call-heavy domains as the fast speed and low cost makes it both efficient and affordable for using many tools to figure out the correct answer.

As mentioned in the blog post, `grok-code-fast-1` is a reasoning model with interleaved tool-calling during its thinking. We also send summarized thinking via the OpenAI-compatible API for better UX support. More API details can be found at /developers/tools/function-calling.

### Reasoning content

`grok-code-fast-1` is a reasoning model, and we expose its thinking trace via `chunk.choices[0].delta.reasoning_content`. Please note that the thinking traces are only accessible when using streaming mode.

### Use native tool calling

`grok-code-fast-1` offers first-party support for native tool-calling and was specifically designed with native tool-calling in mind. We encourage you to use it instead of XML-based tool-call outputs, which may hurt performance.

### Give a detailed system prompt

Be thorough and give many details in your system prompt. A well-written system prompt which describes the task, expectations, and edge-cases the model should be aware of can make a night-and-day difference. For more inspiration, refer to the User Best Practices above.

### Introduce context to the model

`grok-code-fast-1` is accustomed to seeing a lot of context in the initial user prompt. We recommend developers to use XML tags or Markdown-formatted content to mark various sections of the context and to add clarity to certain sections. Descriptive Markdown headings/XML tags and their corresponding definitions will allow `grok-code-fast-1` to use the context more effectively.

### Optimize for cache hits

Our cache hits are a big contributor to `grok-code-fast-1`’s fast inference speed. In agentic tasks where the model uses multiple tools in sequence, most of the prefix remains the same and thus is automatically retrieved from the cache to speed up inference. We recommend against changing or augmenting the prompt history, as that could lead to cache misses and therefore significantly slower inference speeds.

===/developers/advanced-api-usage===
#### Advanced API Usage

# Advanced API Usage

Advanced guides for scaling, optimizing, and integrating xAI APIs.

## In this section

* [Batch API](/developers/advanced-api-usage/batch-api)
* [Deferred Completions](/developers/advanced-api-usage/deferred-chat-completions)
* [Fingerprint](/developers/advanced-api-usage/fingerprint)
* [Async Requests](/developers/advanced-api-usage/async)
* [Use with Code Editors](/developers/advanced-api-usage/use-with-code-editors)
* [Prompt Engineering for Grok Code](/developers/advanced-api-usage/grok-code-prompt-engineering)

===/developers/advanced-api-usage/use-with-code-editors===
# Use with Code Editors

You can use Grok with coding assistant plugins to help you code. Our Code models are specifically optimized for this task, which would provide you a smoother experience.

For pricing and limits of Code models, check out [Models and Pricing](/developers/models).

## Using Grok Code models with Cline

To use Grok with Cline, first download Cline from VSCode marketplace. Once you have installed Cline in VSCode, open Cline.

Click on "Use your own API key".

Then, you can save your xAI API key to Cline.

After setting up your xAI API key with Cline, you can set to use a coding model. Go to Cline settings -> API Configuration and you can choose `grok-code-fast-1` as the model.

## Using Grok Code models with Cursor

You can also use Grok with Cursor to help you code.

After installing Cursor, head to Cursor Settings -> Models.

Open API Keys settings, enter your xAI API key and set Override OpenAI Base URL to `https://api.x.ai/v1`

In the "Add or search model" input box, enter a coding model such as `grok-code-fast-1`. Then click on "Add Custom Model".

## Other code assistants supporting Grok Code models

Besides Cline and Cursor, you can also use our code model with [GitHub Copilot](https://github.com/features/copilot), [opencode](https://opencode.ai/), [Kilo Code](https://kilocode.ai/), [Roo Code](https://roocode.com/) and [Windsurf](https://windsurf.com/).


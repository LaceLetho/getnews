# Grok API - Collections Api

**Sections:** 4

---

## Table of Contents

- developers/collections-api/collection
- developers/collections-api
- developers/collections-api/search
- developers/files/collections/api

---

===/developers/collections-api/collection===
#### Collections API Reference

# Collection Management

The base URL for `collection` management is shared with [Management API](/developers/management-api) at `https://management-api.x.ai/`.
You have to authenticate using **xAI Management API Key** with the header `Authorization: Bearer <your xAI Management API key>`.

For more details on provisioning xAI Management API key and using Management API, you can visit

***

## POST /v1/collections

API endpoint for POST requests to /v1/collections.

```
Method: POST
Path: /v1/collections
```

***

## GET /v1/collections

API endpoint for GET requests to /v1/collections.

```
Method: GET
Path: /v1/collections
```

***

## GET /v1/collections/\{collection\_id}

API endpoint for GET requests to /v1/collections/\{collection\_id}.

```
Method: GET
Path: /v1/collections/{collection_id}
```

***

## DELETE /v1/collections/\{collection\_id}

API endpoint for DELETE requests to /v1/collections/\{collection\_id}.

```
Method: DELETE
Path: /v1/collections/{collection_id}
```

***

## PUT /v1/collections/\{collection\_id}

API endpoint for PUT requests to /v1/collections/\{collection\_id}.

```
Method: PUT
Path: /v1/collections/{collection_id}
```

***

## POST /v1/collections/\{collection\_id}/documents/\{file\_id}

API endpoint for POST requests to /v1/collections/\{collection\_id}/documents/\{file\_id}.

```
Method: POST
Path: /v1/collections/{collection_id}/documents/{file_id}
```

***

## GET /v1/collections/\{collection\_id}/documents

API endpoint for GET requests to /v1/collections/\{collection\_id}/documents.

```
Method: GET
Path: /v1/collections/{collection_id}/documents
```

***

## GET /v1/collections/\{collection\_id}/documents/\{file\_id}

API endpoint for GET requests to /v1/collections/\{collection\_id}/documents/\{file\_id}.

```
Method: GET
Path: /v1/collections/{collection_id}/documents/{file_id}
```

***

## PATCH /v1/collections/\{collection\_id}/documents/\{file\_id}

API endpoint for PATCH requests to /v1/collections/\{collection\_id}/documents/\{file\_id}.

```
Method: PATCH
Path: /v1/collections/{collection_id}/documents/{file_id}
```

***

## DELETE /v1/collections/\{collection\_id}/documents/\{file\_id}

API endpoint for DELETE requests to /v1/collections/\{collection\_id}/documents/\{file\_id}.

```
Method: DELETE
Path: /v1/collections/{collection_id}/documents/{file_id}
```

***

## GET /v1/collections/\{collection\_id}/documents:batchGet

API endpoint for GET requests to /v1/collections/\{collection\_id}/documents:batchGet.

```
Method: GET
Path: /v1/collections/{collection_id}/documents:batchGet
```

===/developers/collections-api===
# Collections API Reference

The Collections API allows you to manage your Collections `documents` and `collections` programmatically.

The base url for `collection` management is shared with [Management API](/developers/management-api) at `https://management-api.x.ai/v1/`. You have to authenticate using **xAI Management API Key** with the header `Authorization: Bearer <your xAI Management API key>`.

For more details on provisioning xAI Management API key and using Management API, you can visit

.

The base url for searching within `collections` is shared with [REST API](/developers/api-reference) at `https://api.x.ai`. You have to authenticate using **xAI API Key** with the header `Authorization: Bearer <your xAI API key>`.

===/developers/collections-api/search===
#### Collections API Reference

# Search in Collections

The base url for searching `collections` is shared with [REST API](/developers/api-reference) at `https://api.x.ai`. You have to authenticate using **xAI API Key** with the header `Authorization: Bearer <your xAI API key>`.

***

## POST /v1/documents/search

API endpoint for POST requests to /v1/documents/search.

```
Method: POST
Path: /v1/documents/search
```

===/developers/files/collections/api===
#### Files & Collections

# Using Collections via API

This guide walks you through managing collections programmatically using the xAI SDK and REST API.

## Creating a Management Key

To use the Collections API, you need to create a Management API Key with the `AddFileToCollection` permission. This permission is required for uploading documents to collections.

1. Navigate to the **Management Keys** section in the [xAI Console](https://console.x.ai)
2. Click on **Create Management Key**
3. Select the `AddFileToCollection` permission along with any other permissions you need
4. If you need to perform operations other than uploading documents (such as creating, updating, or deleting collections), enable the corresponding permissions in the **Collections Endpoint** group
5. Copy and securely store your Management API Key

Make sure to copy your Management API Key immediately after creation. You won't be able to see it again.

## Creating a collection

## Listing collections

## Viewing collection configuration

## Updating collection configuration

## Uploading documents

Uploading a document to a collection is a two-step process:

1. Upload the file to the xAI API
2. Add the uploaded file to your collection

### Uploading with metadata fields

If your collection has [metadata fields](/developers/files/collections/metadata) defined, include them using the `fields` parameter:

## Searching documents

You can also search documents using the Responses API with the `file_search` tool. See the [Collections Search Tool](/developers/tools/collections-search) guide for more details.

### Search modes

There are three search methods available:

* **Keyword search**
* **Semantic search**
* **Hybrid search** (combines both keyword and semantic methods)

By default, the system uses hybrid search, which generally delivers the best and most comprehensive results.

| Mode | Description | Best for | Drawbacks |
|------|-------------|----------|-----------|
| Keyword | Searches for exact matches of specified words, phrases, or numbers | Precise terms (e.g., account numbers, dates, specific financial figures) | May miss contextually relevant content |
| Semantic | Understands meaning and context to find conceptually related content | Discovering general ideas, topics, or intent even when exact words differ | Less precise for specific terms |
| Hybrid | Combines keyword and semantic search for broader and more accurate results | Most real-world use cases | Slightly higher latency |

The hybrid approach balances precision and recall, making it the recommended default for the majority of queries.

An example to set hybrid mode:

You can set `"retrieval_mode": {"type": "keyword"}` for keyword search and `"retrieval_mode": {"type": "semantic"}` for semantic search.

## Deleting a document

## Deleting a collection

## Next Steps

[Metadata Fields →](/developers/files/collections/metadata) - Learn how to attach structured attributes to documents for filtering and contextual embeddings


# Grok API - Management Api

**Sections:** 5

---

## Table of Contents

- developers/management-api-guide
- developers/management-api/audit
- developers/management-api/auth
- developers/management-api/billing
- developers/management-api

---

===/developers/management-api-guide===
#### Key Information

# Using Management API

Some enterprise users may prefer to manage their account details programmatically rather than manually through the xAI Console. For this reason, we have developed a Management API to enable enterprise users to efficiently manage their team details.

You can read the endpoint specifications and descriptions at [Management API Reference](/developers/management-api).

You need to get a management key, which is separate from your API key, to use the management API. The management key can be obtained at [xAI Console](https://console.x.ai) -> Settings -> Management Keys.

The base URL is at `https://management-api.x.ai`, which is also different from the inference API.

## Operations related to API Keys

You can create, list, update, and delete API keys via the management API.

You can also manage the access control lists (ACLs) associated with the API keys.

The available ACL types are:

* `api-key:model`
* `api-key:endpoint`

To enable all models and endpoints available to your team, use:

* `api-key:model:*`
* `api-key:endpoint:*`

Or if you need to specify the particular endpoint available to the API:

* `api-key:endpoint:chat` for chat and vision models
* `api-key:endpoint:image` for image generation models

And to specify models the API key has access to:

* `api-key:model:<model name such as grok-4-1-fast-reasoning>`

### Create an API key

An example to create an API key with all models and endpoints enabled, limiting requests to 5 queries per second and 100 queries per minute, without token number restrictions.

```bash
curl https://management-api.x.ai/auth/teams/{teamId}/api-keys \\
    -X POST \\
    -H "Authorization: Bearer <Your Management API Key>" \\
    -d '{
            "name": "My API key",
            "acls": ["api-key:model:*", "api-key:endpoint:*"],
            "qps": 5,
            "qpm": 100,
            "tpm": null
        }'
```

Specify `tpm` to any integer string to limit the number of tokens produced/consumed per minute. When the token rate limit is triggered, new requests will be rejected and in-flight requests will continue processing.

The newly-created API key will be returned in the `"apiKey"` field of the response object. The API Key ID is returned as `"apiKeyId"` in the response body as well, which is useful for updating and deleting operations.

### List API keys

To retrieve a list of API keys from a team, you can run the following:

```bash
curl https://management-api.x.ai/auth/teams/{teamId}/api-keys?pageSize=10&paginationToken= \\
    -H "Authorization: Bearer <Your Management API Key>"
```

You can customize the query parameters such as `pageSize` and `paginationToken`.

### Update an API key

You can update an API key after it has been created. For example, to update the `qpm` of an API key:

```bash
curl https://management-api.x.ai/auth/teams/{teamId}/api-keys \\
    -X PUT \\
    -d '{
            "apiKey": "<The apiKey Object with updated qpm>",
            "fieldMask": "qpm",
        }'
```

Or to update the `name` of an API key:

```bash
curl https://management-api.x.ai/auth/teams/{teamId}/api-keys \\
    -X PUT \\
    -d '{
            "apiKey": "<The apiKey Object with updated name>",
            "fieldMask": "name",
        }'
```

### Delete an API key

You can also delete an API key with the following:

```bash
curl https://management-api.x.ai/auth/api-keys/{apiKeyId} \\
    -X DELETE \\
    -H "Authorization: Bearer <Your Management API Key>"
```

### Check propagation status of API key across clusters

There could be a slight delay between creating an API key, and the API key being available for use across all clusters.

You can check the propagation status of the API key via API.

```bash
curl https://management-api.x.ai/auth/api-keys/{apiKeyId}/propagation \\
    -H "Authorization: Bearer <Your Management API Key>"
```

### List all models available for the team

You can list all the available models for a team with our management API as well.

The model names in the output can be used with setting ACL string on an API key as `api-key:model:<model-name>`

```bash
curl https://management-api.x.ai/auth/teams/{teamId}/models \\
    -H "Authorization: Bearer <Your Management API Key>"
```

## Access Control List (ACL) management

We also offer endpoint to list possible ACLs for a team. You can then apply the endpoint ACL strings to your API keys.

To view possible endpoint ACLs for a team's API keys:

```bash
curl https://management-api.x.ai/auth/teams/{teamId}/endpoints \\
    -H "Authorization: Bearer <Your Management API Key>"
```

## Validate a management key

You can check if your key is a valid management key. If validation succeeds, the endpoint returns meta information about the management key.
This endpoint does not require any Access Control List (ACL) permissions.

```bash
curl https://management-api.x.ai/auth/management-keys/validation \\
    -H "Authorization: Bearer <Your Management API Key>"
```

## Audit Logs

You can retrieve audit logs for your team. Audit events track changes to team settings, API keys, team membership, and other administrative actions.

### List audit events

To retrieve audit events for a team:

```bash
curl "https://management-api.x.ai/audit/teams/{teamId}/events?pageSize=10" \\
    -H "Authorization: Bearer <Your Management API Key>"
```

You can customize the query parameters:

* `pageSize` - Number of events per page
* `pageToken` - Token for fetching the next page of results
* `eventFilter.userId` - Filter events to a specific user
* `eventFilter.query` - Full-text search in event descriptions
* `eventTimeFrom` - Filter events from a specific time (ISO 8601 format)
* `eventTimeTo` - Filter events up to a specific time (ISO 8601 format)

To fetch the next page of results, use the `nextPageToken` from the response:

```bash
curl "https://management-api.x.ai/audit/teams/{teamId}/events?pageSize=10&pageToken={nextPageToken}" \\
    -H "Authorization: Bearer <Your Management API Key>"
```

Example with time filter:

```bash
curl "https://management-api.x.ai/audit/teams/{teamId}/events?pageSize=50&eventTimeFrom=2025-01-01T00:00:00Z" \\
    -H "Authorization: Bearer <Your Management API Key>"
```

===/developers/management-api/audit===
## Audit Logs

## GET /audit/teams/\{teamId}/events

API endpoint for GET requests to /audit/teams/\{teamId}/events.

```
Method: GET
Path: /audit/teams/{teamId}/events
```

===/developers/management-api/auth===
## Accounts and Authorization

## POST /auth/teams/\{teamId}/api-keys

API endpoint for POST requests to /auth/teams/\{teamId}/api-keys.

```
Method: POST
Path: /auth/teams/{teamId}/api-keys
```

***

## GET /auth/teams/\{teamId}/api-keys

API endpoint for GET requests to /auth/teams/\{teamId}/api-keys.

```
Method: GET
Path: /auth/teams/{teamId}/api-keys
```

***

## PUT /auth/api-keys/\{api\_key\_id}

API endpoint for PUT requests to /auth/api-keys/\{api\_key\_id}.

```
Method: PUT
Path: /auth/api-keys/{api_key_id}
```

***

## DELETE /auth/api-keys/\{apiKeyId}

API endpoint for DELETE requests to /auth/api-keys/\{apiKeyId}.

```
Method: DELETE
Path: /auth/api-keys/{apiKeyId}
```

***

## GET /auth/api-keys/\{apiKeyId}/propagation

API endpoint for GET requests to /auth/api-keys/\{apiKeyId}/propagation.

```
Method: GET
Path: /auth/api-keys/{apiKeyId}/propagation
```

***

## GET /auth/teams/\{teamId}/models

API endpoint for GET requests to /auth/teams/\{teamId}/models.

```
Method: GET
Path: /auth/teams/{teamId}/models
```

***

## GET /auth/teams/\{teamId}/endpoints

API endpoint for GET requests to /auth/teams/\{teamId}/endpoints.

```
Method: GET
Path: /auth/teams/{teamId}/endpoints
```

***

## GET /auth/management-keys/validation

API endpoint for GET requests to /auth/management-keys/validation.

```
Method: GET
Path: /auth/management-keys/validation
```

===/developers/management-api/billing===
## Billing Management

## GET /v1/billing/teams/\{team\_id}/billing-info

API endpoint for GET requests to /v1/billing/teams/\{team\_id}/billing-info.

```
Method: GET
Path: /v1/billing/teams/{team_id}/billing-info
```

***

## POST /v1/billing/teams/\{team\_id}/billing-info

API endpoint for POST requests to /v1/billing/teams/\{team\_id}/billing-info.

```
Method: POST
Path: /v1/billing/teams/{team_id}/billing-info
```

***

## GET /v1/billing/teams/\{team\_id}/invoices

API endpoint for GET requests to /v1/billing/teams/\{team\_id}/invoices.

```
Method: GET
Path: /v1/billing/teams/{team_id}/invoices
```

***

## GET /v1/billing/teams/\{team\_id}/payment-method

API endpoint for GET requests to /v1/billing/teams/\{team\_id}/payment-method.

```
Method: GET
Path: /v1/billing/teams/{team_id}/payment-method
```

***

## POST /v1/billing/teams/\{team\_id}/payment-method/default

API endpoint for POST requests to /v1/billing/teams/\{team\_id}/payment-method/default.

```
Method: POST
Path: /v1/billing/teams/{team_id}/payment-method/default
```

***

## GET /v1/billing/teams/\{team\_id}/postpaid/invoice/preview

API endpoint for GET requests to /v1/billing/teams/\{team\_id}/postpaid/invoice/preview.

```
Method: GET
Path: /v1/billing/teams/{team_id}/postpaid/invoice/preview
```

***

## GET /v1/billing/teams/\{team\_id}/postpaid/spending-limits

API endpoint for GET requests to /v1/billing/teams/\{team\_id}/postpaid/spending-limits.

```
Method: GET
Path: /v1/billing/teams/{team_id}/postpaid/spending-limits
```

***

## POST /v1/billing/teams/\{team\_id}/postpaid/spending-limits

API endpoint for POST requests to /v1/billing/teams/\{team\_id}/postpaid/spending-limits.

```
Method: POST
Path: /v1/billing/teams/{team_id}/postpaid/spending-limits
```

***

## GET /v1/billing/teams/\{team\_id}/prepaid/balance

API endpoint for GET requests to /v1/billing/teams/\{team\_id}/prepaid/balance.

```
Method: GET
Path: /v1/billing/teams/{team_id}/prepaid/balance
```

***

## POST /v1/billing/teams/\{team\_id}/prepaid/top-up

API endpoint for POST requests to /v1/billing/teams/\{team\_id}/prepaid/top-up.

```
Method: POST
Path: /v1/billing/teams/{team_id}/prepaid/top-up
```

***

## POST /v1/billing/teams/\{team\_id}/usage

API endpoint for POST requests to /v1/billing/teams/\{team\_id}/usage.

```
Method: POST
Path: /v1/billing/teams/{team_id}/usage
```

===/developers/management-api===
## Overview

The Management API serves as a dedicated interface to the xAI platform, empowering developers and teams to
programmatically manage their xAI API teams.

For example, users can provision their API key, handle access controls,
and perform team-level operations like creating, listing, updating, or deleting keys and associated access control lists
(ACLs). This API also facilitates oversight of billing aspects, including monitoring prepaid credit balances and usage
deductions, ensuring seamless scalability and cost transparency for Grok model integrations.

To get started, go to [xAI Console](https://console.x.ai). On users page, make sure your xAI account has
`Management Keys` Read + Write permission, and obtain your Management API key on the settings page. If you don't see
any of these options, please ask your team administrator to enable the appropriate permissions.


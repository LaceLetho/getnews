---
name: crypto-news-debug
description: Inspect Railway split deployments with RAILWAY_API_TOKEN, including safe app-service restart/redeploy workflows and read-only GraphQL debugging templates.
---

# Crypto News Railway Debug Skill

Use this skill when you need to inspect this project's Railway split deployment, or perform narrowly scoped app-service restart/redeploy actions, without the Railway CLI.

## What this skill covers

- Read-only inspection of Railway projects, environments, services, deployments, and logs.
- Repo-specific alias mapping for `crypto-news-analysis`, `crypto-news-ingestion`, and legacy `crypto-news-api`.
- Explicitly scoped `restart` and `redeploy` workflows for app services only.
- Read-only GraphQL fallback templates for cases where the preset workflows are not enough.

## Auth Preflight

If `RAILWAY_API_TOKEN` is missing, stop immediately and ask the user to export or provide it before doing anything else.

- Endpoint: `https://backboard.railway.com/graphql/v2`
- Header: `Authorization: Bearer $RAILWAY_API_TOKEN`
- Content type: `Content-Type: application/json`
- Default assumption for this skill: use Bearer-token workflows only.

Minimal connectivity check:

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"query":"query { projects { edges { node { id name } } } }"}'
```

## Target Resolution

Always resolve targets in this order: `project → environment → service → deployment`.

1. Resolve the Railway project ID.
2. Resolve the environment ID inside that project.
3. Resolve the service ID inside that environment.
4. Resolve the deployment ID for the target service.

Do not guess IDs from names. If multiple candidates match, stop and present the candidates instead of guessing.

### Resolve projects

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query { projects { edges { node { id name description updatedAt } } } }"
  }'
```

### Resolve environments for a project

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query environments($projectId: String!) { environments(projectId: $projectId) { edges { node { id name createdAt } } } }",
    "variables":{"projectId":"<PROJECT_ID>"}
  }'
```

### Resolve services for a project

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query project($id: String!) { project(id: $id) { id name services { edges { node { id name icon } } } environments { edges { node { id name } } } } }",
    "variables":{"id":"<PROJECT_ID>"}
  }'
```

### Resolve the latest deployment for a service

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query latestDeployment($input: DeploymentListInput!) { deployments(input: $input, first: 1) { edges { node { id status createdAt url staticUrl } } } }",
    "variables":{
      "input":{
        "projectId":"<PROJECT_ID>",
        "environmentId":"<ENVIRONMENT_ID>",
        "serviceId":"<SERVICE_ID>",
        "status":{"successfulOnly":true}
      }
    }
  }'
```

## Service Aliases

Use repo-specific naming context when matching services:

- `crypto-news-analysis` maps to runtime mode `analysis-service`
- `crypto-news-ingestion` maps to runtime mode `ingestion`
- `crypto-news-api` is a legacy alias that should be treated like `analysis-service`

When investigating split deployment behavior, remember that `crypto-news-analysis` is the public app service and `crypto-news-ingestion` is the private ingestion service.

## Read-Only Workflows

### Inspect a service instance

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query serviceInstance($serviceId: String!, $environmentId: String!) { serviceInstance(serviceId: $serviceId, environmentId: $environmentId) { id serviceName startCommand buildCommand rootDirectory healthcheckPath region numReplicas restartPolicyType restartPolicyMaxRetries latestDeployment { id status createdAt } } }",
    "variables":{"serviceId":"<SERVICE_ID>","environmentId":"<ENVIRONMENT_ID>"}
  }'
```

### List recent deployments

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query deployments($input: DeploymentListInput!, $first: Int) { deployments(input: $input, first: $first) { edges { node { id status createdAt url staticUrl } } } }",
    "variables":{
      "input":{
        "projectId":"<PROJECT_ID>",
        "environmentId":"<ENVIRONMENT_ID>",
        "serviceId":"<SERVICE_ID>"
      },
      "first":10
    }
  }'
```

### Fetch build logs

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query buildLogs($deploymentId: String!, $limit: Int) { buildLogs(deploymentId: $deploymentId, limit: $limit) { timestamp message severity } }",
    "variables":{"deploymentId":"<DEPLOYMENT_ID>","limit":200}
  }'
```

### Fetch runtime logs

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query deploymentLogs($deploymentId: String!, $limit: Int) { deploymentLogs(deploymentId: $deploymentId, limit: $limit) { timestamp message severity } }",
    "variables":{"deploymentId":"<DEPLOYMENT_ID>","limit":200}
  }'
```

### Fetch HTTP logs

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"query httpLogs($deploymentId: String!, $limit: Int) { httpLogs(deploymentId: $deploymentId, limit: $limit) { timestamp requestId method path httpStatus totalDuration srcIp } }",
    "variables":{"deploymentId":"<DEPLOYMENT_ID>","limit":100}
  }'
```

## Operational Actions

Only run restart or redeploy after resolving the exact project, environment, and service IDs.

- Require explicit user intent before any mutation.
- Confirm the target is an app service, not PostgreSQL or another managed database service.
- Resolve the latest successful deployment before invoking a mutation.
- After every mutation, re-check deployment state and logs.

### Restart a running app deployment

Use this only for resolved app services.

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"mutation deploymentRestart($id: String!) { deploymentRestart(id: $id) }",
    "variables":{"id":"<DEPLOYMENT_ID>"}
  }'
```

### Redeploy the latest app deployment

Use this only for resolved app services.

```bash
curl --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "query":"mutation deploymentRedeploy($id: String!) { deploymentRedeploy(id: $id) { id status } }",
    "variables":{"id":"<DEPLOYMENT_ID>"}
  }'
```

Post-action verification checklist:

1. Re-run the latest deployment query.
2. Fetch runtime logs or build logs for the returned deployment.
3. Confirm the deployment moved into a healthy status instead of trusting the mutation response alone.

## Database Safety

PostgreSQL and other managed database services are inspection-only in v1.

- Treat database services as inspection-only even if they appear in the same project.
- do not restart or redeploy database services in v1.
- Limit database work to discovery, configuration inspection, deployment history inspection, and log inspection.

## Raw Read-Only GraphQL Fallback Templates

Use these only when the preset workflows above do not cover the exact read-only question.

### Projects

```graphql
query {
  projects {
    edges {
      node {
        id
        name
        description
        updatedAt
      }
    }
  }
}
```

### Project with services and environments

```graphql
query project($id: String!) {
  project(id: $id) {
    id
    name
    services {
      edges {
        node {
          id
          name
          icon
        }
      }
    }
    environments {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
```

### Deployments

```graphql
query deployments($input: DeploymentListInput!, $first: Int) {
  deployments(input: $input, first: $first) {
    edges {
      node {
        id
        status
        createdAt
        url
        staticUrl
      }
    }
  }
}
```

### Logs

```graphql
query deploymentLogs($deploymentId: String!, $limit: Int) {
  deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
    timestamp
    message
    severity
  }
}
```

## Failure Handling

Treat HTTP 200 responses with a non-empty `errors` array as failures.

When you need to inspect rate-limit headers directly, use `curl --include` so the response headers are preserved:

```bash
curl --include --request POST \
  --url https://backboard.railway.com/graphql/v2 \
  --header "Authorization: Bearer $RAILWAY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"query":"query { projects { edges { node { id name } } } }"}'
```

- If no service matches, stop and report that no candidates were found.
- If multiple services match, stop and list the candidates.
- If logs are empty, report that the log query returned no entries.
- If a field returns `null`, treat that as unresolved state and keep the result read-only until you know why.
- Check `X-RateLimit-Remaining` and `X-RateLimit-Reset` on responses.
- If Railway sends `Retry-After`, wait for that duration and back off before sending another request.

## Non-Goals

This v1 skill must not guide any of the following:

- rollback
- stop service
- cancel deployment
- delete service
- remove service
- update variables
- create domain
- create volume
- database restart
- database redeploy
- arbitrary write mutations beyond the explicit app-service restart/redeploy workflows above

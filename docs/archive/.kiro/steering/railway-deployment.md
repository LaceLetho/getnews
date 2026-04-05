---
inclusion: auto
description: Railway deployment environment and troubleshooting guidance
---

# Railway Deployment

## Deployment Platform

This project is deployed on Railway using Docker containerization. The deployment configuration is defined in:
- `Dockerfile` - Container build instructions
- `railway.toml` - Railway-specific configuration

## When Users Ask About Production Issues

When users mention production problems, online issues, or deployment-related questions, you should:

1. **Activate the Railway skill** to access Railway-specific tools
2. **Check deployment logs** to investigate issues
3. **Review service status** and recent deployments
4. **Examine environment variables** if configuration-related

## Common Production Scenarios

- "线上出问题了" / "Production is broken" → Check Railway logs
- "部署失败" / "Deployment failed" → Review build logs
- "服务挂了" / "Service is down" → Check service status
- "环境变量配置" / "Environment config" → Review Railway environment settings

## Railway Tools Available

Use the `railway-docs` skill to access:
- Deployment logs and monitoring
- Service configuration
- Environment variable management
- Build and runtime diagnostics

## Key Railway Concepts

- **Service**: The deployed application instance
- **Environment**: Production, staging, or development
- **Logs**: Real-time application output and errors
- **Deployments**: Build and deployment history
- **Variables**: Environment-specific configuration

## Troubleshooting Workflow

1. Activate railway-docs skill
2. Fetch recent logs to identify errors
3. Check deployment status and history
4. Verify environment variables match requirements
5. Review Dockerfile and railway.toml for misconfigurations

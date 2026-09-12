# Initial architecture

Article 50 AutoDisclosure is split into independently runnable frontend and backend applications.

```text
Browser (React)
    │ GET /api/health
    ▼
FastAPI application
    ├── api       HTTP routes and schemas
    ├── core      configuration and cross-cutting concerns
    ├── models    workflow domain models
    ├── services  future application orchestration
    ├── agents    future Strands agent definitions
    └── tools     future agent tools
```

Only the health path is active in this ticket. The empty backend packages mark intended extension points without introducing placeholder behavior. Future AWS integrations will read region and model configuration from settings and credentials from the standard AWS credential chain.


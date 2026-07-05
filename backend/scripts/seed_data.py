"""Sample meeting transcripts for seeding — metadata only, no pre-built entities."""

from datetime import datetime, timezone

SAMPLE_MEETINGS = [
    {
        "title": "Authentication Architecture Review",
        "date": datetime(2025, 11, 15, 14, 0, tzinfo=timezone.utc),
        "content": """Sarah: Let's kick off the auth architecture review. We've been using JWT tokens for 18 months and we're hitting some issues.

Mike: The main problem is token revocation. With JWTs, we can't invalidate a session without rotating the secret, which kills all sessions.

Sarah: Right. I've been looking at OAuth 2.0 with refresh tokens. We'd use short-lived access tokens (15 min) and longer refresh tokens stored server-side.

Alex: Decision: we will migrate from JWT to OAuth 2.0. The security team has been pushing for this anyway.

Mike: Action item: Mike to create a migration plan for the auth system by next sprint. Risk: we need to handle backwards compatibility for mobile apps still on v1.

Sarah: Blocker: we're waiting on the security audit results before we finalize the approach.

Alex: We agreed to use Keycloak as the identity provider. It's open source and supports all the protocols we need.

Mike: Decision: we decided to use Keycloak for identity management. Assigned to Alex.

Sarah: Timeline: migration should be complete by Q1. We'll run both systems in parallel during the transition.""",
        "content_type": "transcript",
        "duration_minutes": 60,
        "tags": ["authentication", "architecture", "security"],
    },
    {
        "title": "Database Migration Planning — PostgreSQL to Distributed",
        "date": datetime(2025, 11, 22, 10, 0, tzinfo=timezone.utc),
        "content": """Emma: We've been hitting read performance limits on our PostgreSQL setup. Peak load is causing 2-3 second query times.

David: I've done some analysis. The bottleneck is the reporting queries — they're locking the main write path.

Emma: Decision: we decided to introduce read replicas first before considering a full distributed migration. This is less risky.

David: Action item: David to set up PostgreSQL streaming replication by end of month.

Chris: Risk: replication lag could cause stale reads in the dashboard. We need to implement read-your-writes consistency.

Emma: Blocker: the DevOps team is blocked on provisioning the replica servers — waiting on cloud budget approval.

David: We also decided to migrate the reporting queries to a separate analytics service. This will use the replica.

Decision: going with PostgreSQL read replicas + separate analytics service. We're not doing Cassandra or distributed SQL yet.

Chris: Action item: Chris to evaluate TimescaleDB for time-series data from the monitoring system.

Emma: We need to document the connection routing logic. Writes go to primary, reads can use replicas.""",
        "content_type": "transcript",
        "duration_minutes": 75,
        "tags": ["database", "scalability", "postgresql", "infrastructure"],
    },
    {
        "title": "API Gateway Strategy Session",
        "date": datetime(2025, 12, 3, 15, 30, tzinfo=timezone.utc),
        "content": """Rachel: We're evaluating API gateway options. Current setup is nginx with manual config — it's becoming unmanageable at 40+ services.

Tom: I've been evaluating Kong, AWS API Gateway, and Traefik. My recommendation is Kong Community Edition.

Rachel: Decision: we agreed to adopt Kong as our API gateway. It gives us rate limiting, auth plugins, and observability out of the box.

Tom: Action item: Tom to deploy Kong in staging by December 15th.

Rachel: We also decided to standardize all internal services on gRPC, with REST exposed only at the gateway level.

Decision: going with gRPC internally, REST at the API gateway. This will improve inter-service performance.

Jake: Risk: some teams are on language stacks without good gRPC support — Ruby service might be a problem.

Rachel: Blocker: API documentation is inconsistent — we need OpenAPI specs for all services before Kong can auto-generate docs.

Tom: Action item: all team leads to provide OpenAPI specs for their services by December 20th.

Rachel: We'll have a follow-up on the gRPC migration approach for legacy services next week.""",
        "content_type": "transcript",
        "duration_minutes": 90,
        "tags": ["api", "gateway", "grpc", "architecture"],
    },
    {
        "title": "Security Incident Review — Auth Token Exposure",
        "date": datetime(2025, 12, 10, 9, 0, tzinfo=timezone.utc),
        "content": """Sarah: We had an incident last Tuesday — auth tokens were being logged in plaintext in our application logs.

Mike: Root cause analysis: the request interceptor was logging the full Authorization header. About 40,000 tokens were exposed in the Datadog logs.

Sarah: This actually validates our decision to migrate to OAuth 2.0. Short-lived tokens mean the exposed tokens are now all expired.

Alex: Decision: we're updating the auth migration to OAuth 2.0 instead of our previous JWT plan — this incident accelerates the timeline. Priority: critical.

Mike: The JWT migration we discussed last month is now superseded by this — we need to move faster.

Sarah: Action item: Mike to patch the logging interceptor immediately. Action item: rotate all long-lived tokens by end of day.

Alex: Risk: if any service is caching the old tokens, rotation could break sessions. Need to coordinate with all service teams.

Mike: Decision: we decided to revoke ALL active sessions as a precaution. Users will need to re-authenticate.

Sarah: The incident also revealed we need to audit all our logging configurations. Blocker: we don't have a complete inventory of what gets logged where.

Alex: Action item: security team to perform full logging audit by Dec 20th.""",
        "content_type": "transcript",
        "duration_minutes": 120,
        "tags": ["security", "incident", "authentication", "oauth"],
    },
    {
        "title": "Q1 2026 Roadmap Planning",
        "date": datetime(2025, 12, 18, 13, 0, tzinfo=timezone.utc),
        "content": """Emma: Let's plan Q1. We have three major initiatives: auth migration completion, database scaling, and the new developer portal.

Rachel: The Kong API gateway deployment should be done by end of January. Then we start the gRPC migration in February.

David: Database: read replicas go live end of December. Q1 focus is on the analytics service extraction.

Sarah: Auth: OAuth/Keycloak goes live for internal tools in January, public APIs in March.

Emma: Decision: Q1 priorities are (1) auth migration, (2) API gateway rollout, (3) analytics service. The developer portal moves to Q2.

Tom: Action item: each team lead to create detailed Q1 milestones by Jan 5th.

Rachel: Risk: auth migration and API gateway are both in January — resource overlap could be a problem.

Emma: We agreed to staff up with two contractors for January specifically to cover the overlap.

David: Decision: we're going to hire two contractors for January to cover peak Q1 workload. Emma to post the positions.

Jake: Blocker: we need architecture sign-off on the analytics service design before February start date.

Emma: Action item: architecture review for analytics service scheduled for Jan 15th.""",
        "content_type": "transcript",
        "duration_minutes": 90,
        "tags": ["roadmap", "planning", "q1-2026"],
    },
    {
        "title": "OAuth 2.0 Implementation Update",
        "date": datetime(2026, 1, 8, 11, 0, tzinfo=timezone.utc),
        "content": """Alex: Quick update on the OAuth migration. Keycloak is running in staging. The React frontend auth flow works end-to-end.

Mike: We hit an issue with the mobile apps. The iOS client was using the Authorization Code flow without PKCE — security requirement violation.

Sarah: Decision: we decided to enforce PKCE for all OAuth clients — mobile and web. No exceptions.

Alex: This updates our auth architecture from what we decided in November. We're now requiring PKCE everywhere.

Mike: Action item: update iOS and Android apps to use PKCE by Jan 20th. Ryan to lead mobile updates.

Sarah: The token refresh logic is working. 15-minute access tokens, 24-hour refresh tokens stored in httpOnly cookies.

Alex: Decision: going with httpOnly cookies for refresh tokens instead of localStorage — more secure against XSS.

Mike: We also discovered that three legacy backend services were using the old JWT validation library that we're deprecating.

Sarah: Action item: identify all services using the deprecated JWT library and migrate them. Deadline: Jan 31st.

Alex: The Keycloak admin panel gives us real-time session management. We can now revoke sessions per-user without killing everyone.

Mike: This resolves the core problem from the November architecture review. Token revocation now works properly.""",
        "content_type": "transcript",
        "duration_minutes": 60,
        "tags": ["oauth", "authentication", "keycloak", "mobile", "security"],
    },
]

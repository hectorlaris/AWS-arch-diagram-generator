flowchart LR
    %% Triggers
    EB1[("⏰ EventBridge Scheduler<br/>cron: 0 6 * * ? *<br/>(Daily 6 AM)")]
    EB2[("⏰ EventBridge Rule<br/>rate: 15 minutes")]

    %% Lambdas
    SL["SummaryLambda<br/>Python 3.12 | 60s timeout"]
    ML["MonitorLambda<br/>Python 3.12 | 300s timeout"]

    %% AWS Services
    S3[("📦 S3 State Store<br/>Versioned + SSE-S3")]
    Bedrock["🤖 Amazon Bedrock<br/>Nova Lite v2"]
    SES["📧 Amazon SES<br/>Email Delivery"]
    SM["🔐 Secrets Manager<br/>GitHub Tokens"]
    CW["📊 CloudWatch Logs<br/>Structured JSON"]

    %% External
    GH["🐙 GitHub REST API<br/>Commits, Issues, PRs"]
    Email["Gmail / IMAP<br/>Unread Messages"]
    User["👤 Self-Employed Professional<br/>hector.serrano@colombiatechsas.com"]

    %% Trigger connections
    EB1 -->|"Invokes daily"| SL
    EB2 -->|"Invokes every 15 min"| ML

    %% SummaryLambda flow
    SL -->|"1. Read context"| S3
    SL -->|"2. Generate summary"| Bedrock
    SL -->|"3. Store output"| S3
    SL -->|"4. Send briefing"| SES
    SL -->|"Logs"| CW

    %% MonitorLambda flow
    ML -->|"1. Get credentials"| SM
    ML -->|"2a. Fetch state"| GH
    ML -->|"2b. Fetch state"| Email
    ML -->|"3. Read/Write snapshots"| S3
    ML -->|"4. Score relevance"| Bedrock
    ML -->|"5. Store report"| S3
    ML -->|"6. Alert if relevant"| SES
    ML -->|"Logs"| CW

    %% Email delivery
    SES -->|"Morning Summary"| User
    SES -->|"Change Alert"| User

    %% Styling
    classDef trigger fill:#ff9900,stroke:#232f3e,color:#fff
    classDef lambda fill:#4051b5,stroke:#232f3e,color:#fff
    classDef aws fill:#232f3e,stroke:#ff9900,color:#fff
    classDef external fill:#1a7f37,stroke:#232f3e,color:#fff
    classDef user fill:#0969da,stroke:#232f3e,color:#fff

    class EB1,EB2 trigger
    class SL,ML lambda
    class S3,Bedrock,SES,SM,CW aws
    class GH,Email external
    class User user
    
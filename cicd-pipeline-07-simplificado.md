flowchart TB
    %% ============================================================
    %% REPO 1 + SOLUTION LAYER: CI/CD Pipeline (bootstrap)
    %% Own state: pipeline-cicd/terraform.tfstate
    %% ============================================================
    subgraph SOLUTION["SOLUTION INFRASTRUCTURE — CI/CD Pipeline"]
        direction TB

        GH_PIPE["GitHub Repo: pipeline-cicd<br/>"]
        CSC["CodeStar Connection (GitHub)"]

        subgraph ORCH["Orchestration"]
            CP["AWS CodePipeline<br/>Source → Plan → Approval → Apply"]
            APR["Manual Approval"]
        end

        subgraph EXEC["Terraform Execution (CodeBuild)"]
            CB_PLAN["CodeBuild · plan<br/><br/>]
            CB_APPLY["CodeBuild · apply<br/><br/>"]
            CB_PR["CodeBuild · PR plan<br/>"]
            ENVV["️CodeBuild env vars<br/>"]
        end

        subgraph STATE_PIPE["PIPELINE State (own backend)"]
            S3_PIPE["S3 · pipeline-cicd"]
            DDB_PIPE["DynamoDB · pipeline lock"]
        end

        subgraph GOV["Governance & Observability"]
            KMS["KMS · CMK"]
            IDC["IAM Identity Center"]
            SNS["SNS · alerts / approvals"]
            MON["CloudWatch · CloudTrail · EventBridge"]
        end
    end

    %% ============================================================
    %% REPO 2 + TARGET LAYER: Infrastructure to provision
    %% Separate state: target-infra/terraform.tfstate
    %% ============================================================
    subgraph TARGET["TARGET INFRASTRUCTURE (separate repo & state)"]
        direction TB

        GH_APP["GitHub Repo: target-infra<br/>application Terraform code"]

        subgraph STATE_APP["TARGET State (independent backend)"]
            S3_APP["S3 · <br/>(target_state_bucket)"]
            DDB_APP["DynamoDB · <br/>(target_lock_table)"]
        end

        subgraph RESOURCES["Provisioned resources"]
            NET["Networking"]
            COMPUTE["Compute"]
            OTHERS["Other AWS resources"]
        end
    end

    %% ----------------- Solution bootstrap -----------------
    GH_PIPE -->|local terraform apply<br/>one-time bootstrap| STATE_PIPE

    %% ----------------- Pipeline flow -----------------
    GH_APP -->|push / webhook| CSC
    CSC --> CP
    CP --> CB_PLAN
    CB_PLAN --> APR
    APR --> CB_APPLY
    GH_APP -.->|Pull Request| CB_PR

    %% Target state config injection
    ENVV -. override backend .-> CB_PLAN
    ENVV -. override backend .-> CB_APPLY
    ENVV -. override backend .-> CB_PR

    %% Pipeline OPERATES on the TARGET repo state
    CB_PLAN  <-->|read/write| S3_APP
    CB_APPLY <-->|read/write| S3_APP
    CB_PLAN  <--> DDB_APP
    CB_APPLY <--> DDB_APP

    %% Provisioning the target layer
    CB_APPLY ==>|terraform apply| RESOURCES

    %% Internal solution dependencies
    KMS -. encrypts .-> S3_PIPE
    KMS -. encrypts .-> S3_APP
    CB_PLAN --> SNS
    CB_APPLY --> SNS
    IDC -. authorizes .-> CP
    MON -. audits .-> CP
    MON -. audits .-> CB_APPLY

    %% ----------------- Styles -----------------
    classDef solution fill:#e8f0fe,stroke:#1a73e8,stroke-width:1px,color:#0b1f44;
    classDef target fill:#e6f4ea,stroke:#137333,stroke-width:1px,color:#0b3d1f;
    classDef external fill:#fff4e5,stroke:#e37400,stroke-width:1px,color:#4a2c00;
    classDef config fill:#f3e8fd,stroke:#8430ce,stroke-width:1px,color:#2e0b52;

    class CP,APR,CB_PLAN,CB_APPLY,CB_PR,S3_PIPE,DDB_PIPE,KMS,IDC,SNS,MON solution;
    class NET,COMPUTE,OTHERS,S3_APP,DDB_APP target;
    class GH_PIPE,GH_APP,CSC external;
    class ENVV config;

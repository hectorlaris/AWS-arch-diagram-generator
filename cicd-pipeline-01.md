flowchart LR
    github["GitHub<br/>Repository"]

    subgraph aws_pipeline["AWS CI/CD Account"]
        connection["AWS CodeConnections<br/>GitHub App"]

        subgraph codepipeline["AWS CodePipeline"]
            source["Source"]
            plan["CodeBuild<br/>Terraform Plan"]
            approval["Manual Approval"]
            apply["CodeBuild<br/>Terraform Apply"]
        end

        artifacts[("Amazon S3<br/>Pipeline Artifacts")]
        sns["Amazon SNS"]
        devops["DevOps Email"]
    end

    subgraph target["AWS Target Account / Environment"]
        infrastructure["AWS Infrastructure<br/>Managed by Terraform"]
        state[("S3 Terraform State")]
        locking[("DynamoDB State Lock")]
    end

    github -->|"Push to main"| connection
    connection --> source
    source --> plan

    plan -->|"tfplan artifact"| artifacts
    artifacts --> approval

    approval -->|"Approval request"| sns
    sns -->|"Email notification"| devops

    approval -->|"Approved"| apply
    approval -.->|"Rejected or expired"| stopped["Pipeline stopped"]

    apply -->|"terraform apply tfplan"| infrastructure
    plan -.->|"terraform init / read state"| state
    apply -.->|"terraform init / lock state"| state
    apply -.->|"State locking"| locking

    classDef githubStyle fill:#24292e,stroke:#000,color:#fff;
    classDef awsStyle fill:#ff9900,stroke:#b35c00,stroke-width:2px,color:#111;
    classDef codebuildStyle fill:#d9ead3,stroke:#38761d,stroke-width:2px,color:#111;
    classDef approvalStyle fill:#f4cccc,stroke:#990000,stroke-width:2px,color:#111;
    classDef storageStyle fill:#cfe2f3,stroke:#1155cc,stroke-width:2px,color:#111;
    classDef targetStyle fill:#eadcf8,stroke:#674ea7,stroke-width:2px,color:#111;
    classDef errorStyle fill:#f4cccc,stroke:#cc0000,color:#111;

    class github githubStyle;
    class connection,codepipeline,sns awsStyle;
    class plan,apply codebuildStyle;
    class approval approvalStyle;
    class artifacts,state,locking storageStyle;
    class infrastructure targetStyle;
    class stopped errorStyle;
 
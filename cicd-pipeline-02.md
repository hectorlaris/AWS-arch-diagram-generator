flowchart TB
    Dev["👨‍💻 DevOps User<br/>(IAM Identity Center + MFA)"]
    GitHub["📦 GitHub<br/>aws-3-tier-terraform"]

    subgraph Cloud["☁️ AWS Cloud"]
        subgraph Account["AWS Account · 962682390364"]
            subgraph Region["Region · us-east-1"]

                subgraph CICD["Pipeline CI/CD"]
                    CSC["CodeStar Connection"]
                    CP["CodePipeline<br/>terraform-cicd-terraform-pipeline"]
                    CB["CodeBuild<br/>terraform-execution"]
                    subgraph Stages["Stages"]
                        S1["Source"]
                        S2["Build · plan"]
                        S3["Approval · manual"]
                        S4["Deploy · apply"]
                    end
                end

                subgraph State["State Backend"]
                    S3State["S3 Bucket<br/>terraform-state"]
                    DDB["DynamoDB<br/>state-lock"]
                    KMS["KMS Key<br/>state-encryption"]
                end

                subgraph Notif["Notifications & Audit"]
                    SNS["SNS Topics<br/>approvals / failures / alerts"]
                    CT["CloudTrail"]
                    CW["CloudWatch Logs"]
                end

                subgraph ThreeTier["3-Tier Architecture · VPC 10.0.0.0/22"]
                    IGW["Internet Gateway"]

                    subgraph AZa["AZ us-east-1a"]
                        PubA["Public Subnet<br/>10.0.0.0/25"]
                        PrivA["Private Subnet<br/>10.0.1.0/25"]
                    end
                    subgraph AZb["AZ us-east-1b"]
                        PubB["Public Subnet<br/>10.0.0.128/25"]
                        PrivB["Private Subnet<br/>10.0.1.128/25"]
                    end

                    NAT["NAT Gateway + EIP"]
                    ALB["Application<br/>Load Balancer"]
                    TG["Target Group"]
                    ASG["Auto Scaling Group<br/>EC2 t3.micro x2-4<br/>Apache"]
                    ALARM["CloudWatch Alarm<br/>ALB 5xx"]
                end
            end
        end
    end

    Dev -->|push| GitHub
    GitHub --> CSC --> CP
    CP --> S1 --> S2 --> S3 --> S4
    S2 & S4 --> CB
    CB -->|read/write state| S3State
    CB -->|lock| DDB
    S3State -.encrypt.-> KMS
    CB -.logs.-> CW
    CP -->|notify| SNS
    SNS -->|email| Dev
    CT -.audit.-> CW

    CB ==>|provisions| ThreeTier

    Internet["🌐 Internet"] --> IGW --> ALB
    ALB --> TG --> ASG
    ASG -.hosted in.-> PrivA & PrivB
    ALB -.hosted in.-> PubA & PubB
    PrivA & PrivB -->|outbound| NAT --> IGW
    ASG -.monitored by.-> ALARM

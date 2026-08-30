flowchart TB
    %% ============================================================
    %% CAPA 1: INFRAESTRUCTURA DE LA SOLUCIÓN (Pipeline CI/CD)
    %% Se aprovisiona una vez con Terraform local (bootstrap)
    %% ============================================================
    subgraph SOLUCION["🏗️ INFRAESTRUCTURA DE LA SOLUCIÓN — Pipeline CI/CD (bootstrap)"]
        direction LR

        GH["📦 GitHub Repo<br/>(código Terraform)"]
        CSC["🔗 CodeStar Connection<br/>(GitHub)"]

        subgraph ORQ["Orquestación"]
            CP["🚀 AWS CodePipeline<br/>Source → Plan → Approval → Apply"]
            APR["✋ Manual Approval<br/>(cambios de alto riesgo)"]
        end

        subgraph EJEC["Ejecución Terraform"]
            CB_PLAN["🔨 CodeBuild<br/>terraform plan<br/>(buildspec-plan.yml)"]
            CB_APPLY["🔨 CodeBuild<br/>terraform apply<br/>(buildspec-apply.yml)"]
            CB_PR["🔨 CodeBuild<br/>PR plan<br/>(buildspec-pr-plan.yml)"]
        end

        subgraph ESTADO["Estado y Seguridad"]
            S3["🪣 S3<br/>tf state + artifacts"]
            DDB["🗄️ DynamoDB<br/>state lock"]
            KMS["🔐 KMS<br/>CMK encryption"]
        end

        subgraph GOB["Gobierno y Observabilidad"]
            IDC["👤 IAM Identity Center<br/>Permission Sets"]
            SNS["📣 SNS<br/>alertas / aprobaciones"]
            MON["📊 CloudWatch + CloudTrail<br/>+ EventBridge"]
        end
    end

    %% ============================================================
    %% CAPA 2: INFRAESTRUCTURA OBJETIVO A APROVISIONAR
    %% Lo que el pipeline crea al ejecutar terraform apply
    %% ============================================================
    subgraph OBJETIVO["🎯 INFRAESTRUCTURA OBJETIVO A APROVISIONAR (por el pipeline)"]
        direction LR
        NET["🌐 Networking<br/>(VPC / Subnets / Routing)"]
        COMPUTE["🖥️ Compute<br/>(EC2 / ALB)"]
        OTROS["➕ Otros recursos AWS<br/>definidos en el código"]
    end

    %% ----------------- Flujo del pipeline -----------------
    GH -->|webhook / push| CSC
    CSC --> CP
    CP --> CB_PLAN
    CB_PLAN --> APR
    APR --> CB_APPLY
    GH -.->|Pull Request| CB_PR

    %% Dependencias de servicios de la solución
    CB_PLAN <--> S3
    CB_APPLY <--> S3
    CB_PLAN <--> DDB
    CB_APPLY <--> DDB
    KMS -. cifra .-> S3
    KMS -. cifra .-> DDB
    CB_PLAN --> SNS
    CB_APPLY --> SNS
    IDC -. autoriza .-> CP
    MON -. audita .-> CP
    MON -. audita .-> CB_APPLY

    %% ----------------- Provisionamiento objetivo -----------------
    CB_APPLY ==>|terraform apply<br/>aprovisiona| OBJETIVO

    %% ----------------- Estilos -----------------
    classDef solucion fill:#e8f0fe,stroke:#1a73e8,stroke-width:1px,color:#0b1f44;
    classDef objetivo fill:#e6f4ea,stroke:#137333,stroke-width:1px,color:#0b3d1f;
    classDef externo fill:#fff4e5,stroke:#e37400,stroke-width:1px,color:#4a2c00;

    class CP,APR,CB_PLAN,CB_APPLY,CB_PR,S3,DDB,KMS,IDC,SNS,MON solucion;
    class NET,COMPUTE,OTROS objetivo;
    class GH,CSC externo;

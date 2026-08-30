flowchart TB
    %% ============================================================
    %% REPO 1 + CAPA SOLUCIÓN: Pipeline CI/CD (bootstrap)
    %% Estado propio: pipeline-cicd/terraform.tfstate
    %% ============================================================
    subgraph SOLUCION["🏗️ INFRAESTRUCTURA DE LA SOLUCIÓN — Pipeline CI/CD"]
        direction TB

        GH_PIPE["📦 GitHub Repo: pipeline-cicd<br/>módulos + backend.tf (partial)"]
        CSC["🔗 CodeStar Connection (GitHub)"]

        subgraph ORQ["Orquestación"]
            CP["🚀 AWS CodePipeline<br/>Source → Plan → Approval → Apply"]
            APR["✋ Manual Approval"]
        end

        subgraph EJEC["Ejecución Terraform (CodeBuild)"]
            CB_PLAN["🔨 CodeBuild · plan<br/>init -reconfigure<br/>key=$TF_STATE_KEY"]
            CB_APPLY["🔨 CodeBuild · apply<br/>init -reconfigure<br/>key=$TF_STATE_KEY"]
            CB_PR["🔨 CodeBuild · PR plan<br/>key=$TF_STATE_KEY"]
            ENVV["⚙️ Env vars CodeBuild<br/>TF_STATE_BUCKET · TF_STATE_KEY · TF_LOCK_TABLE"]
        end

        subgraph ESTADO_PIPE["Estado del PIPELINE (backend propio)"]
            S3_PIPE["🪣 S3 · pipeline-cicd/terraform.tfstate"]
            DDB_PIPE["🗄️ DynamoDB · lock pipeline"]
        end

        subgraph GOB["Gobierno y Observabilidad"]
            KMS["🔐 KMS · CMK"]
            IDC["👤 IAM Identity Center"]
            SNS["📣 SNS · alertas / aprobaciones"]
            MON["📊 CloudWatch · CloudTrail · EventBridge"]
        end
    end

    %% ============================================================
    %% REPO 2 + CAPA OBJETIVO: Infraestructura a aprovisionar
    %% Estado SEPARADO: target-infra/terraform.tfstate
    %% ============================================================
    subgraph OBJETIVO["🎯 INFRAESTRUCTURA OBJETIVO (repo y estado separados)"]
        direction TB

        GH_APP["📦 GitHub Repo: infra-objetivo<br/>código Terraform de la app"]

        subgraph ESTADO_APP["Estado OBJETIVO (backend independiente)"]
            S3_APP["🪣 S3 · target-infra/terraform.tfstate<br/>(target_state_bucket)"]
            DDB_APP["🗄️ DynamoDB · lock objetivo<br/>(target_lock_table)"]
        end

        subgraph RECURSOS["Recursos aprovisionados"]
            NET["🌐 Networking · VPC / Subnets / Routing"]
            COMPUTE["🖥️ Compute · EC2 / ALB"]
            OTROS["➕ Otros recursos AWS"]
        end
    end

    %% ----------------- Bootstrap de la solución -----------------
    GH_PIPE -->|terraform apply local<br/>bootstrap una vez| ESTADO_PIPE

    %% ----------------- Flujo del pipeline -----------------
    GH_APP -->|push / webhook| CSC
    CSC --> CP
    CP --> CB_PLAN
    CB_PLAN --> APR
    APR --> CB_APPLY
    GH_APP -.->|Pull Request| CB_PR

    %% Inyección de configuración de estado objetivo
    ENVV -. override backend .-> CB_PLAN
    ENVV -. override backend .-> CB_APPLY
    ENVV -. override backend .-> CB_PR

    %% El pipeline OPERA sobre el estado del repo OBJETIVO
    CB_PLAN  <-->|lee/escribe| S3_APP
    CB_APPLY <-->|lee/escribe| S3_APP
    CB_PLAN  <--> DDB_APP
    CB_APPLY <--> DDB_APP

    %% Aprovisionamiento de la capa objetivo
    CB_APPLY ==>|terraform apply| RECURSOS

    %% Dependencias internas de la solución
    KMS -. cifra .-> S3_PIPE
    KMS -. cifra .-> S3_APP
    CB_PLAN --> SNS
    CB_APPLY --> SNS
    IDC -. autoriza .-> CP
    MON -. audita .-> CP
    MON -. audita .-> CB_APPLY

    %% ----------------- Estilos -----------------
    classDef solucion fill:#e8f0fe,stroke:#1a73e8,stroke-width:1px,color:#0b1f44;
    classDef objetivo fill:#e6f4ea,stroke:#137333,stroke-width:1px,color:#0b3d1f;
    classDef externo fill:#fff4e5,stroke:#e37400,stroke-width:1px,color:#4a2c00;
    classDef config fill:#f3e8fd,stroke:#8430ce,stroke-width:1px,color:#2e0b52;

    class CP,APR,CB_PLAN,CB_APPLY,CB_PR,S3_PIPE,DDB_PIPE,KMS,IDC,SNS,MON solucion;
    class NET,COMPUTE,OTROS,S3_APP,DDB_APP objetivo;
    class GH_PIPE,GH_APP,CSC externo;
    class ENVV config;

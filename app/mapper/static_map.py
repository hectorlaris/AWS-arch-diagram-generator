"""Static mapping of normalized service names to diagrams import paths.

Keys are pre-normalized (lowercase, no whitespace/hyphens/underscores) to allow
direct lookup after applying normalize_service_name() to a node label.

Two maps are maintained and merged:
  - AWS_SERVICE_MAP: services under the diagrams.aws provider hierarchy.
  - NON_AWS_SERVICE_MAP: icons from other diagrams providers (onprem, generic,
    programming, saas) used for nodes that are not AWS services, such as
    GitHub, Terraform, users, email, and generic process/flow concepts.

NON_AWS_SERVICE_MAP entries take precedence when the same key exists in both
(e.g. "github" maps to the real GitHub icon, not the AWS General fallback).
"""

AWS_SERVICE_MAP: dict[str, str] = {
    # Network
    "apigateway": "diagrams.aws.network.APIGateway",
    "route53": "diagrams.aws.network.Route53",
    "elb": "diagrams.aws.network.ELB",
    "vpc": "diagrams.aws.network.VPC",
    "cloudfront": "diagrams.aws.network.CloudFront",
    # Security
    "cognito": "diagrams.aws.security.Cognito",
    "kms": "diagrams.aws.security.KMS",
    "secretsmanager": "diagrams.aws.security.SecretsManager",
    "iam": "diagrams.aws.security.IAM",
    # Compute
    "lambda": "diagrams.aws.compute.Lambda",
    "ecs": "diagrams.aws.compute.ECS",
    "ec2": "diagrams.aws.compute.EC2",
    "fargate": "diagrams.aws.compute.Fargate",
    # Integration
    "stepfunctions": "diagrams.aws.integration.StepFunctions",
    "sqs": "diagrams.aws.integration.SQS",
    "sns": "diagrams.aws.integration.SNS",
    "eventbridge": "diagrams.aws.integration.Eventbridge",
    # Database
    "dynamodb": "diagrams.aws.database.Dynamodb",
    "rds": "diagrams.aws.database.RDS",
    "aurora": "diagrams.aws.database.Aurora",
    "elasticache": "diagrams.aws.database.ElastiCache",
    # Management
    "cloudwatch": "diagrams.aws.management.Cloudwatch",
    "cloudtrail": "diagrams.aws.management.Cloudtrail",
    # Developer Tools
    "xray": "diagrams.aws.devtools.XRay",
    "codebuild": "diagrams.aws.devtools.Codebuild",
    "codepipeline": "diagrams.aws.devtools.Codepipeline",
    "codecommit": "diagrams.aws.devtools.Codecommit",
    "codedeploy": "diagrams.aws.devtools.Codedeploy",
    "codeconnections": "diagrams.aws.devtools.Codepipeline",
    # Machine Learning / AI
    "bedrock": "diagrams.aws.ml.Bedrock",
    "agent": "diagrams.aws.ml.Bedrock",
    "bedrockagent": "diagrams.aws.ml.Bedrock",
    "sagemaker": "diagrams.aws.ml.Sagemaker",
    "comprehend": "diagrams.aws.ml.Comprehend",
    "rekognition": "diagrams.aws.ml.Rekognition",
    "textract": "diagrams.aws.ml.Textract",
    "lex": "diagrams.aws.ml.Lex",
    "polly": "diagrams.aws.ml.Polly",
    "kendra": "diagrams.aws.ml.Kendra",
    "translate": "diagrams.aws.ml.Translate",
    "transcribe": "diagrams.aws.ml.Transcribe",
    # Storage
    "s3": "diagrams.aws.storage.S3",
    # General
    "client": "diagrams.aws.general.Client",
    # Common aliases
    "amazons3": "diagrams.aws.storage.S3",
    "amazonsns": "diagrams.aws.integration.SNS",
    "amazonsqs": "diagrams.aws.integration.SQS",
    "amazondynamodb": "diagrams.aws.database.Dynamodb",
    "awslambda": "diagrams.aws.compute.Lambda",
    "amazonrds": "diagrams.aws.database.RDS",
    "amazonec2": "diagrams.aws.compute.EC2",
    "amazonecs": "diagrams.aws.compute.ECS",
    "amazonvpc": "diagrams.aws.network.VPC",
    "amazoncloudwatch": "diagrams.aws.management.Cloudwatch",
    "amazoncloudfront": "diagrams.aws.network.CloudFront",
    "amazonroute53": "diagrams.aws.network.Route53",
    "awscodebuild": "diagrams.aws.devtools.Codebuild",
    "awscodepipeline": "diagrams.aws.devtools.Codepipeline",
    "awscodeconnections": "diagrams.aws.devtools.Codepipeline",
}


NON_AWS_SERVICE_MAP: dict[str, str] = {
    # Version control
    "github": "diagrams.onprem.vcs.Github",
    "gitlab": "diagrams.onprem.vcs.Gitlab",
    "git": "diagrams.onprem.vcs.Git",
    # Infrastructure as Code
    "terraform": "diagrams.onprem.iac.Terraform",
    "ansible": "diagrams.onprem.iac.Ansible",
    # CI/CD
    "jenkins": "diagrams.onprem.ci.Jenkins",
    "githubactions": "diagrams.onprem.ci.GithubActions",
    # Containers
    "docker": "diagrams.onprem.container.Docker",
    "kubernetes": "diagrams.onprem.container.K3S",
    # Clients / people
    "user": "diagrams.onprem.client.User",
    "users": "diagrams.onprem.client.Users",
    # Communication / SaaS
    "slack": "diagrams.saas.chat.Slack",
    # Monitoring
    "grafana": "diagrams.onprem.monitoring.Grafana",
    "prometheus": "diagrams.onprem.monitoring.Prometheus",
}


# Merged view used by the resolver. Non-AWS entries win on key collisions.
STATIC_SERVICE_MAP: dict[str, str] = {**AWS_SERVICE_MAP, **NON_AWS_SERVICE_MAP}

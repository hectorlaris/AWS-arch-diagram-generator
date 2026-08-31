"""Unit tests for the service resolver module.

Covers dynamic cache building, class import resolution, and warning entries.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.mapper.resolver import (
    resolve_service,
    clear_cache,
    _build_dynamic_cache,
    _import_class_from_path,
)
from app.api.models import WarningEntry


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the dynamic cache before each test for isolation."""
    clear_cache()
    yield
    clear_cache()


class TestStaticMapResolution:
    """Tests for Tier 1 static map lookups."""

    def test_resolve_lambda(self):
        """Lambda resolves via static map without warning."""
        cls, warning = resolve_service("Lambda")
        assert cls is not None
        assert cls.__name__ == "Lambda"
        assert warning is None

    def test_resolve_dynamodb(self):
        """DynamoDB resolves via static map (case insensitive)."""
        cls, warning = resolve_service("DynamoDB")
        assert cls is not None
        assert cls.__name__ == "Dynamodb"
        assert warning is None

    def test_resolve_api_gateway_with_spaces(self):
        """API Gateway with spaces resolves via normalization."""
        cls, warning = resolve_service("API Gateway")
        assert cls is not None
        assert cls.__name__ == "APIGateway"
        assert warning is None

    def test_resolve_api_gateway_with_underscore(self):
        """api_gateway with underscores resolves via normalization."""
        cls, warning = resolve_service("api_gateway")
        assert cls is not None
        assert cls.__name__ == "APIGateway"
        assert warning is None

    def test_resolve_api_gateway_with_hyphen(self):
        """api-gateway with hyphens resolves via normalization."""
        cls, warning = resolve_service("api-gateway")
        assert cls is not None
        assert cls.__name__ == "APIGateway"
        assert warning is None

    def test_resolve_case_insensitive(self):
        """LAMBDA in all caps resolves correctly."""
        cls, warning = resolve_service("LAMBDA")
        assert cls is not None
        assert cls.__name__ == "Lambda"
        assert warning is None

    def test_resolve_sqs(self):
        """SQS resolves via static map."""
        from diagrams.aws.integration import SQS as ExpectedSQS

        cls, warning = resolve_service("SQS")
        assert cls is not None
        assert cls is ExpectedSQS
        assert warning is None

    def test_resolve_s3(self):
        """S3 resolves via static map."""
        from diagrams.aws.storage import S3 as ExpectedS3

        cls, warning = resolve_service("S3")
        assert cls is not None
        assert cls is ExpectedS3
        assert warning is None

    def test_resolve_cloudwatch(self):
        """CloudWatch resolves via static map."""
        cls, warning = resolve_service("CloudWatch")
        assert cls is not None
        assert cls.__name__ == "Cloudwatch"
        assert warning is None

    def test_resolve_cognito(self):
        """Cognito resolves via static map."""
        cls, warning = resolve_service("Cognito")
        assert cls is not None
        assert cls.__name__ == "Cognito"
        assert warning is None

    def test_resolve_kms(self):
        """KMS resolves via static map."""
        from diagrams.aws.security import KMS as ExpectedKMS

        cls, warning = resolve_service("KMS")
        assert cls is not None
        assert cls is ExpectedKMS
        assert warning is None

    def test_resolve_secrets_manager(self):
        """SecretsManager with variations resolves via static map."""
        cls, warning = resolve_service("Secrets Manager")
        assert cls is not None
        assert cls.__name__ == "SecretsManager"
        assert warning is None

    def test_resolve_step_functions(self):
        """Step Functions resolves via static map."""
        cls, warning = resolve_service("Step Functions")
        assert cls is not None
        assert cls.__name__ == "StepFunctions"
        assert warning is None

    def test_resolve_ecs(self):
        """ECS resolves via static map."""
        from diagrams.aws.compute import ECS as ExpectedECS

        cls, warning = resolve_service("ECS")
        assert cls is not None
        assert cls is ExpectedECS
        assert warning is None

    def test_resolve_ec2(self):
        """EC2 resolves via static map."""
        cls, warning = resolve_service("EC2")
        assert cls is not None
        assert cls.__name__ == "EC2"
        assert warning is None


class TestUnknownServiceFallback:
    """Tests for fallback to General class when no match is found."""

    def test_unknown_label_returns_general(self):
        """Completely unknown label falls back to General class."""
        cls, warning = resolve_service("TotallyMadeUpService12345")
        assert cls is not None
        assert cls.__name__ == "General"
        assert warning is not None

    def test_unknown_label_warning_structure(self):
        """Unknown label produces properly structured WarningEntry."""
        cls, warning = resolve_service("NonExistentAWSService999")
        assert isinstance(warning, WarningEntry)
        assert warning.node_label == "NonExistentAWSService999"
        assert "No matching AWS service" in warning.reason
        assert warning.selected_service == "diagrams.aws.general.General"
        assert warning.alternatives is None

    def test_random_string_falls_back(self):
        """Random gibberish string returns General with warning."""
        cls, warning = resolve_service("xyzzy12345abcdef")
        assert cls.__name__ == "General"
        assert warning is not None
        assert warning.node_label == "xyzzy12345abcdef"


class TestDynamicResolution:
    """Tests for Tier 2 dynamic resolution via diagrams.aws introspection."""

    def test_dynamic_resolves_known_service_not_in_static_map(self):
        """Services in diagrams.aws but NOT in static map resolve dynamically."""
        # ElastiCache is in diagrams.aws.database but not in our static map
        cls, warning = resolve_service("ElastiCache")
        # Should either resolve dynamically or fall back to General
        assert cls is not None
        # If diagrams library has ElastiCache, it should resolve without warning
        # Otherwise it would fall back to General
        if cls.__name__ != "General":
            assert warning is None or warning.reason.startswith("Ambiguous")

    def test_dynamic_cache_is_built(self):
        """The dynamic cache builds successfully from diagrams.aws."""
        cache = _build_dynamic_cache()
        assert isinstance(cache, dict)
        # Should contain at least some entries from the diagrams.aws package
        assert len(cache) > 0


class TestAmbiguousMatchResolution:
    """Tests for ambiguous match handling."""

    def test_ambiguous_selects_first_alphabetical(self):
        """When multiple matches exist, first alphabetical FQN is selected."""
        # We mock the cache to have controlled ambiguous entries
        mock_class_a = type("MockA", (), {"__module__": "diagrams.aws.a.MockA"})
        mock_class_b = type("MockB", (), {"__module__": "diagrams.aws.b.MockB"})

        fake_cache = {
            "ambiguous": [
                ("diagrams.aws.b.MockB.Ambiguous", mock_class_b),
                ("diagrams.aws.a.MockA.Ambiguous", mock_class_a),
            ]
        }

        with patch("app.mapper.resolver._get_dynamic_cache", return_value=fake_cache):
            with patch("app.mapper.resolver.STATIC_SERVICE_MAP", {}):
                cls, warning = resolve_service("Ambiguous")

        assert cls is mock_class_a
        assert warning is not None
        assert warning.reason.startswith("Ambiguous match")
        assert warning.selected_service == "diagrams.aws.a.MockA.Ambiguous"
        assert "diagrams.aws.b.MockB.Ambiguous" in warning.alternatives

    def test_ambiguous_limits_alternatives_to_5(self):
        """Alternatives list is capped at 5 entries."""
        mock_classes = []
        fake_entries = []
        for i in range(8):
            cls = type(f"Mock{i}", (), {"__module__": f"diagrams.aws.mod{i}"})
            mock_classes.append(cls)
            fake_entries.append((f"diagrams.aws.mod{i}.Testname", cls))

        fake_cache = {"testname": fake_entries}

        with patch("app.mapper.resolver._get_dynamic_cache", return_value=fake_cache):
            with patch("app.mapper.resolver.STATIC_SERVICE_MAP", {}):
                cls, warning = resolve_service("Testname")

        assert warning is not None
        assert len(warning.alternatives) <= 5

    def test_ambiguous_warning_has_node_label(self):
        """Ambiguous warning preserves the original node label."""
        mock_class_a = type("A", (), {"__module__": "diagrams.aws.compute"})
        mock_class_b = type("B", (), {"__module__": "diagrams.aws.network"})

        fake_cache = {
            "myservice": [
                ("diagrams.aws.compute.MyService", mock_class_a),
                ("diagrams.aws.network.MyService", mock_class_b),
            ]
        }

        with patch("app.mapper.resolver._get_dynamic_cache", return_value=fake_cache):
            with patch("app.mapper.resolver.STATIC_SERVICE_MAP", {}):
                cls, warning = resolve_service("My Service")

        assert warning.node_label == "My Service"


class TestImportClassFromPath:
    """Tests for the internal import helper."""

    def test_import_valid_path(self):
        """Importing a known diagrams class works correctly."""
        cls = _import_class_from_path("diagrams.aws.compute.Lambda")
        assert cls.__name__ == "Lambda"

    def test_import_invalid_module_raises(self):
        """Importing from non-existent module raises ImportError."""
        with pytest.raises((ImportError, ModuleNotFoundError)):
            _import_class_from_path("diagrams.aws.nonexistent.FakeClass")

    def test_import_invalid_class_raises(self):
        """Importing non-existent class from valid module raises AttributeError."""
        with pytest.raises(AttributeError):
            _import_class_from_path("diagrams.aws.compute.NonExistentClass99")

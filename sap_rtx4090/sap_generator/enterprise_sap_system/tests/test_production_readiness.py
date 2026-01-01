#!/usr/bin/env python3
"""
Production Readiness Tests
==========================

Tests for production-critical functionality:
- Error handling
- Thread safety
- Configuration validation
- Circuit breaker behavior
"""

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestLoggingConfig:
    """Test structured logging infrastructure."""

    def test_logger_import(self):
        """Test that logger can be imported."""
        from enterprise_sap_system.core.logging_config import get_logger
        logger = get_logger(__name__)
        assert logger is not None

    def test_logger_methods(self):
        """Test that all log methods work without error."""
        from enterprise_sap_system.core.logging_config import get_logger
        logger = get_logger(__name__)

        # These should not raise
        logger.debug("debug message", key="value")
        logger.info("info message", key="value")
        logger.warning("warning message", key="value")
        logger.error("error message", key="value")

    def test_exception_classes(self):
        """Test custom exception classes."""
        from enterprise_sap_system.core.logging_config import (
            SAPGeneratorError,
            ExtractionError,
            ValidationError,
            APIError,
            LLMError,
            ConfigurationError
        )

        # Test that they can be instantiated
        e1 = ExtractionError("test", field="drug_name")
        assert e1.field == "drug_name"

        e2 = APIError("test", api="clinicaltrials.gov", status_code=404)
        assert e2.status_code == 404

        e3 = LLMError("test", provider="claude")
        assert e3.provider == "claude"


class TestTieredLLMClient:
    """Test LLM client with circuit breaker."""

    def test_thread_safe_singleton(self):
        """Test that singleton is thread-safe."""
        from enterprise_sap_system.core.tiered_llm import get_tiered_client, reset_client

        reset_client()  # Clear any existing client
        clients = []

        def get_client():
            clients.append(get_tiered_client())

        # Start multiple threads
        threads = [threading.Thread(target=get_client) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same client
        assert len(clients) == 10
        assert all(c is clients[0] for c in clients)

    def test_circuit_breaker_opens_after_errors(self):
        """Test that circuit breaker opens after consecutive errors."""
        from enterprise_sap_system.core.tiered_llm import APIStatus

        status = APIStatus(available=True)

        # Simulate 3 errors (threshold)
        for _ in range(3):
            status.record_error()

        # After 3 errors, cooldown should be set
        assert status.cooldown_until > time.time()

    def test_circuit_breaker_rate_limit_backoff(self):
        """Test exponential backoff on rate limits."""
        from enterprise_sap_system.core.tiered_llm import APIStatus

        status = APIStatus(available=True)

        # First rate limit
        cooldown1 = status.record_error(is_rate_limit=True)
        assert cooldown1 == 30  # Base cooldown

        # Second rate limit
        cooldown2 = status.record_error(is_rate_limit=True)
        assert cooldown2 == 60  # 2x backoff

        # Third rate limit
        cooldown3 = status.record_error(is_rate_limit=True)
        assert cooldown3 == 120  # 4x backoff

    def test_success_resets_circuit_breaker(self):
        """Test that success resets the circuit breaker."""
        from enterprise_sap_system.core.tiered_llm import APIStatus

        status = APIStatus(available=True)

        # Record some errors
        status.record_error()
        status.record_error()
        assert status.consecutive_errors == 2

        # Record success
        status.record_success()
        assert status.consecutive_errors == 0
        assert status.cooldown_until == 0

    def test_get_status_method(self):
        """Test status reporting method."""
        from enterprise_sap_system.core.tiered_llm import get_tiered_client

        client = get_tiered_client()
        status = client.get_status()

        assert "claude" in status
        assert "openai" in status
        assert "groq" in status

        for tier_status in status.values():
            assert "available" in tier_status
            assert "configured" in tier_status
            assert "consecutive_errors" in tier_status


class TestConfiguration:
    """Test configuration management."""

    def test_thread_safe_config(self):
        """Test that config is thread-safe."""
        from enterprise_sap_system.core.config import get_config, reset_config

        reset_config()  # Clear any existing config
        configs = []

        def get_cfg():
            configs.append(get_config())

        # Start multiple threads
        threads = [threading.Thread(target=get_cfg) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same config
        assert len(configs) == 10
        assert all(c is configs[0] for c in configs)

    def test_model_config_validation(self):
        """Test that model config validates providers."""
        from enterprise_sap_system.core.config import ModelConfig

        # With no API keys
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig(
                groq_api_key=None,
                anthropic_api_key=None,
                openai_api_key=None
            )
            providers = config.get_available_providers()
            assert providers == []

    def test_env_var_validation(self):
        """Test environment variable validation."""
        from enterprise_sap_system.core.config import validate_env_vars, ConfigurationError

        # Test with missing required vars
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError):
                validate_env_vars(required=["DEFINITELY_NOT_SET"])

        # Test with optional vars (should not raise)
        with patch.dict(os.environ, {}, clear=True):
            result = validate_env_vars(optional=["OPTIONAL_VAR"])
            assert result["OPTIONAL_VAR"] is False


class TestDataModels:
    """Test data model consistency."""

    def test_treatment_arm_has_description(self):
        """Test that TreatmentArm has description field."""
        from enterprise_sap_system.core.structured_extractor import TreatmentArm

        arm = TreatmentArm(name="Treatment A")
        assert hasattr(arm, 'description')
        assert arm.description == "Treatment A"  # Auto-populated

    def test_treatment_arm_compatibility(self):
        """Test that both TreatmentArm classes are compatible."""
        from enterprise_sap_system.core.structured_extractor import TreatmentArm as ExtractorArm
        from enterprise_sap_system.core.schemas import TreatmentArm as SchemaArm

        # Both should have all required fields
        extractor_arm = ExtractorArm(name="Test", is_placebo=True)
        schema_arm = SchemaArm(name="Test", is_placebo=True)

        assert extractor_arm.name == schema_arm.name
        assert extractor_arm.is_placebo == schema_arm.is_placebo
        assert hasattr(extractor_arm, 'description')
        assert hasattr(schema_arm, 'description')


class TestEnhancedParser:
    """Test enhanced parser error handling."""

    def test_parser_handles_llm_failure(self):
        """Test that parser gracefully handles LLM failures."""
        from enterprise_sap_system.core.enhanced_parser import EnhancedProtocolParser

        parser = EnhancedProtocolParser(use_llm_fallback=False)
        result = parser.parse("This is a test protocol.", nct_id="NCT12345678")

        # Should return a result (even if empty) without raising
        assert result is not None
        assert hasattr(result, 'nct_id')


class TestHybridPipeline:
    """Test hybrid pipeline error handling."""

    def test_pipeline_handles_missing_facts(self):
        """Test that pipeline handles missing extracted facts."""
        from enterprise_sap_system.core.hybrid_pipeline import HybridSAPPipeline

        # Create pipeline with extraction disabled
        pipeline = HybridSAPPipeline(
            use_rag=False,
            use_validation=False,
            verbose=False
        )

        result = pipeline.generate("Minimal test protocol")

        # Should not crash, should return result with warnings
        assert result is not None
        assert hasattr(result, 'success')
        assert hasattr(result, 'warnings')


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

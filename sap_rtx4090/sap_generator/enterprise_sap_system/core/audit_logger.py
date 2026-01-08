#!/usr/bin/env python3
"""
Audit Logger for SAP Generation
================================

Production-grade logging for regulatory compliance.

Logs:
1. All LLM prompts and responses (for reproducibility)
2. Extraction results (for verification)
3. Verification results (for audit trail)
4. Timestamps and versions (for traceability)

Output: JSON Lines format (.jsonl) for easy parsing and archival.
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class AuditLogEntry:
    """A single audit log entry."""
    timestamp: str
    event_type: str  # prompt, response, extraction, verification, error
    protocol_id: str
    session_id: str
    data: Dict[str, Any]
    # Hashes for integrity verification
    data_hash: str = ""

    def __post_init__(self):
        if not self.data_hash:
            self.data_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of data for integrity."""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]


class AuditLogger:
    """
    Audit logger for SAP generation pipeline.

    Creates one log file per protocol, stored in logs/ directory.
    """

    def __init__(self, log_dir: str = None, enabled: bool = True):
        self.enabled = enabled
        if not enabled:
            return

        # Default log directory
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "logs" / "audit"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Session ID for this run
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_file = None
        self._current_protocol = None

    def _get_log_file(self, protocol_id: str) -> Path:
        """Get log file path for a protocol."""
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in protocol_id)
        return self.log_dir / f"{safe_id}_{self.session_id}.jsonl"

    def _write_entry(self, entry: AuditLogEntry):
        """Write entry to log file."""
        if not self.enabled:
            return

        log_file = self._get_log_file(entry.protocol_id)
        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def log_prompt(self, protocol_id: str, prompt_type: str, prompt_text: str,
                   model: str = None, metadata: Dict = None):
        """Log an LLM prompt."""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="prompt",
            protocol_id=protocol_id,
            session_id=self.session_id,
            data={
                "prompt_type": prompt_type,
                "prompt_text": prompt_text[:50000],  # Limit size
                "prompt_length": len(prompt_text),
                "model": model,
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)

    def log_response(self, protocol_id: str, prompt_type: str, response_text: str,
                     model: str = None, duration_s: float = None, metadata: Dict = None):
        """Log an LLM response."""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="response",
            protocol_id=protocol_id,
            session_id=self.session_id,
            data={
                "prompt_type": prompt_type,
                "response_text": response_text[:100000],  # Limit size
                "response_length": len(response_text),
                "model": model,
                "duration_s": duration_s,
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)

    def log_extraction(self, protocol_id: str, elements: List[Dict],
                       source: str = None, metadata: Dict = None):
        """Log extraction results."""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="extraction",
            protocol_id=protocol_id,
            session_id=self.session_id,
            data={
                "element_count": len(elements),
                "elements": elements[:100],  # Limit to first 100
                "source": source,
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)

    def log_verification(self, protocol_id: str, verification_type: str,
                         passed: int, failed: int, warnings: int,
                         details: List[Dict] = None, metadata: Dict = None):
        """Log verification results."""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="verification",
            protocol_id=protocol_id,
            session_id=self.session_id,
            data={
                "verification_type": verification_type,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "total": passed + failed + warnings,
                "pass_rate": passed / (passed + failed + warnings) if (passed + failed + warnings) > 0 else 0,
                "details": details[:50] if details else [],  # Limit
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)

    def log_error(self, protocol_id: str, error_type: str, error_message: str,
                  stack_trace: str = None, metadata: Dict = None):
        """Log an error."""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="error",
            protocol_id=protocol_id,
            session_id=self.session_id,
            data={
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)

    def log_sap_generated(self, protocol_id: str, sap_text: str,
                          validation_score: float = None,
                          verification_summary: Dict = None,
                          metadata: Dict = None):
        """Log final SAP generation."""
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="sap_generated",
            protocol_id=protocol_id,
            session_id=self.session_id,
            data={
                "sap_length": len(sap_text),
                "sap_hash": hashlib.sha256(sap_text.encode()).hexdigest()[:32],
                "validation_score": validation_score,
                "verification_summary": verification_summary or {},
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)

    def get_session_logs(self, protocol_id: str) -> List[Dict]:
        """Read all logs for a protocol in this session."""
        log_file = self._get_log_file(protocol_id)
        if not log_file.exists():
            return []

        entries = []
        with open(log_file, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def get_log_path(self, protocol_id: str) -> Path:
        """Get the log file path for a protocol."""
        return self._get_log_file(protocol_id)


# Global logger instance
_global_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _global_logger
    if _global_logger is None:
        # Check if logging is disabled via environment
        enabled = os.environ.get("SAP_AUDIT_LOGGING", "1") != "0"
        _global_logger = AuditLogger(enabled=enabled)
    return _global_logger


def set_audit_logger(logger: AuditLogger):
    """Set a custom audit logger."""
    global _global_logger
    _global_logger = logger

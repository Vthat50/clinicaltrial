"""Database CRUD operations."""
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from .models import Trial, Protocol, ProtocolSection, SAP, SAPSection, get_session
from src.parsing.protocol_parser import ParsedProtocol, ParsedSection


class DatabaseOperations:
    """CRUD operations for clinical trial data."""

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def close(self):
        """Close the database session."""
        self.session.close()

    # Trial operations
    def get_or_create_trial(
        self,
        nct_id: str,
        title: Optional[str] = None,
        phase: Optional[str] = None,
        condition: Optional[str] = None,
        sponsor: Optional[str] = None,
    ) -> Trial:
        """Get existing trial or create new one."""
        trial = self.session.query(Trial).filter_by(nct_id=nct_id).first()

        if not trial:
            trial = Trial(
                nct_id=nct_id,
                title=title,
                phase=phase,
                condition=condition,
                sponsor=sponsor,
            )
            self.session.add(trial)
            self.session.commit()
        else:
            # Update fields if provided
            if title and not trial.title:
                trial.title = title
            if phase and not trial.phase:
                trial.phase = phase
            if condition and not trial.condition:
                trial.condition = condition
            if sponsor and not trial.sponsor:
                trial.sponsor = sponsor
            self.session.commit()

        return trial

    def get_trial_by_nct(self, nct_id: str) -> Optional[Trial]:
        """Get trial by NCT ID."""
        return self.session.query(Trial).filter_by(nct_id=nct_id).first()

    def get_all_trials(self) -> list[Trial]:
        """Get all trials."""
        return self.session.query(Trial).all()

    # Protocol operations
    def save_protocol(
        self,
        trial: Trial,
        file_path: str,
        raw_text: str,
        parsed_protocol: ParsedProtocol,
    ) -> Protocol:
        """Save protocol with extracted sections."""
        # Check if protocol already exists
        existing = (
            self.session.query(Protocol)
            .filter_by(trial_id=trial.id, file_path=file_path)
            .first()
        )

        if existing:
            # Delete existing sections to replace
            self.session.query(ProtocolSection).filter_by(
                protocol_id=existing.id
            ).delete()
            protocol = existing
            protocol.raw_text = raw_text
            protocol.parsed_at = datetime.utcnow()
        else:
            protocol = Protocol(
                trial_id=trial.id,
                file_path=file_path,
                raw_text=raw_text,
            )
            self.session.add(protocol)

        self.session.commit()

        # Add sections
        for section in parsed_protocol.sections:
            db_section = ProtocolSection(
                protocol_id=protocol.id,
                section_type=section.section_type.value,
                section_title=section.title,
                content=section.content,
                page_start=section.page_start,
                page_end=section.page_end,
            )
            self.session.add(db_section)

        self.session.commit()
        return protocol

    def get_protocol_sections(
        self, nct_id: str, section_type: Optional[str] = None
    ) -> list[ProtocolSection]:
        """Get protocol sections for a trial."""
        trial = self.get_trial_by_nct(nct_id)
        if not trial:
            return []

        query = (
            self.session.query(ProtocolSection)
            .join(Protocol)
            .filter(Protocol.trial_id == trial.id)
        )

        if section_type:
            query = query.filter(ProtocolSection.section_type == section_type)

        return query.all()

    # SAP operations
    def save_sap(
        self,
        trial: Trial,
        generated_content: str,
        sections: dict[str, str],
        file_path: Optional[str] = None,
    ) -> SAP:
        """Save generated SAP."""
        sap = SAP(
            trial_id=trial.id,
            file_path=file_path,
            generated_sap=generated_content,
        )
        self.session.add(sap)
        self.session.commit()

        # Add sections
        for section_type, content in sections.items():
            db_section = SAPSection(
                sap_id=sap.id,
                section_type=section_type,
                content=content,
            )
            self.session.add(db_section)

        self.session.commit()
        return sap

    def get_sap_by_nct(self, nct_id: str) -> Optional[SAP]:
        """Get generated SAP for a trial."""
        trial = self.get_trial_by_nct(nct_id)
        if not trial:
            return None
        return self.session.query(SAP).filter_by(trial_id=trial.id).first()

    # Utility methods
    def get_statistics(self) -> dict:
        """Get database statistics."""
        return {
            "trials": self.session.query(Trial).count(),
            "protocols": self.session.query(Protocol).count(),
            "protocol_sections": self.session.query(ProtocolSection).count(),
            "saps": self.session.query(SAP).count(),
        }


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table

    console = Console()
    db = DatabaseOperations()

    stats = db.get_statistics()

    table = Table(title="Database Statistics")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", style="green")

    for entity, count in stats.items():
        table.add_row(entity, str(count))

    console.print(table)
    db.close()

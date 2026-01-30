"""SQLAlchemy models for clinical trial database."""
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base, sessionmaker

from src.config import DATABASE_URL

Base = declarative_base()


class Trial(Base):
    """Clinical trial metadata."""
    __tablename__ = "trials"

    id = Column(Integer, primary_key=True)
    nct_id = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(Text)
    phase = Column(String(50))
    condition = Column(String(200))
    sponsor = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    protocols = relationship("Protocol", back_populates="trial", cascade="all, delete-orphan")
    saps = relationship("SAP", back_populates="trial", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Trial(nct_id='{self.nct_id}', title='{self.title[:50] if self.title else ''}...')>"


class Protocol(Base):
    """Protocol document and extracted text."""
    __tablename__ = "protocols"

    id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey("trials.id"), nullable=False)
    file_path = Column(String(500))
    raw_text = Column(Text)
    parsed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trial = relationship("Trial", back_populates="protocols")
    sections = relationship("ProtocolSection", back_populates="protocol", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Protocol(id={self.id}, trial_id={self.trial_id})>"


class ProtocolSection(Base):
    """Parsed section from a protocol."""
    __tablename__ = "protocol_sections"

    id = Column(Integer, primary_key=True)
    protocol_id = Column(Integer, ForeignKey("protocols.id"), nullable=False)
    section_type = Column(String(50), nullable=False, index=True)
    section_title = Column(Text)
    content = Column(Text)
    page_start = Column(Integer)
    page_end = Column(Integer)

    # Relationships
    protocol = relationship("Protocol", back_populates="sections")

    def __repr__(self):
        return f"<ProtocolSection(type='{self.section_type}', title='{self.section_title[:30] if self.section_title else ''}...')>"


class SAP(Base):
    """Statistical Analysis Plan."""
    __tablename__ = "saps"

    id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey("trials.id"), nullable=False)
    file_path = Column(String(500))  # Original SAP file path
    generated_sap = Column(Text)  # Generated abbreviated SAP
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trial = relationship("Trial", back_populates="saps")
    sections = relationship("SAPSection", back_populates="sap", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SAP(id={self.id}, trial_id={self.trial_id})>"


class SAPSection(Base):
    """Section of a generated SAP."""
    __tablename__ = "sap_sections"

    id = Column(Integer, primary_key=True)
    sap_id = Column(Integer, ForeignKey("saps.id"), nullable=False)
    section_type = Column(String(50), nullable=False)
    content = Column(Text)

    # Relationships
    sap = relationship("SAP", back_populates="sections")

    def __repr__(self):
        return f"<SAPSection(type='{self.section_type}')>"


# Engine and session factory
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)


def get_session():
    """Get a new database session."""
    return SessionLocal()


if __name__ == "__main__":
    from rich.console import Console
    console = Console()

    console.print("[blue]Initializing database...[/blue]")
    init_db()
    console.print(f"[green]Database created at: {DATABASE_URL}[/green]")

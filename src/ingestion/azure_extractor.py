"""Azure Document Intelligence extractor for production PDF processing."""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

console = Console()


@dataclass
class ExtractedTable:
    """Extracted table from document."""
    page_number: int
    row_count: int
    column_count: int
    cells: list[dict]  # [{row, col, content, is_header}]

    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        if not self.cells:
            return ""

        # Build grid
        grid = {}
        for cell in self.cells:
            grid[(cell["row"], cell["col"])] = cell["content"]

        rows = []
        for r in range(self.row_count):
            row = []
            for c in range(self.column_count):
                row.append(grid.get((r, c), ""))
            rows.append("| " + " | ".join(row) + " |")

            # Add header separator after first row
            if r == 0:
                rows.append("|" + "|".join(["---"] * self.column_count) + "|")

        return "\n".join(rows)


@dataclass
class ExtractedSection:
    """Extracted section with hierarchy."""
    level: int  # 1 = h1, 2 = h2, etc.
    title: str
    content: str
    page_start: int
    page_end: int
    tables: list[ExtractedTable] = field(default_factory=list)


@dataclass
class AzureExtractionResult:
    """Complete extraction result from Azure DI."""
    file_path: str
    total_pages: int
    sections: list[ExtractedSection] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
    raw_text: str = ""
    key_value_pairs: dict = field(default_factory=dict)

    def get_full_text(self) -> str:
        """Get all text content."""
        return self.raw_text

    def get_section_by_title(self, title_pattern: str) -> Optional[ExtractedSection]:
        """Find section by title pattern."""
        import re
        pattern = re.compile(title_pattern, re.IGNORECASE)
        for section in self.sections:
            if pattern.search(section.title):
                return section
        return None


class AzureDocumentExtractor:
    """Extract structured content from PDFs using Azure Document Intelligence."""

    def __init__(self, endpoint: str = None, key: str = None):
        self.endpoint = endpoint or os.environ.get("AZURE_DI_ENDPOINT")
        self.key = key or os.environ.get("AZURE_DI_KEY")
        self.client = None

        if self.endpoint and self.key:
            self._init_client()
        else:
            console.print("[yellow]Azure DI credentials not set, using fallback[/yellow]")

    def _init_client(self):
        """Initialize Azure Document Intelligence client."""
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential

            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key)
            )
            console.print("[green]Azure Document Intelligence client initialized[/green]")
        except ImportError:
            console.print("[yellow]azure-ai-documentintelligence not installed[/yellow]")
            console.print("Install with: pip install azure-ai-documentintelligence")

    def extract(self, pdf_path: Path, model_id: str = "prebuilt-layout") -> Optional[AzureExtractionResult]:
        """Extract structured content from PDF using Azure DI.

        Args:
            pdf_path: Path to PDF file
            model_id: Azure DI model to use:
                - "prebuilt-document": General document extraction
                - "prebuilt-layout": Better for complex layouts/tables
                - "prebuilt-read": OCR-focused extraction

        Returns:
            AzureExtractionResult with structured content
        """
        if not self.client:
            console.print("[red]Azure DI client not available[/red]")
            return None

        if not pdf_path.exists():
            console.print(f"[red]File not found: {pdf_path}[/red]")
            return None

        try:
            console.print(f"[blue]Analyzing {pdf_path.name} with Azure DI...[/blue]")

            with open(pdf_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    model_id=model_id,
                    body=f,
                    content_type="application/pdf"
                )

            result = poller.result()
            return self._parse_result(result, str(pdf_path))

        except Exception as e:
            console.print(f"[red]Azure DI extraction failed: {e}[/red]")
            return None

    def _parse_result(self, result, file_path: str) -> AzureExtractionResult:
        """Parse Azure DI result into structured format."""
        extraction = AzureExtractionResult(
            file_path=file_path,
            total_pages=len(result.pages) if result.pages else 0,
        )

        # Extract raw text
        if result.content:
            extraction.raw_text = result.content

        # Extract tables
        if result.tables:
            for table in result.tables:
                cells = []
                for cell in table.cells:
                    cells.append({
                        "row": cell.row_index,
                        "col": cell.column_index,
                        "content": cell.content or "",
                        "is_header": getattr(cell, "kind", "") == "columnHeader"
                    })

                extraction.tables.append(ExtractedTable(
                    page_number=table.bounding_regions[0].page_number if table.bounding_regions else 0,
                    row_count=table.row_count,
                    column_count=table.column_count,
                    cells=cells
                ))

        # Extract key-value pairs
        if result.key_value_pairs:
            for kv in result.key_value_pairs:
                if kv.key and kv.value:
                    key_text = kv.key.content if kv.key.content else ""
                    value_text = kv.value.content if kv.value.content else ""
                    if key_text:
                        extraction.key_value_pairs[key_text] = value_text

        # Extract sections from paragraphs with roles
        if result.paragraphs:
            current_section = None
            current_content = []

            for para in result.paragraphs:
                role = getattr(para, "role", None)
                content = para.content or ""
                page = para.bounding_regions[0].page_number if para.bounding_regions else 1

                if role in ["title", "sectionHeading"]:
                    # Save previous section
                    if current_section:
                        current_section.content = "\n".join(current_content)
                        extraction.sections.append(current_section)

                    # Start new section
                    level = 1 if role == "title" else 2
                    current_section = ExtractedSection(
                        level=level,
                        title=content,
                        content="",
                        page_start=page,
                        page_end=page
                    )
                    current_content = []
                else:
                    current_content.append(content)
                    if current_section:
                        current_section.page_end = page

            # Save last section
            if current_section:
                current_section.content = "\n".join(current_content)
                extraction.sections.append(current_section)

        console.print(f"[green]Extracted {len(extraction.sections)} sections, {len(extraction.tables)} tables[/green]")
        return extraction

    def extract_to_json(self, pdf_path: Path, output_path: Path) -> bool:
        """Extract PDF and save as structured JSON."""
        result = self.extract(pdf_path)
        if not result:
            return False

        try:
            output_data = {
                "file_path": result.file_path,
                "total_pages": result.total_pages,
                "sections": [
                    {
                        "level": s.level,
                        "title": s.title,
                        "content": s.content[:1000] + "..." if len(s.content) > 1000 else s.content,
                        "page_start": s.page_start,
                        "page_end": s.page_end
                    }
                    for s in result.sections
                ],
                "tables": [
                    {
                        "page": t.page_number,
                        "rows": t.row_count,
                        "cols": t.column_count,
                        "markdown": t.to_markdown()[:500]
                    }
                    for t in result.tables
                ],
                "key_value_pairs": result.key_value_pairs
            }

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)

            console.print(f"[green]Saved to {output_path}[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to save JSON: {e}[/red]")
            return False


# Fallback to pdfplumber if Azure DI not available
class HybridExtractor:
    """Hybrid extractor that uses Azure DI when available, falls back to pdfplumber."""

    def __init__(self):
        self.azure = AzureDocumentExtractor()
        self.use_azure = self.azure.client is not None

        if not self.use_azure:
            from src.ingestion.pdf_extractor import PDFExtractor
            self.pdfplumber = PDFExtractor()

    def extract(self, pdf_path: Path) -> AzureExtractionResult:
        """Extract using best available method."""
        if self.use_azure:
            result = self.azure.extract(pdf_path)
            if result:
                return result

        # Fallback to pdfplumber
        console.print("[yellow]Using pdfplumber fallback[/yellow]")
        from src.ingestion.pdf_extractor import PDFExtractor
        extractor = PDFExtractor()
        content = extractor.extract(pdf_path)

        if not content:
            return None

        # Convert to Azure-compatible format
        return AzureExtractionResult(
            file_path=str(pdf_path),
            total_pages=content.total_pages,
            raw_text=content.full_text,
            sections=[],
            tables=[]
        )

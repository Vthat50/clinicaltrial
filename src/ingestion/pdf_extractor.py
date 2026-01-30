"""Extract text from PDF files."""
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
from rich.console import Console

console = Console()


@dataclass
class PageContent:
    """Content from a single PDF page."""
    page_num: int
    text: str
    tables: list = field(default_factory=list)


@dataclass
class PDFContent:
    """Full extracted content from a PDF."""
    file_path: str
    total_pages: int
    pages: list[PageContent] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Get all text combined."""
        return "\n\n".join(page.text for page in self.pages)

    def get_page_range(self, start: int, end: int) -> str:
        """Get text from a range of pages (1-indexed)."""
        return "\n\n".join(
            page.text for page in self.pages
            if start <= page.page_num <= end
        )


class PDFExtractor:
    """Extract text and tables from PDF files."""

    def __init__(self):
        self.console = Console()

    def extract(self, pdf_path: Path) -> Optional[PDFContent]:
        """Extract text and tables from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            PDFContent object with extracted data
        """
        if not pdf_path.exists():
            self.console.print(f"[red]File not found: {pdf_path}[/red]")
            return None

        try:
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                for i, page in enumerate(pdf.pages, 1):
                    # Extract text
                    text = page.extract_text() or ""
                    text = self._clean_text(text)

                    # Extract tables
                    tables = []
                    try:
                        raw_tables = page.extract_tables()
                        for table in raw_tables:
                            if table:
                                tables.append(table)
                    except Exception:
                        pass  # Some pages may not have valid tables

                    pages.append(PageContent(
                        page_num=i,
                        text=text,
                        tables=tables
                    ))

            return PDFContent(
                file_path=str(pdf_path),
                total_pages=total_pages,
                pages=pages
            )

        except Exception as e:
            self.console.print(f"[red]Error extracting {pdf_path}: {e}[/red]")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Fix common OCR/extraction issues
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)  # Fix hyphenation
        text = text.replace('\x00', '')  # Remove null bytes

        # Restore paragraph breaks at likely locations
        text = re.sub(r'\.(\s+)([A-Z])', r'.\n\n\2', text)

        return text.strip()

    def extract_to_file(self, pdf_path: Path, output_path: Path) -> bool:
        """Extract PDF text and save to a text file.

        Args:
            pdf_path: Path to the PDF file
            output_path: Path to save the text file

        Returns:
            True if successful
        """
        content = self.extract(pdf_path)
        if not content:
            return False

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Source: {pdf_path.name}\n")
                f.write(f"Total Pages: {content.total_pages}\n")
                f.write("=" * 80 + "\n\n")

                for page in content.pages:
                    f.write(f"\n--- Page {page.page_num} ---\n\n")
                    f.write(page.text)
                    f.write("\n")

            return True
        except Exception as e:
            self.console.print(f"[red]Error saving to {output_path}: {e}[/red]")
            return False


if __name__ == "__main__":
    # Test extraction
    from src.config import PROTOCOLS_DIR, PROCESSED_DIR

    extractor = PDFExtractor()
    for pdf_file in PROTOCOLS_DIR.glob("*.pdf"):
        console.print(f"[blue]Extracting {pdf_file.name}...[/blue]")
        output_file = PROCESSED_DIR / f"{pdf_file.stem}.txt"
        if extractor.extract_to_file(pdf_file, output_file):
            console.print(f"[green]Saved to {output_file}[/green]")

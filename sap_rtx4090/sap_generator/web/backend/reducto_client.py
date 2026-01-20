"""
Reducto API client for Schedule of Assessments (SOA) table extraction.

Reducto provides superior table extraction for complex clinical protocol tables.
This module handles:
1. Uploading PDF to Reducto with specific page ranges
2. Parsing tables with markdown output
3. Formatting results for integration with LlamaParse output
"""

import os
import tempfile
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Reducto client - lazy loaded
REDUCTO_AVAILABLE = False
_reducto_client = None


def get_reducto_client():
    """Lazy-load Reducto client to avoid startup overhead."""
    global REDUCTO_AVAILABLE, _reducto_client

    if _reducto_client is not None:
        return _reducto_client

    api_key = os.getenv("REDUCTO_API_KEY")
    if not api_key:
        print("[Reducto] REDUCTO_API_KEY not set")
        return None

    try:
        from reducto import Reducto
        _reducto_client = Reducto(api_key=api_key)
        REDUCTO_AVAILABLE = True
        print("[Reducto] Client initialized successfully")
        return _reducto_client
    except ImportError:
        print("[Reducto] Package not installed. Run: pip install reducto")
        return None
    except Exception as e:
        print(f"[Reducto] Initialization failed: {e}")
        return None


@dataclass
class ReductoResult:
    """Result from Reducto SOA extraction."""
    success: bool
    pages_processed: List[int]
    content: str  # Extracted table content in markdown
    raw_blocks: List[Dict[str, Any]]  # Raw block data for debugging
    credits_used: float
    error: Optional[str] = None


def extract_soa_with_reducto(file_content: bytes, page_numbers: List[int]) -> ReductoResult:
    """
    Extract SOA tables from specific pages using Reducto API.

    Args:
        file_content: PDF file as bytes
        page_numbers: List of 1-indexed page numbers to process

    Returns:
        ReductoResult with extracted content or error
    """
    client = get_reducto_client()
    if not client:
        return ReductoResult(
            success=False,
            pages_processed=[],
            content="",
            raw_blocks=[],
            credits_used=0,
            error="Reducto client not available. Set REDUCTO_API_KEY environment variable."
        )

    if not page_numbers:
        return ReductoResult(
            success=False,
            pages_processed=[],
            content="",
            raw_blocks=[],
            credits_used=0,
            error="No pages specified for extraction"
        )

    try:
        # Write PDF to temp file for upload
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            print(f"[Reducto] Uploading PDF for pages {page_numbers}...")

            # Upload to Reducto
            upload = client.upload(file=Path(tmp_path))
            print(f"[Reducto] Upload complete: {upload.file_id}")

            # Build page range configuration
            # Reducto uses 1-indexed pages
            page_ranges = _pages_to_ranges(page_numbers)
            print(f"[Reducto] Page ranges: {page_ranges}")

            # Parse with page range restriction
            # Request markdown format for tables
            result = client.parse.run(
                input=upload.file_id,
                settings={
                    "page_range": page_ranges,
                    "table_output_format": "md",  # Markdown format for tables
                }
            )

            print(f"[Reducto] Parse complete")

            # Process results into formatted content
            content, raw_blocks = _format_reducto_output(result, page_numbers)

            # Get credits used if available
            credits_used = 0
            if hasattr(result, 'usage') and result.usage:
                credits_used = getattr(result.usage, 'num_pages', len(page_numbers))

            print(f"[Reducto] Extracted {len(content):,} chars from {len(page_numbers)} pages")

            return ReductoResult(
                success=True,
                pages_processed=page_numbers,
                content=content,
                raw_blocks=raw_blocks,
                credits_used=credits_used
            )

        finally:
            # Cleanup temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

    except Exception as e:
        print(f"[Reducto] Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return ReductoResult(
            success=False,
            pages_processed=[],
            content="",
            raw_blocks=[],
            credits_used=0,
            error=str(e)
        )


def _pages_to_ranges(pages: List[int]) -> List[Dict[str, int]]:
    """
    Convert list of page numbers to Reducto page_range format.

    Args:
        pages: List of 1-indexed page numbers

    Returns:
        List of {"start": N, "end": M} dicts for consecutive ranges
    """
    if not pages:
        return []

    pages = sorted(set(pages))
    ranges = []
    start = end = pages[0]

    for page in pages[1:]:
        if page == end + 1:
            end = page
        else:
            ranges.append({"start": start, "end": end})
            start = end = page

    ranges.append({"start": start, "end": end})
    return ranges


def _format_reducto_output(result, page_numbers: List[int]) -> tuple:
    """
    Format Reducto parse result into markdown content with [TABLE] markers.

    Args:
        result: Reducto parse result object
        page_numbers: Pages that were processed (original page numbers)

    Returns:
        Tuple of (formatted_content, raw_blocks)
    """
    content_parts = []
    raw_blocks = []

    # Reducto renumbers pages starting from 1 in the extracted subset
    # Map relative page (1-indexed in subset) to actual page number
    sorted_pages = sorted(page_numbers)

    def get_actual_page(relative_page: int) -> int:
        """Convert Reducto's relative page number to actual PDF page."""
        if relative_page and 1 <= relative_page <= len(sorted_pages):
            return sorted_pages[relative_page - 1]
        return relative_page

    try:
        # Reducto returns chunks with blocks
        # Each block has a type (Table, Text, Header, etc.) and content
        if hasattr(result, 'result') and hasattr(result.result, 'chunks'):
            for chunk in result.result.chunks:
                if hasattr(chunk, 'blocks'):
                    for block in chunk.blocks:
                        relative_page = None
                        if hasattr(block, 'bbox') and hasattr(block.bbox, 'page'):
                            relative_page = block.bbox.page

                        actual_page = get_actual_page(relative_page) if relative_page else None

                        block_dict = {
                            "type": getattr(block, 'type', 'Unknown'),
                            "content": getattr(block, 'content', ''),
                            "page": actual_page,
                        }
                        raw_blocks.append(block_dict)

                        block_type = getattr(block, 'type', '')
                        block_content = getattr(block, 'content', '')

                        if block_type == "Table":
                            # Wrap tables in markers for frontend rendering
                            page_info = f" (Page {actual_page})" if actual_page else ""
                            content_parts.append(
                                f"\n[TABLE]{page_info}\n{block_content}\n[/TABLE]\n"
                            )
                        elif block_type in ["Text", "Header", "Title"]:
                            # Include text/headers for context
                            content_parts.append(block_content)

        # Alternative structure - direct blocks array
        elif hasattr(result, 'blocks'):
            for block in result.blocks:
                block_dict = {
                    "type": getattr(block, 'type', 'Unknown'),
                    "content": getattr(block, 'content', ''),
                }
                raw_blocks.append(block_dict)

                if getattr(block, 'type', '') == "Table":
                    content_parts.append(
                        f"\n[TABLE]\n{block.content}\n[/TABLE]\n"
                    )
                else:
                    content_parts.append(getattr(block, 'content', ''))

    except Exception as e:
        print(f"[Reducto] Error formatting output: {e}")
        # Return raw result as string if parsing fails
        return str(result), []

    return "\n".join(content_parts), raw_blocks


def check_reducto_available() -> Dict[str, Any]:
    """
    Check if Reducto is available and configured.

    Returns:
        Dict with availability status and configuration info
    """
    api_key = os.getenv("REDUCTO_API_KEY")
    has_key = bool(api_key)

    # Try to import
    try:
        from reducto import Reducto
        can_import = True
    except ImportError:
        can_import = False

    # Try to initialize client
    client = get_reducto_client() if has_key and can_import else None

    return {
        "available": client is not None,
        "has_api_key": has_key,
        "can_import": can_import,
        "api_key_preview": f"{api_key[:8]}..." if api_key and len(api_key) > 8 else None,
    }

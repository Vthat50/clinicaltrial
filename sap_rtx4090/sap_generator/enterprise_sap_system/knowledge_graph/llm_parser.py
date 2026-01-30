"""
LLM Parser - Robust JSON parsing for LLM responses
===================================================

Shared parser for both workbench and quick protocol generation.
Handles common LLM JSON output issues with automatic repair and retry.

Author: SAP Generation System
Version: v92
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass


@dataclass
class ParseResult:
    """Result of parsing attempt."""
    success: bool
    data: Optional[Dict]
    error: Optional[str] = None
    repairs_applied: List[str] = None
    retried_with_llm: bool = False

    def __post_init__(self):
        if self.repairs_applied is None:
            self.repairs_applied = []


class LLMParser:
    """
    Robust JSON parser for LLM responses.

    Features:
    - Strips markdown code blocks
    - Fixes common JSON syntax errors
    - Retries with Claude for malformed JSON
    - Schema validation (optional)
    - Truncation detection and recovery
    """

    def __init__(self, client=None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize parser.

        Args:
            client: Anthropic client for retry requests (optional)
            model: Model to use for JSON repair retries
        """
        self.client = client
        self.model = model

    def parse(
        self,
        response_text: str,
        schema: Optional[Dict] = None,
        retry_with_llm: bool = True,
        context: str = ""
    ) -> ParseResult:
        """
        Parse LLM response text as JSON with automatic repair.

        Args:
            response_text: Raw text from LLM response
            schema: Optional JSON schema for validation
            retry_with_llm: Whether to retry with Claude if parsing fails
            context: Context about what was being extracted (for retry prompt)

        Returns:
            ParseResult with success status, data, and any repairs applied
        """
        if not response_text:
            return ParseResult(success=False, data=None, error="Empty response")

        repairs = []
        text = response_text.strip()

        # Step 1: Strip markdown code blocks
        text, stripped = self._strip_markdown(text)
        if stripped:
            repairs.append("stripped_markdown")

        # Step 2: Try direct parse
        try:
            data = json.loads(text)
            result = ParseResult(success=True, data=data, repairs_applied=repairs)
            if schema:
                validation_error = self._validate_schema(data, schema)
                if validation_error:
                    result.error = f"Schema validation: {validation_error}"
            return result
        except json.JSONDecodeError as e:
            original_error = str(e)

        # Step 3: Apply automatic repairs
        text, repair_list = self._apply_repairs(text)
        repairs.extend(repair_list)

        # Step 4: Try parse after repairs
        try:
            data = json.loads(text)
            result = ParseResult(success=True, data=data, repairs_applied=repairs)
            if schema:
                validation_error = self._validate_schema(data, schema)
                if validation_error:
                    result.error = f"Schema validation: {validation_error}"
            return result
        except json.JSONDecodeError as e:
            repair_error = str(e)

        # Step 5: Check for truncation
        if self._is_truncated(text):
            repairs.append("detected_truncation")
            text = self._attempt_truncation_recovery(text)
            try:
                data = json.loads(text)
                repairs.append("recovered_from_truncation")
                return ParseResult(success=True, data=data, repairs_applied=repairs)
            except json.JSONDecodeError:
                pass

        # Step 6: Retry with LLM if available
        if retry_with_llm and self.client:
            repaired_text = self._retry_with_llm(response_text, original_error, context)
            if repaired_text:
                try:
                    data = json.loads(repaired_text)
                    repairs.append("llm_repair")
                    return ParseResult(
                        success=True,
                        data=data,
                        repairs_applied=repairs,
                        retried_with_llm=True
                    )
                except json.JSONDecodeError:
                    pass

        # All attempts failed
        return ParseResult(
            success=False,
            data=None,
            error=f"Failed to parse JSON: {original_error}",
            repairs_applied=repairs
        )

    def _strip_markdown(self, text: str) -> Tuple[str, bool]:
        """Strip markdown code block wrappers."""
        original = text

        # Handle ```json ... ```
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```JSON"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()
        return text, text != original

    def _apply_repairs(self, text: str) -> Tuple[str, List[str]]:
        """Apply common JSON syntax repairs."""
        repairs = []
        original = text

        # Fix 1: Trailing commas before } or ]
        # e.g., {"a": 1,} -> {"a": 1}
        pattern = r',(\s*[}\]])'
        if re.search(pattern, text):
            text = re.sub(pattern, r'\1', text)
            repairs.append("removed_trailing_commas")

        # Fix 2: Single quotes to double quotes (careful with apostrophes)
        # Only if the text doesn't parse and uses single quotes for keys/values
        if "'" in text and '"' not in text[:100]:
            # Likely using single quotes throughout
            text = self._convert_single_quotes(text)
            repairs.append("converted_single_quotes")

        # Fix 3: Unquoted keys
        # e.g., {name: "value"} -> {"name": "value"}
        pattern = r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)'
        if re.search(pattern, text):
            text = re.sub(pattern, r'\1"\2"\3', text)
            repairs.append("quoted_keys")

        # Fix 4: JavaScript comments
        # Remove // comments
        if '//' in text:
            text = re.sub(r'//[^\n]*', '', text)
            repairs.append("removed_line_comments")
        # Remove /* */ comments
        if '/*' in text:
            text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
            repairs.append("removed_block_comments")

        # Fix 5: Newlines in strings
        # Replace literal newlines in strings with \n
        # This is tricky - only do if we detect the pattern

        # Fix 6: NaN, Infinity, undefined -> null
        text = re.sub(r'\bNaN\b', 'null', text)
        text = re.sub(r'\bInfinity\b', 'null', text)
        text = re.sub(r'\bundefined\b', 'null', text)
        if text != original and "replaced_js_values" not in repairs:
            repairs.append("replaced_js_values")

        # Fix 7: Control characters
        # Remove non-printable characters except \n, \r, \t
        cleaned = ''.join(c if c.isprintable() or c in '\n\r\t' else '' for c in text)
        if cleaned != text:
            text = cleaned
            repairs.append("removed_control_chars")

        return text, repairs

    def _convert_single_quotes(self, text: str) -> str:
        """Carefully convert single quotes to double quotes."""
        result = []
        in_string = False
        string_char = None
        i = 0

        while i < len(text):
            c = text[i]

            if not in_string:
                if c == '"':
                    in_string = True
                    string_char = '"'
                    result.append(c)
                elif c == "'":
                    # Start of single-quoted string - convert to double
                    in_string = True
                    string_char = "'"
                    result.append('"')
                else:
                    result.append(c)
            else:
                if c == '\\' and i + 1 < len(text):
                    # Escape sequence
                    result.append(c)
                    result.append(text[i + 1])
                    i += 1
                elif c == string_char:
                    # End of string
                    in_string = False
                    result.append('"' if string_char == "'" else c)
                elif c == '"' and string_char == "'":
                    # Double quote inside single-quoted string - escape it
                    result.append('\\"')
                else:
                    result.append(c)
            i += 1

        return ''.join(result)

    def _is_truncated(self, text: str) -> bool:
        """Check if JSON appears to be truncated."""
        text = text.strip()

        # Count brackets
        open_braces = text.count('{')
        close_braces = text.count('}')
        open_brackets = text.count('[')
        close_brackets = text.count(']')

        # If significantly unbalanced, likely truncated
        if open_braces > close_braces + 2:
            return True
        if open_brackets > close_brackets + 2:
            return True

        # Check for obvious truncation patterns
        if text.endswith(','):
            return True
        if text.endswith(':'):
            return True
        if text.endswith('"') and not text.endswith('""'):
            # Could be mid-string
            if text.count('"') % 2 != 0:
                return True

        return False

    def _attempt_truncation_recovery(self, text: str) -> str:
        """Attempt to close truncated JSON."""
        text = text.rstrip()

        # Remove trailing incomplete elements
        if text.endswith(','):
            text = text[:-1]
        if text.endswith(':'):
            # Incomplete key-value, remove the key too
            text = re.sub(r',?\s*"[^"]*"\s*:$', '', text)

        # Close open brackets/braces
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        # Add closing brackets in reverse order of opening
        # This is a simple heuristic - may not always be correct
        for _ in range(open_brackets):
            text += ']'
        for _ in range(open_braces):
            text += '}'

        return text

    def _retry_with_llm(self, original: str, error: str, context: str) -> Optional[str]:
        """Ask Claude to fix malformed JSON."""
        if not self.client:
            return None

        prompt = f"""The following JSON response has a syntax error. Please fix it and return ONLY valid JSON.

Error: {error}

Context: {context if context else "Extracting structured data from a clinical trial protocol"}

Malformed JSON:
```
{original[:8000]}
```

Return ONLY the corrected JSON, no explanation:"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()
            text, _ = self._strip_markdown(text)
            return text

        except Exception as e:
            print(f"[LLMParser] Retry failed: {e}")
            return None

    def _validate_schema(self, data: Dict, schema: Dict) -> Optional[str]:
        """Basic schema validation - check required fields exist."""
        if "required" not in schema:
            return None

        missing = []
        for field in schema.get("required", []):
            if field not in data:
                missing.append(field)

        if missing:
            return f"Missing required fields: {', '.join(missing)}"

        return None


# Convenience function for simple usage
def parse_llm_json(
    response_text: str,
    client=None,
    retry: bool = True,
    context: str = ""
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Simple function to parse LLM JSON response.

    Args:
        response_text: Raw LLM response
        client: Anthropic client for retry (optional)
        retry: Whether to retry with LLM on failure
        context: Context for retry prompt

    Returns:
        Tuple of (parsed_data, error_message)
        If successful, error_message is None
        If failed, parsed_data is None
    """
    parser = LLMParser(client=client)
    result = parser.parse(response_text, retry_with_llm=retry, context=context)

    if result.success:
        if result.repairs_applied:
            print(f"[LLMParser] Applied repairs: {', '.join(result.repairs_applied)}")
        return result.data, None
    else:
        return None, result.error

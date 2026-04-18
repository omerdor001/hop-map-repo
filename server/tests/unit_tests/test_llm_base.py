"""Unit tests for LLMProvider._parse_response().

All tests operate on the static helper directly — no subclass, no network,
no external dependencies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure server/ is on sys.path so llm/ can be imported.
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from llm.base import LLMProvider


class TestParseResponseValid:
    """Happy-path cases — well-formed model output."""

    def test_plain_json_parsed_correctly(self):
        raw = '{"decision": "YES", "confidence": 85, "reason": "discord link"}'
        result = LLMProvider._parse_response(raw)
        assert result["decision"] == "YES"
        assert result["confidence"] == 85
        assert result["reason"] == "discord link"

    def test_no_decision_not_in_allowed_set(self):
        # decision must be uppercased whatever the model returns
        raw = '{"decision": "yes", "confidence": 70, "reason": "test"}'
        result = LLMProvider._parse_response(raw)
        assert result["decision"] == "YES"

    def test_no_decision_returns_no(self):
        raw = '{"confidence": 50, "reason": "no decision field"}'
        result = LLMProvider._parse_response(raw)
        assert result["decision"] == "NO"

    def test_markdown_fenced_json_stripped(self):
        raw = "```json\n{\"decision\": \"NO\", \"confidence\": 10, \"reason\": \"ok\"}\n```"
        result = LLMProvider._parse_response(raw)
        assert result["decision"] == "NO"
        assert result["confidence"] == 10

    def test_markdown_fence_without_language_tag_stripped(self):
        raw = "```\n{\"decision\": \"YES\", \"confidence\": 99, \"reason\": \"bad\"}\n```"
        result = LLMProvider._parse_response(raw)
        assert result["decision"] == "YES"

    def test_confidence_clamped_above_100(self):
        raw = '{"decision": "YES", "confidence": 999, "reason": "overflow"}'
        result = LLMProvider._parse_response(raw)
        assert result["confidence"] == 100

    def test_confidence_clamped_below_0(self):
        raw = '{"decision": "NO", "confidence": -50, "reason": "underflow"}'
        result = LLMProvider._parse_response(raw)
        assert result["confidence"] == 0

    def test_missing_confidence_defaults_to_50(self):
        raw = '{"decision": "NO", "reason": "test"}'
        result = LLMProvider._parse_response(raw)
        assert result["confidence"] == 50

    def test_missing_reason_defaults_to_empty_string(self):
        raw = '{"decision": "YES", "confidence": 80}'
        result = LLMProvider._parse_response(raw)
        assert result["reason"] == ""

    def test_reason_is_stripped_of_whitespace(self):
        raw = '{"decision": "YES", "confidence": 80, "reason": "  bad link  "}'
        result = LLMProvider._parse_response(raw)
        assert result["reason"] == "bad link"

    def test_whitespace_around_json_ignored(self):
        raw = '\n\n  {"decision": "NO", "confidence": 0, "reason": "clean"}  \n'
        result = LLMProvider._parse_response(raw)
        assert result["decision"] == "NO"


class TestParseResponseInvalid:
    """Error cases — malformed or non-JSON model output."""

    def test_non_json_raises_json_decode_error(self):
        with pytest.raises(json.JSONDecodeError):
            LLMProvider._parse_response("Not JSON at all.")

    def test_empty_string_raises_json_decode_error(self):
        with pytest.raises(json.JSONDecodeError):
            LLMProvider._parse_response("")

    def test_partial_json_raises_json_decode_error(self):
        with pytest.raises(json.JSONDecodeError):
            LLMProvider._parse_response('{"decision": "YES"')

    def test_array_instead_of_object_raises_type_error_or_attribute_error(self):
        # json.loads succeeds but .get() on a list raises AttributeError
        with pytest.raises((AttributeError, TypeError, json.JSONDecodeError, ValueError)):
            LLMProvider._parse_response('[1, 2, 3]')

    def test_markdown_fence_with_garbage_inside_raises(self):
        raw = "```json\nnot valid json\n```"
        with pytest.raises(json.JSONDecodeError):
            LLMProvider._parse_response(raw)

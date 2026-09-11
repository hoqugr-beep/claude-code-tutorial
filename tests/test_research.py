"""Tests for the research layer's honesty guarantees.

The fixtures below are trimmed from real ``claude --print`` traces captured
while building this tool, including one run that produced a confident,
specific, source-looking claim without ever searching the web. That run is
the reason this layer verifies the execution trace instead of the text.
"""

import unittest

from stockcast.errors import ResearchError
from stockcast.research import (
    Catalyst,
    ResearchResult,
    _parse_catalysts,
    build_prompt,
    count_searches,
    extract_json,
)

# A real fabricated run: fluent prose, a plausible URL, zero tool calls.
FABRICATED_TRACE = [
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Oracle (ORCL) reported record Q1 FY2027 revenue of "
                        "$19.35 billion.\n\nSource: "
                        "https://finance.yahoo.com/quote/ORCL/news/"
                    ),
                }
            ]
        },
    },
    {"type": "result", "result": "...", "is_error": False, "permission_denials": []},
]

GENUINE_TRACE = [
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "WebSearch",
                 "input": {"query": "ORCL Q1 FY2027 earnings"}}
            ]
        },
    },
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "WebFetch",
                 "input": {"url": "https://example.com/orcl-earnings"}}
            ]
        },
    },
    {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "```json\n{}\n```"}]},
    },
]


class TestSearchVerification(unittest.TestCase):
    def test_fabricated_run_counts_zero_searches(self):
        count, queries = count_searches(FABRICATED_TRACE)
        self.assertEqual(count, 0)
        self.assertEqual(queries, [])

    def test_genuine_run_counts_its_searches(self):
        count, queries = count_searches(GENUINE_TRACE)
        self.assertEqual(count, 2)
        self.assertIn("ORCL Q1 FY2027 earnings", queries)

    def test_unrelated_tools_do_not_count_as_research(self):
        trace = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"cmd": "ls"}},
                        {"type": "tool_use", "name": "Read", "input": {"f": "a.txt"}},
                    ]
                },
            }
        ]
        self.assertEqual(count_searches(trace)[0], 0)

    def test_tolerates_malformed_events(self):
        for trace in ([{}], [{"type": "assistant"}],
                      [{"type": "assistant", "message": {"content": None}}]):
            self.assertEqual(count_searches(trace)[0], 0)


class TestVerifiedFlag(unittest.TestCase):
    def test_zero_searches_is_never_verified(self):
        self.assertFalse(ResearchResult("ORCL", searches_performed=0).verified)

    def test_searches_make_it_verified(self):
        self.assertTrue(ResearchResult("ORCL", searches_performed=3).verified)


class TestJsonExtraction(unittest.TestCase):
    def test_fenced_block(self):
        self.assertEqual(
            extract_json('chat\n```json\n{"confidence": 0.4}\n```\nbye'),
            {"confidence": 0.4},
        )

    def test_unfenced_object(self):
        self.assertEqual(extract_json('text {"a": 1} tail'), {"a": 1})

    def test_nested_braces(self):
        parsed = extract_json('```json\n{"a": {"b": [1, 2]}}\n```')
        self.assertEqual(parsed["a"]["b"], [1, 2])

    def test_no_json_raises(self):
        with self.assertRaises(ResearchError):
            extract_json("I could not find anything relevant.")

    def test_malformed_json_raises(self):
        with self.assertRaises(ResearchError):
            extract_json("```json\n{not valid,,}\n```")


class TestCatalystParsing(unittest.TestCase):
    def test_normalises_case(self):
        catalyst = _parse_catalysts(
            [{"headline": "Beat", "direction": "BULLISH", "importance": "HIGH"}]
        )[0]
        self.assertEqual(catalyst.direction, "bullish")
        self.assertEqual(catalyst.importance, "high")
        self.assertEqual(catalyst.sign, 1)

    def test_unknown_direction_becomes_uncertain(self):
        catalyst = _parse_catalysts([{"headline": "x", "direction": "moon"}])[0]
        self.assertEqual(catalyst.direction, "uncertain")
        self.assertEqual(catalyst.sign, 0)

    def test_non_http_source_is_dropped(self):
        catalyst = _parse_catalysts(
            [{"headline": "x", "source_url": "javascript:alert(1)"}]
        )[0]
        self.assertEqual(catalyst.source_url, "")

    def test_skips_entries_without_a_headline(self):
        self.assertEqual(_parse_catalysts([{"headline": ""}, {}, "junk", 42]), [])

    def test_handles_non_list_input(self):
        for value in (None, {}, "text", 7):
            self.assertEqual(_parse_catalysts(value), [])

    def test_bearish_sign(self):
        self.assertEqual(Catalyst("m", "h", "bearish", "high").sign, -1)


class TestPrompt(unittest.TestCase):
    def test_names_the_search_tool_explicitly(self):
        # A soft "search the web" let the model skip the tool entirely.
        self.assertIn("WebSearch", build_prompt("ORCL", "1 week", "2026-09-18"))

    def test_forbids_invention_and_permits_omission(self):
        prompt = build_prompt("ORCL", "1 week", "2026-09-18")
        self.assertIn("Never invent", prompt)
        self.assertIn("omit", prompt)

    def test_includes_every_requested_research_area(self):
        prompt = build_prompt("ORCL", "1 week", "2026-09-18")
        for topic in ("election", "wars", "interest rate", "energy", "earnings"):
            self.assertIn(topic.lower(), prompt.lower(), topic)

    def test_carries_the_ticker_and_horizon(self):
        prompt = build_prompt("NVDA", "3 months", "2026-12-11")
        self.assertIn("NVDA", prompt)
        self.assertIn("3 months", prompt)
        self.assertIn("2026-12-11", prompt)


if __name__ == "__main__":
    unittest.main()

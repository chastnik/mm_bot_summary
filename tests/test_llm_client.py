import unittest

from llm_client import LLMClient


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class TestLLMClientContentExtraction(unittest.TestCase):
    def setUp(self):
        self.client = LLMClient()

    def test_extract_text_from_string_content(self):
        response = _Response("simple text")
        result = self.client._extract_content_from_completion(response)
        self.assertEqual(result, "simple text")

    def test_extract_text_from_parts_content(self):
        response = _Response(
            [
                {"type": "text", "text": "part one"},
                {"type": "text", "text": " and part two"},
            ]
        )
        result = self.client._extract_content_from_completion(response)
        self.assertEqual(result, "part one and part two")

    def test_extract_returns_empty_on_missing_choices(self):
        class EmptyResponse:
            choices = []

        result = self.client._extract_content_from_completion(EmptyResponse())
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()

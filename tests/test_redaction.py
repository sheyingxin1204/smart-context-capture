import unittest

from smart_context import ContextPacket, SourceType
from smart_context.redaction import redact_url


class RedactionTests(unittest.TestCase):
    def test_redacts_userinfo_and_sensitive_query_values(self) -> None:
        value = redact_url(
            "https://alice:password@example.test/path?token=secret&foo=bar&session_id=abc#top"
        )

        self.assertEqual(
            value,
            "https://example.test/path?token=%5BREDACTED%5D&foo=bar&session_id=%5BREDACTED%5D#top",
        )
        self.assertNotIn("password", value)
        self.assertNotIn("secret", value)

    def test_keeps_non_http_locator_values_unchanged(self) -> None:
        self.assertEqual(redact_url("figma:abc123?node-id=1-2"), "figma:abc123?node-id=1-2")

    def test_packet_serialization_redacts_metadata_but_not_content(self) -> None:
        packet = ContextPacket(
            source_type=SourceType.CHROME_TAB,
            source_id="https://example.test/?token=secret",
            uri_or_path="https://example.test/?token=secret",
            content="The page text may mention token=secret as ordinary content.",
            structured_data={"url": "https://example.test/?session=abc"},
            provenance=[{"final_url": "https://example.test/?api_key=xyz"}],
        )

        value = packet.to_dict()
        self.assertNotIn("secret", value["source_id"])
        self.assertNotIn("abc", value["structured_data"]["url"])
        self.assertNotIn("xyz", value["provenance"][0]["final_url"])
        self.assertIn("token=secret", value["content"])


if __name__ == "__main__":
    unittest.main()

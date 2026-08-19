import unittest

from smart_context import (
    AdapterStatus,
    Capability,
    CapabilityRegistry,
    CaptureRequest,
    ContextRouter,
    SourceType,
)


class ContextRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CapabilityRegistry(
            [
                Capability("local", SourceType.LOCAL_FILE, AdapterStatus.AVAILABLE),
                Capability("chrome", SourceType.CHROME_TAB, AdapterStatus.UNAVAILABLE),
                Capability("public-http", SourceType.CHROME_TAB, AdapterStatus.AVAILABLE),
                Capability("screenshot", SourceType.CHROME_TAB, AdapterStatus.AVAILABLE),
                Capability("figma", SourceType.FIGMA_NODE, AdapterStatus.AVAILABLE),
            ]
        )
        self.router = ContextRouter(self.registry)

    def test_routes_local_file_to_primary(self) -> None:
        decision = self.router.route(
            CaptureRequest("report.pdf", source_hint=SourceType.LOCAL_FILE)
        )
        self.assertEqual(decision.adapter, "local")
        self.assertFalse(decision.fallback)

    def test_routes_public_url_to_low_permission_primary(self) -> None:
        decision = self.router.route(
            CaptureRequest("https://example.com", source_hint=SourceType.CHROME_TAB)
        )
        self.assertEqual(decision.adapter, "public-http")
        self.assertFalse(decision.fallback)

    def test_browser_session_explicitly_prefers_cdp(self) -> None:
        self.registry.register(
            Capability("chrome", SourceType.CHROME_TAB, AdapterStatus.AVAILABLE)
        )
        decision = self.router.route(
            CaptureRequest(
                "https://example.com",
                source_hint=SourceType.CHROME_TAB,
                prefer_browser_session=True,
            )
        )
        self.assertEqual(decision.adapter, "chrome")
        self.assertFalse(decision.fallback)

    def test_current_tab_requires_browser_session(self) -> None:
        decision = self.router.route(
            CaptureRequest("current", source_hint=SourceType.CHROME_TAB)
        )
        self.assertEqual(decision.adapter, "screenshot")
        self.assertTrue(decision.fallback)

    def test_detects_figma_from_locator(self) -> None:
        decision = self.router.route(CaptureRequest("https://figma.com/design/file"))
        self.assertEqual(decision.source_type, SourceType.FIGMA_NODE)


if __name__ == "__main__":
    unittest.main()

import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import urllib.error

SPEC = importlib.util.spec_from_file_location(
    "package_access", Path(__file__).parents[1] / "scripts/check-package-access.py")
access = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(access)


class PackageAccessTest(unittest.TestCase):
    def setUp(self):
        self.config = {"source_repositories": ["unlaxer-bom", "ABR-Snapshot"],
                       "snapshot_repository": "ABR-Snapshot", "snapshot_tag": "v1.2.0-snapshot",
                       "snapshot_assets": ["meta", "payload"]}
        self.responses = {
            "user": {"login": "caulis-deployuser"},
            "repos/caulis/unlaxer-bom/contents/": [],
            "repos/caulis/ABR-Snapshot/contents/": [],
            "repos/caulis/ABR-Snapshot/releases/tags/v1.2.0-snapshot": {
                "assets": [{"name": "meta"}, {"name": "payload"}]},
            "orgs/caulis/packages?package_type=maven&per_page=100&page=1": [
                {"name": "org.unlaxer.unlaxer-bom", "version_count": 2,
                 "repository": {"name": "unlaxer-bom"}}]}

    def fetch(self, token, path):
        response = self.responses[path]
        if isinstance(response, Exception):
            raise response
        return response

    def check(self, token="test-token"):
        return access.check_access(token, "caulis", "caulis-deployuser", self.config, self.fetch)

    def test_missing_secret_does_not_attempt_requests(self):
        self.responses.clear()
        with self.assertRaisesRegex(access.AccessError, "not available"):
            self.check("")

    def test_personal_account_is_rejected_before_repository_requests(self):
        self.responses = {"user": {"login": "opaopa6969"}}
        with self.assertRaisesRegex(access.AccessError, "does not match"):
            self.check()

    def test_reports_all_missing_read_permissions(self):
        for path in ["repos/caulis/unlaxer-bom/contents/", "repos/caulis/ABR-Snapshot/contents/"]:
            self.responses[path] = access.AccessError(path + ": HTTP 404")
        with self.assertRaises(access.AccessError) as error:
            self.check()
        self.assertIn("unlaxer-bom", str(error.exception))
        self.assertIn("ABR-Snapshot", str(error.exception))

    def test_missing_snapshot_payload_is_rejected(self):
        self.responses["repos/caulis/ABR-Snapshot/releases/tags/v1.2.0-snapshot"]["assets"].pop()
        with self.assertRaisesRegex(access.AccessError, "payload"):
            self.check()

    def test_missing_packages_scope_is_rejected(self):
        path = "orgs/caulis/packages?package_type=maven&per_page=100&page=1"
        self.responses[path] = access.AccessError(path + ": HTTP 403")
        with self.assertRaisesRegex(access.AccessError, "HTTP 403"):
            self.check()

    def test_report_contains_no_token(self):
        report = self.check()
        self.assertEqual(report["account"], "caulis-deployuser")
        self.assertEqual(report["packages"][0]["version_count"], 2)
        self.assertNotIn("test-token", str(report))

    def test_http_error_body_is_not_reported(self):
        with mock.patch.object(access.urllib.request, "build_opener") as factory:
            factory.return_value.open.side_effect = urllib.error.HTTPError(
                "https://api.github.com/user", 403, "test-token", None, None)
            with self.assertRaises(access.AccessError) as error:
                access.request_json("test-token", "user")
        self.assertEqual(str(error.exception), "user: HTTP 403")


if __name__ == "__main__":
    unittest.main()

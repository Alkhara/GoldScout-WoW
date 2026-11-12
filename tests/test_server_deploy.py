"""tools/server_deploy.py: a failed server deploy puts the previous version back."""
import json
import os
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import server_deploy  # noqa: E402


def status(version, share=100):
    return json.dumps({"id": "d", "author_email": "someone@example.com",
                       "versions": [{"version_id": version, "percentage": share}]})


class FakeWrangler:
    """Answers wrangler commands; deploy and rollback change what's live."""

    def __init__(self, live="old", deploy_ok=True, deploy_goes_live=True, rollback_ok=True, status_ok=True):
        self.live, self.commands, self.shown = live, [], []
        self.deploy_ok, self.deploy_goes_live = deploy_ok, deploy_goes_live
        self.rollback_ok, self.status_ok = rollback_ok, status_ok

    def __call__(self, command, show=True):
        self.commands.append(command[2:])
        self.shown.append(show)
        verb = command[2]
        if verb == "deployments":
            return self.status_ok, ("Some notice\n" + status(self.live)) if self.status_ok else ""
        if verb == "deploy":
            if self.deploy_goes_live:
                self.live = "new"
            return self.deploy_ok, ""
        if verb == "rollback":
            if self.rollback_ok:
                self.live = command[3]
            return self.rollback_ok, ""
        raise AssertionError(command)

    def verbs(self):
        return [c[0] for c in self.commands]


def checker(*results):
    """A check that returns each result in turn (None = healthy)."""
    queue = list(results)
    return lambda: queue.pop(0)


class ServerDeployTests(unittest.TestCase):
    def setUp(self):
        # In CI, GITHUB_STEP_SUMMARY is the Tests run's own summary: keep these fake deploys out of it.
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("GITHUB_STEP_SUMMARY", None)

    def test_a_healthy_deploy_is_kept(self):
        wrangler = FakeWrangler()
        self.assertEqual(server_deploy.main(wrangler, checker(None)), 0)
        self.assertEqual(wrangler.verbs(), ["deployments", "deploy"])
        self.assertEqual(wrangler.live, "new")

    def test_a_failing_check_rolls_back_to_the_previous_version(self):
        wrangler = FakeWrangler()
        self.assertEqual(server_deploy.main(wrangler, checker("health failed", None)), 1)
        self.assertEqual(wrangler.verbs(), ["deployments", "deploy", "deployments", "rollback"])
        self.assertEqual(wrangler.commands[-1][1], "old")
        self.assertIn("--yes", wrangler.commands[-1])
        self.assertEqual(wrangler.live, "old")

    def test_a_deploy_that_never_went_live_needs_no_rollback(self):
        wrangler = FakeWrangler(deploy_ok=False, deploy_goes_live=False)
        self.assertEqual(server_deploy.main(wrangler, checker()), 1)
        self.assertNotIn("rollback", wrangler.verbs())

    def test_a_deploy_that_went_live_and_then_failed_is_rolled_back(self):
        wrangler = FakeWrangler(deploy_ok=False)              # e.g. the triggers update failed
        self.assertEqual(server_deploy.main(wrangler, checker(None)), 1)
        self.assertEqual(wrangler.live, "old")

    def test_no_rollback_when_the_previous_version_is_unknown(self):
        wrangler = FakeWrangler(status_ok=False)
        self.assertEqual(server_deploy.main(wrangler, checker("health failed")), 1)
        self.assertNotIn("rollback", wrangler.verbs())

    def test_a_failed_rollback_still_fails_the_run(self):
        wrangler = FakeWrangler(rollback_ok=False)
        self.assertEqual(server_deploy.main(wrangler, checker("health failed")), 1)
        self.assertEqual(wrangler.live, "new")

    def test_the_status_with_its_email_address_is_never_printed(self):
        wrangler = FakeWrangler()
        server_deploy.main(wrangler, checker(None))
        for command, show in zip(wrangler.commands, wrangler.shown):
            if command[0] == "deployments":
                self.assertFalse(show)

    def test_a_drill_deploys_then_rolls_back_and_passes(self):
        wrangler = FakeWrangler()
        self.assertEqual(server_deploy.main(wrangler, checker(None, None), drill=True), 0)
        self.assertEqual(wrangler.verbs(), ["deployments", "deploy", "deployments", "rollback"])
        self.assertEqual(wrangler.live, "old")

    def test_a_drill_whose_rollback_fails_fails(self):
        wrangler = FakeWrangler(rollback_ok=False)
        self.assertEqual(server_deploy.main(wrangler, checker(None), drill=True), 1)

    def test_live_version_needs_one_version_on_all_traffic(self):
        self.assertEqual(server_deploy.live_version(lambda c, s=True: (True, status("v1"))), "v1")
        self.assertIsNone(server_deploy.live_version(lambda c, s=True: (True, status("v1", 50))))
        self.assertIsNone(server_deploy.live_version(lambda c, s=True: (True, "not json")))

    def test_health_is_retried_while_the_new_version_spreads(self):
        answers, waits = iter([False, False, True, True]), []
        problem = server_deploy.check(sleep=waits.append, healthy=lambda url: next(answers),
                                      accepts=lambda url: None)
        self.assertIsNone(problem)
        self.assertEqual(len(waits), 2)

    def test_check_reports_an_address_that_stays_down(self):
        problem = server_deploy.check(sleep=lambda s: None, healthy=lambda url: "workers.dev" not in url,
                                      accepts=lambda url: None)
        self.assertIn("workers.dev", problem)

    def test_check_reports_a_refused_export_version(self):
        def refuses(url):
            sys.exit(1)
        problem = server_deploy.check(sleep=lambda s: None, healthy=lambda url: True, accepts=refuses)
        self.assertIn("export version", problem)


if __name__ == "__main__":
    unittest.main()

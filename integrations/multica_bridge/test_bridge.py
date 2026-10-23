import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name("bridge.py")
spec = importlib.util.spec_from_file_location("multica_bridge", MODULE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class StubCLI:
    def __init__(self):
        self.calls = []
    def call(self, tool, *parts, **kwargs):
        self.calls.append((tool, parts))
        if tool == "multica":
            if parts[:2] == ("issue", "list"):
                return {"issues": [], "has_more": False}
            if parts[:2] == ("issue", "get"):
                return {"issue": {"identifier": parts[2], "status": "todo"}}
        return {}


class BridgeTests(unittest.TestCase):
    def test_plan_requires_matching_repo_and_issue(self):
        plan = {"issue": "MUL-42", "repo": "/tmp/repo",
                "lanes": [{"slug": "fix-login", "tasks": ["Fix bug"],
                           "plan": ["Review login.py"], "acceptance": ["Run tests"]}]}
        bridge.verify_plan(plan, "MUL-42", "/tmp/repo")
        with self.assertRaises(ValueError):
            bridge.verify_plan(plan, "MUL-99", "/tmp/repo")

    def test_no_false_completion_on_done_claim(self):
        self.assertFalse(bridge.run_is_delivered({"lanes": [{"phase": "working"}]}))
        self.assertFalse(bridge.run_is_delivered({"lanes": []}))
        self.assertTrue(bridge.run_is_delivered(
            {"lanes": [{"phase": "published"}, {"phase": "merged"}]}))

    def test_duplicate_issue_claim_has_one_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"state_dir": tmp, "workspace_id": "ws",
                   "approver_ids": ["u"], "projects": {"p": "/tmp/repo"}}
            ctl = bridge.Controller(cfg, StubCLI())
            one = ctl.create({"identifier": "MUL-42"}, "/tmp/repo")
            two = ctl.create({"identifier": "MUL-42"}, "/tmp/repo")
            self.assertEqual(one["job_id"], two["job_id"])
            self.assertEqual(ctl.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)
            ctl.close()

    def test_ambiguous_send_refuses_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"state_dir": tmp, "workspace_id": "ws",
                   "approver_ids": ["u"], "projects": {"p": "/tmp/repo"}}
            fake = StubCLI()
            ctl = bridge.Controller(cfg, fake)
            job = ctl.create({"identifier": "MUL-42"}, "/tmp/repo")
            ctl.set("MUL-42", "planning_send")
            ctl.advance(ctl.get("MUL-42"), {"status": "in_progress"})
            self.assertEqual(ctl.get("MUL-42")["phase"], "needs_recovery")
            self.assertFalse(any(x[0] == "herdr" for x in fake.calls))
            ctl.close()

    def test_pagination_raises_on_unknown_payload(self):
        with self.assertRaises(ValueError):
            bridge.listed_issues({"items": [{"id": "x"}]})

    def test_approval_requires_exact_hash(self):
        self.assertIsNotNone(bridge.APPROVE.fullmatch("APPROVE " + "a" * 64))
        self.assertIsNone(bridge.APPROVE.fullmatch("Approve now " + "a" * 64))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.approvals import ApprovalService
from nxus_harness.audit import AuditLog
from nxus_harness.engine import HarnessEngine
from nxus_harness.evidence import EvidenceStore
from nxus_harness.models import (Claim, PlanManifest, PlannedOperation, PolicyDenied, RiskLevel, RunState, TaskContract,
                                 TaskProfile, ValidationError, parse_utc, utc_now)
from nxus_harness.llama_cpp_adapter import LlamaCppProfile
from nxus_harness.llm_planner import LlmPlanner
from nxus_harness.ollama_adapter import OllamaProfile
from nxus_harness.policy import PolicyEngine
from nxus_harness.tools import ToolGateway, ToolRegistry


class _FakeAdapter:
    """Remplace LlamaCppAdapter dans les tests : même interface
    (structured_chat), aucun réseau. La réponse est fixée par le test."""

    def __init__(self, response: dict, *, raises: Exception | None = None) -> None:
        self.response = response
        self.last_messages: list[dict] | None = None
        self.raises = raises  # simule une panne réseau/timeout réelle côté llama-server

    def structured_chat(self, messages, schema, json_schema=None, *, code_task=False):  # noqa: ANN001 - signature miroir de LlamaCppAdapter
        self.last_messages = messages
        self.last_json_schema = json_schema
        if self.raises is not None:
            raise self.raises
        return self.response


class HarnessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "fixtures").mkdir()
        fixture_source = Path(__file__).resolve().parents[1] / "fixtures" / "corpus.md"
        shutil.copy(fixture_source, self.root / "fixtures" / "corpus.md")
        self.engine = HarnessEngine(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def contract(self, *, tenant: str = "tenant-a", profile: TaskProfile = TaskProfile.CODE_CHANGE) -> TaskContract:
        return TaskContract(
            task_id="test-task", tenant_id=tenant, actor_id="operator", objective="Créer un brouillon local.",
            acceptance_criteria=["brouillon présent", "contrôle réussi"], profile=profile,
            max_risk=RiskLevel.R1 if profile == TaskProfile.CODE_CHANGE else RiskLevel.R0,
            allowed_paths=["drafts/test.md"] if profile == TaskProfile.CODE_CHANGE else [],
            allowed_tools=["write_workspace_draft", "run_declared_check"] if profile == TaskProfile.CODE_CHANGE else ["retrieve_fixture"],
            desired_draft="# Brouillon\ncontenu sûr\n",
        )

    def test_t01_demo_completed_with_audit(self) -> None:
        context = self.engine.run_demo(self.contract())
        self.assertEqual(context.state, RunState.COMPLETED)
        self.assertTrue((context.workspace / "drafts/test.md").exists())
        self.assertTrue(AuditLog.verify(context.run_dir / "audit.jsonl")[0])

    def test_t03_hostile_fixture_stays_untrusted(self) -> None:
        context = self.engine.run_demo(self.contract(profile=TaskProfile.RESEARCH_READONLY))
        self.assertEqual(context.state, RunState.COMPLETED)
        self.assertFalse(context.policy.kill_switch)
        self.assertEqual(context.results[0]["result"]["untrusted"], True)

    def test_t05_grant_is_single_use(self) -> None:
        service = ApprovalService(self.root / "grants.json")
        grant = service.issue(actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 1})
        service.validate_and_consume(grant_id=grant.grant_id, actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 1})
        with self.assertRaises(PolicyDenied):
            service.validate_and_consume(grant_id=grant.grant_id, actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 1})

    def test_t05_grant_is_bound_to_exact_arguments(self) -> None:
        service = ApprovalService(self.root / "grants.json")
        grant = service.issue(actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 1})
        with self.assertRaises(PolicyDenied):
            service.validate_and_consume(grant_id=grant.grant_id, actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 2})

    def test_t37_grant_consumption_is_atomic_across_processes(self) -> None:
        # [AJOUTÉ 19/10/2026 — faille réelle signalée par un audit externe,
        # puis REPRODUITE avec deux process Python séparés lancés en
        # parallèle avant la correction : les deux obtenaient "OK" sur le
        # même grant à usage unique, car chaque process ne voyait que sa
        # propre copie en mémoire du fichier d'approbations. Un thread ne
        # suffit PAS à reproduire ceci (le GIL sérialise), il faut de vrais
        # process séparés -- c'est pourquoi ce test utilise subprocess,
        # pas threading.
        import subprocess
        import sys

        src_dir = str(Path(__file__).resolve().parents[1] / "src")
        store_path = self.root / "race_grants.json"
        setup_code = (
            f"import sys; sys.path.insert(0, {src_dir!r})\n"
            "from pathlib import Path\n"
            "from nxus_harness.approvals import ApprovalService\n"
            f"service = ApprovalService(Path({str(store_path)!r}))\n"
            "grant = service.issue(actor_id='op', run_id='r1', manifest_hash='m1', tool_id='execute_python', arguments={'code': 'print(1)'})\n"
            "print(grant.grant_id)\n"
        )
        grant_id = subprocess.run([sys.executable, "-c", setup_code], capture_output=True, text=True, timeout=10).stdout.strip()
        self.assertTrue(grant_id, "échec de la préparation du grant")

        consume_code = (
            f"import sys, time; sys.path.insert(0, {src_dir!r})\n"
            "from pathlib import Path\n"
            "from nxus_harness.approvals import ApprovalService\n"
            f"service = ApprovalService(Path({str(store_path)!r}))\n"
            "time.sleep(0.05)\n"
            "try:\n"
            f"    service.validate_and_consume(grant_id={grant_id!r}, actor_id='op', run_id='r1', manifest_hash='m1', tool_id='execute_python', arguments={{'code': 'print(1)'}})\n"
            "    print('OK')\n"
            "except Exception:\n"
            "    print('DENIED')\n"
        )
        procs = [subprocess.Popen([sys.executable, "-c", consume_code], stdout=subprocess.PIPE, text=True) for _ in range(8)]
        outcomes = [proc.communicate(timeout=10)[0].strip() for proc in procs]
        self.assertEqual(outcomes.count("OK"), 1, f"le grant à usage unique a été consommé {outcomes.count('OK')} fois : {outcomes}")

    def test_t05_expired_grant_is_refused(self) -> None:
        service = ApprovalService(self.root / "grants.json")
        grant = service.issue(actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 1})
        service._grants[grant.grant_id] = replace(grant, expires_at=(parse_utc(utc_now()) - timedelta(seconds=1)).isoformat())
        service._save()  # [AJOUTÉ 19/10/2026] validate_and_consume relit maintenant le disque sous verrou (voir approvals.py) ; une mutation en mémoire seule ne serait plus visible, comme sur le vrai disque.
        with self.assertRaises(PolicyDenied):
            service.validate_and_consume(grant_id=grant.grant_id, actor_id="a", run_id="r", manifest_hash="m", tool_id="tool", arguments={"x": 1})

    def test_t06_external_action_is_disabled(self) -> None:
        with self.assertRaises(PolicyDenied):
            ToolRegistry().get("send_external_message")

    def test_t07_extra_arguments_are_rejected(self) -> None:
        registry = ToolRegistry()
        with self.assertRaises(ValidationError):
            registry.validate_arguments(registry.get("write_workspace_draft"), {"path": "a.md", "content": "x", "extra": True})

    def test_t08_path_traversal_in_contract_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            TaskContract(
                task_id="x", tenant_id="t", actor_id="a", objective="x", acceptance_criteria=["x"],
                profile=TaskProfile.CODE_CHANGE, max_risk=RiskLevel.R1, allowed_paths=["../outside.md"],
            ).validate()

    def test_t10_critical_claim_without_evidence_fails(self) -> None:
        store = EvidenceStore(self.root / "evidence")
        store.add_claim(Claim("claim-1", "affirmation", True, [], "unsupported"))
        with self.assertRaises(ValidationError):
            store.require_valid_claims()

    def test_t11_audit_redacts_fixture_secret(self) -> None:
        path = self.root / "audit.jsonl"
        audit = AuditLog(path, run_id="r", tenant_id="t")
        audit.append("test", "redaction", "allow", {"token": "TOP_SECRET_DEMO"})
        raw = path.read_text(encoding="utf-8")
        self.assertNotIn("TOP_SECRET_DEMO", raw)
        self.assertTrue(AuditLog.verify(path)[0])

    def test_t12_kill_switch_revokes_and_aborts(self) -> None:
        context = self.engine.create_run(self.contract())
        self.engine.plan(context)
        grants = self.engine.approve(context, actor_id="operator")
        self.assertTrue(grants)
        self.engine.abort(context, "test")
        self.assertEqual(context.state, RunState.ABORTED)
        self.assertTrue(context.policy.kill_switch)
        with self.assertRaises(ValidationError):
            self.engine.execute(context, grants)

    def test_t14_tenants_have_separate_runs(self) -> None:
        first = self.engine.run_demo(self.contract(tenant="tenant-a"))
        second = self.engine.run_demo(self.contract(tenant="tenant-b"))
        self.assertNotEqual(first.run_dir.parent, second.run_dir.parent)
        self.assertFalse((first.run_dir.parent / second.run_id).exists())

    def test_t15_ollama_remote_profile_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            OllamaProfile(base_url="http://10.0.0.9:11434", model="model", enabled=True).validate()

    def test_t16_llama_cpp_remote_profile_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            LlamaCppProfile(base_url="http://10.0.0.9:8080", model="model", enabled=True).validate()

    def test_t16_llama_cpp_enabled_without_model_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            LlamaCppProfile(enabled=True).validate()

    def test_t17_retrieve_fixture_records_real_evidence(self) -> None:
        # [AJOUTÉ 18/10/2026] Verrouille le RAG local réel : avant ce correctif,
        # retrieve_fixture renvoyait des matches sans aucune Evidence tracée.
        contract = replace(self.contract(profile=TaskProfile.RESEARCH_READONLY), objective="couverte")
        context = self.engine.run_demo(contract)
        self.assertEqual(context.state, RunState.COMPLETED)
        result = context.results[0]["result"]
        self.assertEqual(result["matches"], ["## Réponse couverte"])
        self.assertEqual(len(result["evidence_ids"]), 1)
        self.assertIn(result["evidence_ids"][0], context.evidence.evidence_ids())

    def test_t18_llm_planner_completes_run_like_simulated_planner(self) -> None:
        # [AJOUTÉ 18/10/2026] Preuve que le plan proposé par un modèle (ici
        # simulé via _FakeAdapter, sans réseau) traverse le MÊME pipeline de
        # validation qu'un plan déterministe et aboutit à un run COMPLETED.
        contract = self.contract()
        fake = _FakeAdapter({"operations": [
            {"tool_id": "write_workspace_draft", "arguments": {"path": "drafts/test.md", "content": contract.desired_draft}},
            {"tool_id": "run_declared_check", "arguments": {"check": "draft_exists"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertEqual(context.state, RunState.COMPLETED)
        self.assertTrue((context.workspace / "drafts/test.md").exists())

    def test_t18_llm_planner_rejects_tool_outside_contract(self) -> None:
        # Le modèle propose un outil hors périmètre déclaré (send_external_message,
        # R4, jamais autorisé) : rejeté avant même d'atteindre PolicyEngine.
        contract = self.contract()
        fake = _FakeAdapter({"operations": [
            {"tool_id": "send_external_message", "arguments": {"recipient": "x", "body": "y"}},
        ]})
        with self.assertRaises(ValidationError):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t18_llm_planner_rejects_malformed_response(self) -> None:
        contract = self.contract()
        fake = _FakeAdapter({"operations": "pas une liste"})
        with self.assertRaises(ValidationError):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t19_memory_persists_across_runs_for_same_tenant(self) -> None:
        # [AJOUTÉ 18/10/2026] Vraie mémoire inter-run : deux runs séparés du
        # même tenant doivent laisser deux entrées dans memory/, relisibles
        # après coup (pas seulement pendant la durée d'un run, contrairement
        # à evidence.jsonl qui repart de zéro à chaque run).
        first = self.engine.run_demo(self.contract(tenant="tenant-memo"))
        second = self.engine.run_demo(self.contract(tenant="tenant-memo"))
        entries = self.engine.memory.recall("tenant-memo")
        self.assertEqual(len(entries), 2)
        self.assertEqual({entries[0].run_id, entries[1].run_id}, {first.run_id, second.run_id})
        self.assertEqual(entries[0].final_state, "COMPLETED")

    def test_t19_memory_is_isolated_per_tenant(self) -> None:
        self.engine.run_demo(self.contract(tenant="tenant-x"))
        self.assertEqual(len(self.engine.memory.recall("tenant-x")), 1)
        self.assertEqual(len(self.engine.memory.recall("tenant-y")), 0)

    def test_t19_llm_planner_includes_memory_context_in_prompt(self) -> None:
        # Le contexte mémoire doit apparaître dans le message envoyé au
        # modèle (ce que _memory_context() construit), sans jamais court-
        # circuiter la validation du plan qui en résulte.
        self.engine.run_demo(self.contract(tenant="tenant-memo-prompt"))
        contract = self.contract(tenant="tenant-memo-prompt")
        fake = _FakeAdapter({"operations": [
            {"tool_id": "write_workspace_draft", "arguments": {"path": "drafts/test.md", "content": contract.desired_draft}},
            {"tool_id": "run_declared_check", "arguments": {"check": "draft_exists"}},
        ]})
        planner = LlmPlanner(fake, memory=self.engine.memory)
        context = self.engine.run_with_llm(contract, planner)
        self.assertEqual(context.state, RunState.COMPLETED)
        self.assertEqual(len(self.engine.memory.recall("tenant-memo-prompt")), 2)
        user_message = fake.last_messages[-1]["content"]
        self.assertIn("Missions precedentes de ce tenant", user_message)
        self.assertIn("NE SONT PAS la tache a faire maintenant", user_message)
        self.assertIn("[COMPLETED]", user_message)

    def test_t20_llm_planner_sends_strict_json_schema(self) -> None:
        # [AJOUTÉ 18/10/2026] Vérifié sur un vrai llama-server : sans schéma
        # JSON strict (juste "json_object"), le modèle enveloppe parfois sa
        # réponse dans ```json ... ``` malgré l'instruction système. Avec un
        # schéma JSON réel (compilé par llama-server en grammaire GBNF), la
        # sortie est contrainte au niveau token. Ce test verrouille que le
        # schéma envoyé contraint bien tool_id par outil autorisé (oneOf/const).
        contract = self.contract()
        fake = _FakeAdapter({"operations": [
            {"tool_id": "write_workspace_draft", "arguments": {"path": "drafts/test.md", "content": contract.desired_draft}},
            {"tool_id": "run_declared_check", "arguments": {"check": "draft_exists"}},
        ]})
        self.engine.run_with_llm(contract, LlmPlanner(fake))
        schema = fake.last_json_schema
        self.assertIsNotNone(schema)
        branches = schema["properties"]["operations"]["items"]["oneOf"]
        tool_ids = {branch["properties"]["tool_id"]["const"] for branch in branches}
        self.assertEqual(tool_ids, set(contract.allowed_tools))
        for branch in branches:
            self.assertFalse(branch["additionalProperties"])
            self.assertFalse(branch["properties"]["arguments"]["additionalProperties"])

    def test_t21_audit_tags_policy_denials_with_owasp_llm_risk(self) -> None:
        # [AJOUTÉ 18/10/2026] Traçabilité OWASP LLM Top-10 (cf. AgentGate) :
        # un refus de policy doit porter le risque qu'il mitige ; une
        # autorisation n'en porte aucun (rien n'a été refusé).
        decision_denied = PolicyEngine().authorize(
            contract=self.contract(), manifest=None, state=RunState.INTAKE,
            tool_id="write_workspace_draft", arguments={}, tool_risk=RiskLevel.R1,
        )
        self.assertEqual(decision_denied.rule_id, "P-STATE-001")
        self.assertEqual(decision_denied.owasp_llm_risk, "LLM06:2025 Excessive Agency")

        context = self.engine.run_demo(self.contract())
        audit_lines = [json.loads(line) for line in (context.run_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
        policy_events = [e for e in audit_lines if e["component"] == "policy"]
        self.assertTrue(policy_events)
        for event in policy_events:
            if event["decision"] == "allow":
                self.assertIsNone(event["details"]["owasp_llm_risk"])
            else:
                self.assertIsNotNone(event["details"]["owasp_llm_risk"])

    def test_t22_submit_stops_at_awaiting_approval(self) -> None:
        # [AJOUTÉ 18/10/2026 — humain dans la boucle] Avant ce correctif,
        # seule run_demo() existait : plan() + approve() + execute() dans le
        # MÊME appel Python, donc aucune vraie pause pour une décision
        # humaine. submit() doit s'arrêter net à AWAITING_APPROVAL.
        context = self.engine.submit(self.contract())
        self.assertEqual(context.state, RunState.AWAITING_APPROVAL)
        self.assertTrue((context.run_dir / "PLAN.md").is_file())
        self.assertFalse((context.workspace / "drafts/test.md").exists())

    def test_t22_resume_run_reloads_equivalent_context_from_disk(self) -> None:
        # La pièce clé : un DEUXIÈME appel (simulant un process séparé, comme
        # le fait réellement `nxus_harness approve` en CLI) doit retrouver
        # exactement le même run, prêt à être approuvé.
        submitted = self.engine.submit(self.contract())
        resumed = self.engine.resume_run(submitted.contract.tenant_id, submitted.run_id)
        self.assertEqual(resumed.state, RunState.AWAITING_APPROVAL)
        self.assertEqual(resumed.manifest.manifest_hash, submitted.manifest.manifest_hash)
        self.assertEqual(resumed.contract.objective, submitted.contract.objective)

    def test_t22_approve_and_run_completes_after_resume(self) -> None:
        contract = self.contract()
        submitted = self.engine.submit(contract)
        resumed = self.engine.resume_run(contract.tenant_id, submitted.run_id)
        completed = self.engine.approve_and_run(resumed, actor_id=contract.actor_id)
        self.assertEqual(completed.state, RunState.COMPLETED)
        self.assertTrue((completed.workspace / "drafts/test.md").exists())

    def test_t22_resume_run_unknown_run_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.engine.resume_run("demo-tenant", "run-does-not-exist")

    def _agentic_contract(self, **overrides) -> TaskContract:
        base = TaskContract(
            task_id="exec-task", tenant_id="tenant-a", actor_id="operator",
            objective="Exécuter un script Python de test.", acceptance_criteria=["le script tourne"],
            profile=TaskProfile.AGENTIC_EXECUTION, max_risk=RiskLevel.R2,
            allowed_tools=["execute_python", "fetch_url"],
            allowed_urls=["https://example.invalid/data"],
        )
        return replace(base, **overrides)

    def test_t23_execute_python_runs_for_real_inside_workspace(self) -> None:
        # [AJOUTÉ 18/10/2026 — R2] Preuve que "exécuter du code" n'est pas
        # juste accepté par le policy engine mais tourne VRAIMENT : le script
        # écrit un fichier dans le workspace, on vérifie qu'il existe après.
        # allowed_paths doit déclarer ce que le code a le droit de produire :
        # le contrôle "scope" de verify_and_complete() s'applique à TOUTE
        # écriture dans le workspace, pas seulement à write_workspace_draft —
        # vérifié ici (sans allowed_paths, le run échoue à raison en scope).
        contract = self._agentic_contract(allowed_paths=["preuve.txt"],
                                          allowed_tools=["execute_python", "fetch_url", "run_declared_check"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "open('preuve.txt', 'w').write('ok')"}},
            {"tool_id": "run_declared_check", "arguments": {"check": "file_equals:preuve.txt:ok"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertEqual(context.state, RunState.COMPLETED)
        self.assertEqual((context.workspace / "preuve.txt").read_text(encoding="utf-8"), "ok")
        self.assertEqual(context.results[0]["result"]["exit_code"], 0)

    def test_t25_declared_check_catches_wrong_execution_result(self) -> None:
        # [AJOUTÉ 18/10/2026 — bug réel trouvé en comparant raisonnement
        # on/off] Avant ce correctif, "declared_check" valait NOT_APPLICABLE
        # pour AGENTIC_EXECUTION : un run pouvait COMPLETED avec un résultat
        # de calcul FAUX, tant que le fichier produit restait dans
        # allowed_paths ("scope" vérifie l'emplacement, jamais le contenu).
        # Reproduit en vrai (2 essais sur 4 avec un vrai llama-server).
        contract = self._agentic_contract(allowed_paths=["resultat.txt"],
                                          allowed_tools=["execute_python", "run_declared_check"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "open('resultat.txt', 'w').write('42')"}},  # faux : devrait être 391
            {"tool_id": "run_declared_check", "arguments": {"check": "file_equals:resultat.txt:391"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertNotEqual(context.state, RunState.COMPLETED)
        verification = json.loads((context.run_dir / "verification.json").read_text(encoding="utf-8"))
        declared = next(item for item in verification if item["check_id"] == "declared_check")
        self.assertEqual(declared["status"], "not_run")

    def test_t26_stdout_matches_file_catches_model_self_consistent_lie(self) -> None:
        # [AJOUTÉ 18/10/2026 — bug réel trouvé via scripts/mission_loop.py]
        # file_equals laisse le modèle choisir SA PROPRE valeur "attendue" :
        # en conditions réelles, le modèle a calculé 385 (stdout correct
        # d'execute_python), puis écrit "1001" dans le fichier et déclaré
        # file_equals:...:1001 -- cohérent avec lui-même, FAUX par rapport au
        # vrai calcul. Le harnais disait COMPLETED à raison (rien n'était
        # incohérent dans ce qu'il vérifiait), mais le résultat était faux.
        # Reproduit ici à l'identique avec un faux adapter déterministe.
        contract = self._agentic_contract(allowed_paths=["resultat.txt"],
                                          allowed_tools=["execute_python", "write_workspace_draft", "run_declared_check"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "print(385)"}},
            {"tool_id": "write_workspace_draft", "arguments": {"path": "resultat.txt", "content": "1001"}},
            {"tool_id": "run_declared_check", "arguments": {"check": "stdout_matches_file:resultat.txt"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertNotEqual(context.state, RunState.COMPLETED)
        verification = json.loads((context.run_dir / "verification.json").read_text(encoding="utf-8"))
        declared = next(item for item in verification if item["check_id"] == "declared_check")
        self.assertEqual(declared["status"], "not_run")

    def test_t26_stdout_matches_file_passes_when_consistent(self) -> None:
        contract = self._agentic_contract(allowed_paths=["resultat.txt"],
                                          allowed_tools=["execute_python", "write_workspace_draft", "run_declared_check"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "print(385)"}},
            {"tool_id": "write_workspace_draft", "arguments": {"path": "resultat.txt", "content": "385"}},
            {"tool_id": "run_declared_check", "arguments": {"check": "stdout_matches_file:resultat.txt"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertEqual(context.state, RunState.COMPLETED)
        self.assertEqual(context.results[-1]["result"]["expected_from_stdout"], "385")

    def test_t36_qa_readonly_can_reach_jacobian_verify(self) -> None:
        # [AJOUTÉ 19/10/2026 — biais de conception corrigé] jacobian_verify
        # est R0 (zéro effet de bord prouvé) mais n'était câblé que sur
        # AGENTIC_EXECUTION -- une tâche QA_READONLY devait escalader vers
        # un profil bien plus permissif (R2) juste pour vérifier un calcul.
        # Ce test échouait avant la correction du profil dans policy.py.
        contract = TaskContract(
            task_id="qa-jacobian", tenant_id="tenant-qa", actor_id="operator",
            objective="Vérifier un calcul.", acceptance_criteria=["calcul vérifié"],
            profile=TaskProfile.QA_READONLY, max_risk=RiskLevel.R0,
            allowed_paths=[], allowed_tools=["jacobian_verify"],
        )
        fake = _FakeAdapter({"operations": [
            {"tool_id": "jacobian_verify", "arguments": {"operation_id": "integer.compute.extended_gcd", "args_json": "{}"}},
        ]})
        try:
            self.engine.run_with_llm(contract, LlmPlanner(fake))
        except PolicyDenied as exc:
            self.fail(f"QA_READONLY aurait dû pouvoir atteindre jacobian_verify : {exc}")

    def test_t32_jacobian_verify_registered_r0_and_reachable_via_policy(self) -> None:
        # jacobian_verify appelle un binaire externe (venv dédié, non garanti
        # dans tout environnement de test) -- ce test vérifie seulement le
        # câblage (registre + policy), pas l'exécution réelle du binaire
        # (vérifiée manuellement en vrai, voir docs/investigations/).
        from nxus_harness.tools import ToolRegistry
        definition = ToolRegistry().get("jacobian_verify")
        self.assertEqual(definition.risk, RiskLevel.R0)
        contract = self._agentic_contract(allowed_paths=[], allowed_tools=["jacobian_verify"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "jacobian_verify", "arguments": {"operation_id": "integer.compute.extended_gcd", "args_json": "{}"}},
        ]})
        # Ne doit PAS être refusé par la policy (allowed_tools le couvre) --
        # peut échouer plus loin si le binaire est absent de cet environnement,
        # ce qui n'est pas ce que ce test vérifie.
        try:
            self.engine.run_with_llm(contract, LlmPlanner(fake))
        except PolicyDenied as exc:
            self.fail(f"jacobian_verify n'aurait pas dû être refusé par la policy : {exc}")

    def test_t32_smokinggun_scan_rejects_target_outside_allowlist(self) -> None:
        contract = self._agentic_contract(allowed_paths=["src"], allowed_tools=["smokinggun_scan"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "smokinggun_scan", "arguments": {"target": "/etc"}},
        ]})
        with self.assertRaises(PolicyDenied):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t31_rea_inspect_rejects_subcommand_outside_safelist(self) -> None:
        # [AJOUTÉ 18/10/2026 — pont vers la vraie CLI rea] install-adb-package,
        # debug-with-gdb, execute-rizin-command etc. sont de VRAIES sous-
        # commandes de rea -- elles doivent être refusées par policy.py
        # avant tout subprocess, pas seulement "non reconnues".
        contract = self._agentic_contract(allowed_paths=["fake.apk"], allowed_tools=["rea_inspect"])
        for dangerous in ("install-adb-package", "debug-with-gdb", "execute-rizin-command", "cutter-command"):
            fake = _FakeAdapter({"operations": [
                {"tool_id": "rea_inspect", "arguments": {"subcommand": dangerous, "target": "fake.apk"}},
            ]})
            with self.assertRaises(PolicyDenied):
                self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t41_rea_inspect_and_smokinggun_reject_shell_metacharacters_in_target(self) -> None:
        # [AJOUTÉ 19/10/2026 — défense en profondeur, T9 du rapport d'audit
        # externe] rea_inspect/smokinggun_scan passent par shell=True sur
        # Windows -- target est déjà contraint à allowed_paths exact, mais
        # ce test vérifie en plus qu'un chemin contenant un métacaractère
        # shell Windows (&, |, %, ^, guillemet, parenthèses) est refusé
        # même s'il correspondait par ailleurs à allowed_paths.
        for hostile_target in ["fake.apk & calc", "fake.apk | type secret.txt", 'fake.apk" whoami "']:
            contract = self._agentic_contract(allowed_paths=[hostile_target], allowed_tools=["rea_inspect", "smokinggun_scan"])
            for tool_id, args in (("rea_inspect", {"subcommand": "inspect-android-package", "target": hostile_target}),
                                  ("smokinggun_scan", {"target": hostile_target})):
                fake = _FakeAdapter({"operations": [{"tool_id": tool_id, "arguments": args}]})
                with self.assertRaises(PolicyDenied):
                    self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t31_rea_inspect_rejects_target_outside_allowlist(self) -> None:
        contract = self._agentic_contract(allowed_paths=["fake.apk"], allowed_tools=["rea_inspect"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "rea_inspect", "arguments": {"subcommand": "inspect-android-package", "target": "/etc/passwd"}},
        ]})
        with self.assertRaises(PolicyDenied):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t30_submit_marks_run_aborted_on_unexpected_planner_exception(self) -> None:
        # [AJOUTÉ 18/10/2026 — bug réel reproduit en conditions réelles : un
        # TimeoutError de llama-server pendant planner.create() (observé en
        # vrai, llm_planner.py appelle adapter.structured_chat) n'était
        # capturé par AUCUN code -- ni engine.submit(), ni l'appelant
        # (scripts/view_runs.py, qui ne catchait que ValidationError/
        # PolicyDenied). Le run restait coincé à DRAFTING_PLAN pour
        # toujours, /live affichant un état figé sans jamais le dire.
        # submit() doit maintenant transitionner vers ABORTED avant de
        # relayer N'IMPORTE QUELLE exception du planner.
        contract = self._agentic_contract(allowed_paths=["preuve.txt"])
        fake = _FakeAdapter({}, raises=TimeoutError("llama-server ne répond pas"))
        with self.assertRaises(TimeoutError):
            self.engine.submit(contract, planner=LlmPlanner(fake))
        runs = list((self.engine.runs_root / contract.tenant_id).iterdir())
        self.assertEqual(len(runs), 1)
        state = json.loads((runs[0] / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "ABORTED")

    def test_t29_reflection_review_rejects_too_many_operations(self) -> None:
        # [AJOUTÉ 18/10/2026 — finding "needs_validation" du security-audit
        # skill, run-1] Un plan proposé avec un nombre d'opérations massif
        # (ici : au-delà du plafond ReflectionReview.MAX_OPERATIONS_PER_PLAN)
        # doit être rejeté par du CODE avant AWAITING_APPROVAL, pas seulement
        # par une relecture humaine de PLAN.md.
        from nxus_harness.planner import ReflectionReview
        contract = self._agentic_contract(allowed_paths=["preuve.txt"], allowed_tools=["run_declared_check"])
        too_many = ReflectionReview.MAX_OPERATIONS_PER_PLAN + 1
        fake = _FakeAdapter({"operations": [
            {"tool_id": "run_declared_check", "arguments": {"check": "draft_exists"}} for _ in range(too_many)
        ]})
        with self.assertRaises(ValidationError):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t27_stdout_matches_file_rejects_silent_crash_as_empty_vs_empty(self) -> None:
        # [AJOUTÉ 18/10/2026 — bug réel trouvé via une vraie mission
        # (Ornith-1.5-9B, scripts/mission_loop.py)] Le modèle a proposé du
        # code execute_python syntaxiquement valide mais qui plante à
        # l'exécution (TypeError : open(...).write(__doc__) avec
        # __doc__=None) avant d'afficher quoi que ce soit ni d'écrire le
        # fichier. stdout vide ET fichier absent/vide -> "" == "" ->
        # passait à tort, run marqué COMPLETED sans que rien n'ait
        # fonctionné. Reproduit ici avec un code qui échoue (exit_code != 0)
        # sans produire de stdout.
        contract = self._agentic_contract(allowed_paths=["resultat.txt"],
                                          allowed_tools=["execute_python", "run_declared_check"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "raise TypeError('plante avant tout print')"}},
            {"tool_id": "run_declared_check", "arguments": {"check": "stdout_matches_file:resultat.txt"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertNotEqual(context.state, RunState.COMPLETED)
        declared = context.results[-1]["result"]
        self.assertFalse(declared["passed"])
        self.assertIn("error", declared)

    def test_t25_agentic_execution_without_declared_check_fails(self) -> None:
        # Sans AUCUN run_declared_check proposé, le run ne doit plus pouvoir
        # COMPLETED silencieusement pour AGENTIC_EXECUTION (avant : NOT_APPLICABLE).
        contract = self._agentic_contract(allowed_paths=["preuve.txt"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "open('preuve.txt', 'w').write('ok')"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertNotEqual(context.state, RunState.COMPLETED)

    def test_t33_execute_python_handles_non_cp1252_output_without_crashing(self) -> None:
        # [AJOUTÉ 18/10/2026 — bug réel trouvé en relisant le code de cette
        # session] subprocess.run sans encoding= explicite retombe sur
        # locale.getpreferredencoding() (cp1252 sur Windows) -- un print()
        # affichant un caractère hors cp1252 (ex. ⊕, emoji, certains
        # accents) faisait planter l'appel en UnicodeDecodeError au lieu
        # d'un échec propre. Reproduit ici avec un caractère connu pour
        # faire planter cp1252 (vu en vrai sur `jacobian catalog`).
        contract = self._agentic_contract(acceptance_criteria=["le script tourne"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "print('\\u2295 test unicode')"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        result = context.results[0]["result"]
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("test unicode", result["stdout"])

    def test_t38_execute_python_output_cap_kills_process_without_full_buffering(self) -> None:
        # [AJOUTÉ 19/10/2026 — faille réelle signalée par un audit externe]
        # subprocess.run(capture_output=True) capturait TOUT en mémoire
        # avant notre troncature aux derniers N caractères -- un programme
        # qui produit plusieurs Go de sortie épuisait la mémoire du harnais
        # avant même le timeout. _run_capped lit en flux et tue le process
        # dès que le plafond est dépassé. Vérifié ici qu'un programme qui
        # tenterait d'écrire ~1 Go est arrêté quasi immédiatement (pas après
        # le budget_seconds complet), avec une sortie bornée exactement au
        # plafond, pas tronquée après coup.
        contract = self._agentic_contract(budget_seconds=30, acceptance_criteria=["sortie plafonnée"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "[print('A' * 10000) for _ in range(100000)]"}},
        ]})
        import time
        t0 = time.monotonic()
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        elapsed = time.monotonic() - t0
        result = context.results[0]["result"]
        self.assertLessEqual(len(result["stdout"]), 8000)
        self.assertFalse(result["timed_out"])
        self.assertLess(elapsed, 10, "le process aurait dû être tué bien avant le budget complet")

    def test_t40_kill_switch_terminates_running_subprocess_before_its_timeout(self) -> None:
        # [AJOUTÉ 19/10/2026 — faille réelle signalée par un audit externe]
        # PolicyEngine.stop() positionnait seulement un bool consulté lors
        # de l'autorisation de la PROCHAINE opération -- un sous-processus
        # déjà lancé (execute_python ici) tournait jusqu'à son propre
        # timeout, kill switch ou pas. cancel_event (threading.Event) est
        # maintenant observé par un watchdog dans _run_capped qui tue le
        # process dès que stop() est appelé, depuis N'IMPORTE QUEL thread.
        import threading
        import time
        from nxus_harness.tools import _run_capped
        from nxus_harness.policy import PolicyEngine

        policy = PolicyEngine()
        t0 = time.monotonic()
        threading.Timer(0.3, policy.stop).start()
        result = _run_capped(["python", "-c", "import time; time.sleep(10)"], cwd=self.root,
                             timeout=10, cancel_event=policy.cancel_event)
        elapsed = time.monotonic() - t0
        self.assertTrue(result["cancelled"])
        self.assertLess(elapsed, 5, "le process aurait dû être tué par stop(), pas tourner jusqu'au timeout de 10s")

    def test_t23_execute_python_timeout_is_enforced(self) -> None:
        contract = self._agentic_contract(budget_seconds=1, acceptance_criteria=["le script tourne"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "import time; time.sleep(5)"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        self.assertTrue(context.results[0]["result"]["timed_out"])

    def test_t35_skeptical_review_is_advisory_and_never_raises(self) -> None:
        # [AJOUTÉ 19/10/2026 — inspiré par comparaison avec un autre
        # harnais, dont le "tech lead" est un LLM qui ne fait QUE donner un
        # verdict (VALIDÉ/À REFAIRE) sans aucune preuve structurelle. Ici
        # l'avis est explicitement NON CONTRAIGNANT : ce test vérifie que
        # (a) la persona méfiante et la température basse sont bien
        # transmises, (b) une panne de l'adaptateur ne fait JAMAIS échouer
        # l'appelant (c'est un avis, pas une porte de validation).
        from nxus_harness.skeptical_review import skeptical_review
        import tempfile
        from pathlib import Path

        class _RaisingAdapter:
            def structured_chat(self, *args, **kwargs):
                raise RuntimeError("llama-server indisponible")

        class _RecordingAdapter:
            def __init__(self):
                self.seen_temperature = None
            def structured_chat(self, messages, schema, json_schema=None, code_task=False, temperature_override=None):
                self.seen_temperature = temperature_override
                return {"avis": "ok"}

        tmp = Path(tempfile.mkdtemp())
        # Panne de l'adaptateur : ne doit jamais lever, juste renvoyer un texte d'indisponibilité.
        avis = skeptical_review(_RaisingAdapter(), objective="t", plan_text="p", workspace=tmp, results=[])
        self.assertIn("indisponible", avis)

        recorder = _RecordingAdapter()
        skeptical_review(recorder, objective="t", plan_text="p", workspace=tmp, results=[])
        self.assertEqual(recorder.seen_temperature, 0.1)

    def test_t34_write_workspace_draft_rejects_oversized_content(self) -> None:
        # [AJOUTÉ 19/10/2026 — checklist "entrées trop grandes", comparée à
        # un autre harnais] Aucune limite n'existait sur la taille du
        # contenu proposé -- un modèle pouvait demander l'écriture de
        # plusieurs centaines de Mo sans être refusé avant exécution.
        contract = self._agentic_contract(allowed_paths=["gros.txt"],
                                          allowed_tools=["write_workspace_draft"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "write_workspace_draft", "arguments": {"path": "gros.txt", "content": "x" * 2_000_000}},
        ]})
        with self.assertRaises(PolicyDenied):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t34_execute_python_rejects_oversized_code(self) -> None:
        contract = self._agentic_contract()
        fake = _FakeAdapter({"operations": [
            {"tool_id": "execute_python", "arguments": {"code": "# " + "x" * 300_000}},
        ]})
        with self.assertRaises(PolicyDenied):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t23_fetch_url_outside_allowlist_is_denied(self) -> None:
        contract = self._agentic_contract()
        fake = _FakeAdapter({"operations": [
            {"tool_id": "fetch_url", "arguments": {"url": "https://not-allowed.example/"}},
        ]})
        with self.assertRaises(PolicyDenied):
            self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t23_fetch_url_ssrf_guard_denies_private_hosts(self) -> None:
        # Même présent dans l'allowlist du CONTRAT, un hôte privé doit être
        # refusé par la garde SSRF de policy.py avant même le test d'allowlist :
        # une allowlist mal écrite par erreur ne doit pas suffire à l'autoriser.
        for hostile_url in ("http://127.0.0.1:8080/", "http://169.254.169.254/latest/meta-data/",
                            "http://192.168.1.1/admin", "http://10.0.0.5/"):
            contract = self._agentic_contract(allowed_urls=[hostile_url])
            fake = _FakeAdapter({"operations": [{"tool_id": "fetch_url", "arguments": {"url": hostile_url}}]})
            with self.assertRaises(PolicyDenied):
                self.engine.run_with_llm(contract, LlmPlanner(fake))

    def test_t28_fetch_url_ssrf_guard_denies_dns_rebinding(self) -> None:
        # [AJOUTÉ 18/10/2026 — finding "confirmed" du security-audit skill,
        # run-1 : la garde SSRF ne regardait QUE la chaîne du hostname,
        # jamais l'IP résolue. Un hostname à l'apparence publique ("
        # exemple.com") peut résoudre vers 127.0.0.1 (DNS rebinding réel,
        # ou ici un hostname local qui pointe légitimement vers loopback) et
        # contourner le filtre de chaîne. On simule ça avec un hostname qui
        # résout réellement vers loopback sans que la CHAÎNE ne le trahisse.
        import nxus_harness.policy as policy_module
        contract = self._agentic_contract(allowed_urls=["http://rebind-test.invalid/"])
        fake = _FakeAdapter({"operations": [
            {"tool_id": "fetch_url", "arguments": {"url": "http://rebind-test.invalid/"}},
        ]})
        original_getaddrinfo = policy_module.socket.getaddrinfo
        def fake_getaddrinfo(host, *args, **kwargs):
            if host == "rebind-test.invalid":
                return [(2, 1, 6, "", ("127.0.0.1", 0))]
            return original_getaddrinfo(host, *args, **kwargs)
        policy_module.socket.getaddrinfo = fake_getaddrinfo
        try:
            with self.assertRaises(PolicyDenied):
                self.engine.run_with_llm(contract, LlmPlanner(fake))
        finally:
            policy_module.socket.getaddrinfo = original_getaddrinfo

    def test_t23_fetch_url_within_allowlist_is_approved_and_attempted(self) -> None:
        # Pas d'accès réseau réel dans ce test (aucune garantie en CI) :
        # on vérifie que la policy ALLOW passe et que _execute est atteint
        # (il renvoie une erreur réseau proprement gérée, pas une exception).
        contract = self._agentic_contract()
        fake = _FakeAdapter({"operations": [
            {"tool_id": "fetch_url", "arguments": {"url": "https://example.invalid/data"}},
        ]})
        context = self.engine.run_with_llm(contract, LlmPlanner(fake))
        result = context.results[0]["result"]
        self.assertEqual(result["url"], "https://example.invalid/data")
        self.assertTrue(result["untrusted"])
        self.assertIn("error", result)  # example.invalid n'existe pas : erreur réseau propre, pas un crash

    def test_t39_fetch_url_rechecks_dns_at_connection_time_not_just_at_policy_time(self) -> None:
        # [AJOUTÉ 19/10/2026 — TOCTOU réel signalé par un audit externe]
        # policy.py validait l'IP résolue AVANT d'autoriser l'opération,
        # mais _execute() (tools.py) laissait ensuite urlopen() résoudre à
        # nouveau le hostname pour la VRAIE connexion -- rien ne garantissait
        # que c'était la même adresse qu'au moment de la validation (DNS à
        # TTL court, "rebinding"). Simule exactement ce scénario : le DNS
        # change ENTRE la validation (fait par le test, simulée publique) et
        # l'exécution réelle (où le hostname résout maintenant en privé).
        # _execute() doit refuser au moment de la connexion, pas seulement
        # lors d'une validation antérieure qui pourrait être périmée.
        import nxus_harness.policy as policy_module

        contract = self._agentic_contract(allowed_urls=["http://rebind-at-execute.invalid/"])
        gateway_policy = PolicyEngine()
        # Simule la policy initiale voyant une IP publique (DNS pas encore rebind).
        original_getaddrinfo = policy_module.socket.getaddrinfo
        def public_then_private(host, *args, **kwargs):
            if host == "rebind-at-execute.invalid":
                return [(2, 1, 6, "", ("8.8.8.8", 0))]
            return original_getaddrinfo(host, *args, **kwargs)
        policy_module.socket.getaddrinfo = public_then_private
        try:
            decision = gateway_policy.authorize(
                contract=contract, manifest=PlanManifest(
                    run_id="r", task_id="t", base_snapshot="x", allowed_paths=[],
                    allowed_urls=["http://rebind-at-execute.invalid/"],
                    operations=[PlannedOperation("op-1", "fetch_url", {"url": "http://rebind-at-execute.invalid/"}, RiskLevel.R2, "none")],
                    created_at="2026-01-01T00:00:00+00:00", expires_at="2026-01-01T00:10:00+00:00", plan_hash="h"),
                state=RunState.EXECUTING, tool_id="fetch_url",
                arguments={"url": "http://rebind-at-execute.invalid/"}, tool_risk=RiskLevel.R2)
            self.assertEqual(decision.outcome, "allow", "la policy initiale devrait autoriser (IP publique simulée)")
        finally:
            policy_module.socket.getaddrinfo = original_getaddrinfo

        # Au moment de l'exécution réelle, le DNS a maintenant rebind vers une IP privée.
        def private_now(host, *args, **kwargs):
            if host == "rebind-at-execute.invalid":
                return [(2, 1, 6, "", ("127.0.0.1", 0))]
            return original_getaddrinfo(host, *args, **kwargs)
        policy_module.socket.getaddrinfo = private_now
        try:
            gateway = ToolGateway(workspace=self.root / "ws3", fixtures=self.root / "fixtures",
                                  registry=ToolRegistry(), policy=PolicyEngine(),
                                  approvals=ApprovalService(self.root / "approvals3.json"),
                                  audit=AuditLog(self.root / "audit3.jsonl", run_id="r", tenant_id="t"))
            result = gateway._execute("fetch_url", {"url": "http://rebind-at-execute.invalid/"}, budget_seconds=5)
            self.assertIn("error", result)
            self.assertIn("SSRF", result["error"])
        finally:
            policy_module.socket.getaddrinfo = original_getaddrinfo

    def test_t24_fetch_url_does_not_follow_redirect_to_private_host(self) -> None:
        # [AJOUTÉ 18/10/2026] Trouvé en documentant la checklist R2+ :
        # urlopen() suit les redirections par défaut. Un serveur local
        # accessible (dans l'allowlist) qui redirige vers l'IP de métadonnées
        # cloud ne doit PAS aboutir à une requête vers cette cible.
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class _RedirectingHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass

        server = HTTPServer(("127.0.0.1", 0), _RedirectingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        # [AJOUTÉ 19/10/2026] Ce test appelle _execute() DIRECTEMENT (hors du
        # chemin policy.py normal) avec un vrai serveur de test en 127.0.0.1,
        # pour isoler la défense anti-redirection elle-même. Le nouveau
        # garde-fou TOCTOU (_execute() valide/épingle maintenant aussi l'IP
        # résolue, en profondeur, comme policy.py) refuserait ce 127.0.0.1 de
        # test AVANT même d'atteindre la redirection -- comportement correct
        # en usage réel, mais qui empêcherait ce test d'isoler ce qu'il
        # vérifie. On neutralise UNIQUEMENT la validation (pas le pinning),
        # pour ce test, en simulant "déjà autorisé par ailleurs".
        import nxus_harness.policy as policy_module
        original_resolve = policy_module.resolve_public_ips
        policy_module.resolve_public_ips = lambda host: set()
        try:
            gateway = ToolGateway(workspace=self.root / "ws2", fixtures=self.root / "fixtures",
                                  registry=ToolRegistry(), policy=PolicyEngine(),
                                  approvals=ApprovalService(self.root / "approvals2.json"),
                                  audit=AuditLog(self.root / "audit2.jsonl", run_id="r", tenant_id="t"))
            result = gateway._execute("fetch_url", {"url": f"http://127.0.0.1:{port}/"}, budget_seconds=5)
            self.assertIn("error", result)
            self.assertIn("redirection", result["error"])
        finally:
            policy_module.resolve_public_ips = original_resolve
            server.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)

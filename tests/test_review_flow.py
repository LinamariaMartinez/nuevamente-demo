"""Pruebas del grafo real con recuperación y Gemini simulados, sin API key."""

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

import graph
from agents import reviewer
from agents.retry import invoke_with_retry
from google.genai.errors import ServerError, ClientError
import test_fase3


class ReviewFlowTests(unittest.TestCase):
    def run_flow(self, scores):
        scores = iter(scores)
        drafts = []
        feedback = []

        def research(state):
            return {"retrieved_docs": [Document(page_content="Fuente VCN")],
                    "revision_attempts": 0}

        def write(state):
            feedback.append(state.get("review_feedback", ""))
            draft = f"Borrador {len(drafts) + 1}"
            drafts.append(draft)
            return {"current_draft": draft}

        def evaluate(prompt):
            return reviewer.ReviewResult(source_anchoring_score=next(scores), pedagogical_score=0.9, format_compliance_score=0.9, approved=True, feedback="Corregir dato")

        with patch.object(graph, "researcher_node", research), \
             patch.object(graph, "writer_node", write), \
             patch.object(reviewer, "ChatGoogleGenerativeAI") as model, \
             contextlib.redirect_stdout(io.StringIO()):
            model.return_value.with_structured_output.return_value = RunnableLambda(evaluate)
            result = graph.build_graph().invoke({
                "query": "VCN", "user_profile": "Principiante", "output_format": "Resumen",
                "review_feedback": "", "final_content": "Contenido anterior",
            })
        return result, drafts, feedback

    def test_approval_at_threshold(self):
        result, drafts, _ = self.run_flow([0.8])
        self.assertTrue(result["approved"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["final_content"], drafts[-1])
        self.assertEqual(result["revision_attempts"], 1)

    def test_revision_then_approval(self):
        result, drafts, feedback = self.run_flow([0.1, 0.9])
        self.assertEqual(len(drafts), 2)
        self.assertEqual(feedback, ["", "Corregir dato"])
        self.assertTrue(result["approved"])
        self.assertEqual(result["final_content"], drafts[-1])

    def test_exhaustion_never_approves(self):
        result, drafts, _ = self.run_flow([0.1, 0.1, 0.1])
        self.assertEqual(len(drafts), 3)
        self.assertEqual(result["revision_attempts"], 3)
        self.assertFalse(result["approved"])
        self.assertEqual(result["review_status"], "max_attempts_reached")
        self.assertEqual(result["final_content"], "")
        self.assertEqual(result["current_draft"], drafts[-1])

    def test_last_attempt_can_still_approve(self):
        result, drafts, _ = self.run_flow([0.1, 0.2, 0.8])
        self.assertTrue(result["approved"])
        self.assertEqual(result["revision_attempts"], 3)
        self.assertEqual(result["final_content"], drafts[-1])

    def test_score_bounds(self):
        for field in ["source_anchoring_score", "pedagogical_score", "format_compliance_score"]:
            for score in [-0.1, 1.1, float("nan"), float("inf")]:
                values = dict(source_anchoring_score=.9, pedagogical_score=.9,
                              format_compliance_score=.9, approved=True, feedback="x")
                values[field] = score
                with self.subTest(field=field, score=score), self.assertRaises(ValidationError):
                    reviewer.ReviewResult(**values)

    def test_pedagogy_and_format_are_required(self):
        for field in ['pedagogical_score', 'format_compliance_score']:
            values = dict(source_anchoring_score=1., pedagogical_score=1.,
                          format_compliance_score=1., approved=True, feedback='Corregir')
            values[field] = .5
            with patch.object(reviewer, 'ChatGoogleGenerativeAI') as model:
                model.return_value.with_structured_output.return_value = RunnableLambda(
                    lambda prompt: reviewer.ReviewResult(**values))
                result = reviewer.reviewer_node({'retrieved_docs': [Document(page_content='Fuente')],
                                                'current_draft': 'Borrador', 'revision_attempts': 2})
            self.assertFalse(result['approved'])
            self.assertTrue(result['requires_admin_review'])
            self.assertEqual(result['review_status'], 'max_attempts_reached')

    def test_missing_sources_and_empty_draft_skip_api(self):
        with patch.object(reviewer, 'ChatGoogleGenerativeAI') as model:
            for state in [{}, {'retrieved_docs': [Document(page_content='Fuente')], 'current_draft': ''}]:
                result = reviewer.reviewer_node(state)
                self.assertFalse(result['approved'])
                self.assertEqual(result['final_content'], '')
                self.assertEqual(graph.check_score(result), 'invalid_content')
            model.assert_not_called()

    def test_retry_transient_error_then_success(self):
        from unittest.mock import Mock
        chain = Mock()
        chain.invoke.side_effect = [ServerError(503, {'error': {'message': 'unavailable'}}), 'ok']
        with patch('agents.retry.time.sleep') as sleep:
            self.assertEqual(invoke_with_retry(chain, {}), 'ok')
            self.assertEqual(chain.invoke.call_count, 2)
            sleep.assert_called_once()

    def test_retry_exhaustion_and_client_errors(self):
        from unittest.mock import Mock
        chain = Mock()
        chain.invoke.side_effect = ServerError(503, {'error': {'message': 'unavailable'}})
        with patch('agents.retry.time.sleep'), self.assertRaises(ServerError):
            invoke_with_retry(chain, {})
        self.assertEqual(chain.invoke.call_count, 4)
        chain.reset_mock()
        chain.invoke.side_effect = ClientError(400, {'error': {'message': 'bad request'}})
        with self.assertRaises(ClientError):
            invoke_with_retry(chain, {})
        self.assertEqual(chain.invoke.call_count, 1)

    def test_smoke_test_fails_on_exhaustion(self):
        result, _, _ = self.run_flow([0.1, 0.1, 0.1])
        output = io.StringIO()
        with patch.object(test_fase3, "build_graph") as build, \
             contextlib.redirect_stdout(output):
            build.return_value.invoke.return_value = result
            with self.assertRaisesRegex(AssertionError, "max_attempts_reached"):
                test_fase3.main()
        self.assertIn("CONTENIDO NO APROBADO", output.getvalue())
        self.assertNotIn("CONTENIDO FINAL APROBADO", output.getvalue())

    def test_smoke_test_displays_only_approved_content(self):
        result, _, _ = self.run_flow([0.8])
        output = io.StringIO()
        with patch.object(test_fase3, "build_graph") as build, \
             contextlib.redirect_stdout(output):
            build.return_value.invoke.return_value = result
            test_fase3.main()
        self.assertIn("CONTENIDO FINAL APROBADO", output.getvalue())


if __name__ == "__main__":
    unittest.main()

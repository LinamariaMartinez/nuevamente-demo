"""Comprueba el prompt enviado al modelo sin llamadas externas."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from agents import writer
from agents.writer_examples import profile_examples


class WriterPromptTests(unittest.TestCase):
    def test_profiles_have_two_distinct_demonstrations(self):
        answers = []
        for profile in ["Principiante", "Intermedio", "Avanzado", "Docente de biología"]:
            pairs = profile_examples(profile)
            self.assertEqual([role for role, _ in pairs], ["human", "ai", "human", "ai"])
            answers.append(pairs[1][1])
            self.assertRegex(pairs[3][1], "batería|autonomía")
        self.assertEqual(len(set(answers)), 4)
        self.assertEqual(profile_examples("  AVANZADO "), profile_examples("Avanzado"))

    def test_actual_request_keeps_context_format_niche_and_feedback(self):
        captured = []
        def respond(prompt):
            captured.append(prompt.to_messages())
            return AIMessage(content="Respuesta simulada")

        with patch.object(writer, "ChatGoogleGenerativeAI", return_value=RunnableLambda(respond)):
            result = writer.writer_node({
                "user_profile": "Docente de biología", "output_format": "Paso a paso",
                "niche": "Escuela rural", "query": "Explica {tema}",
                "retrieved_docs": [Document(page_content="Fuente real con {llaves}: observar antes de registrar.")],
                "review_feedback": "No añadas cifras.",
            })
        self.assertEqual(result, {"current_draft": "Respuesta simulada"})
        messages = captured[0]
        self.assertEqual([m.type for m in messages], ["system", "human", "ai", "human", "ai", "human"])
        for text in ["Docente de biología", "Paso a paso", "Escuela rural", "No son fuentes"]:
            self.assertIn(text, messages[0].content)
        for text in ["Fuente real con {llaves}", "Explica {tema}", "No añadas cifras."]:
            self.assertIn(text, messages[-1].content)
        self.assertNotIn("Luma", messages[-1].content)
        self.assertNotIn("Nara", messages[-1].content)

    def test_missing_context_never_calls_model(self):
        with patch.object(writer, "ChatGoogleGenerativeAI") as model:
            self.assertEqual(writer.writer_node({}), {"current_draft": ""})
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()

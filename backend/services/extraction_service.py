"""
Meeting Entity Extraction Service

Extracts structured entities from meeting transcripts using the LLM.
Falls back to pattern matching when LLM is unavailable.
"""
import json
import re
from typing import Dict, List, Any, Optional

from backend.services.llm_service import get_active_provider, complete_llm
from backend.utils.logger import logger


EXTRACTION_PROMPT = """You are an expert meeting analyst. Extract structured information from the following meeting transcript.

Return a JSON object with exactly these keys:
{
  "summary": "2-3 sentence summary of the meeting",
  "participants": ["list of person names mentioned"],
  "projects": ["list of project names mentioned"],
  "topics": ["list of main topics discussed"],
  "decisions": [
    {
      "title": "Decision title",
      "description": "What was decided",
      "assigned_to": "person name or null",
      "pros": ["list of advantages"],
      "cons": ["list of disadvantages"],
      "reasons": ["list of reasons for this decision"]
    }
  ],
  "tasks": [
    {
      "title": "Task title",
      "description": "Task details",
      "assigned_to": "person name or null",
      "due_date": "YYYY-MM-DD or null",
      "status": "open"
    }
  ],
  "risks": ["list of risks mentioned"],
  "blockers": ["list of blockers or impediments"],
  "questions": ["list of open questions"],
  "documents": ["list of documents or links mentioned"]
}

Meeting Transcript:
{transcript}

Return ONLY valid JSON, no markdown, no explanation."""


class ExtractionService:
    """Extracts entities from meeting transcripts via the active cloud LLM (Gemini/Groq/OpenAI)."""

    async def extract_from_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Extract all entities from a meeting transcript.
        Tries LLM first, falls back to pattern matching.
        """
        try:
            result = await self._extract_with_llm(transcript)
            if result:
                return result
        except Exception as e:
            logger.warning("LLM extraction failed, using patterns: {}", str(e))

        return self._extract_with_patterns(transcript)

    async def _extract_with_llm(self, transcript: str) -> Optional[Dict[str, Any]]:
        """Call the active LLM provider (Gemini by default) to extract entities."""
        provider = get_active_provider()
        prompt = EXTRACTION_PROMPT.replace("{transcript}", transcript[:8000])
        raw = await complete_llm(
            provider,
            messages=[{"role": "user", "content": prompt}],
        )

        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        return None

    def _extract_with_patterns(self, transcript: str) -> Dict[str, Any]:
        """
        Pattern-based extraction as fallback.
        Identifies common meeting patterns heuristically.
        """
        lines = transcript.split('\n')

        participants = self._extract_speakers(transcript)
        decisions = self._extract_decisions(transcript)
        tasks = self._extract_tasks(transcript)
        risks = self._extract_risks(transcript)
        blockers = self._extract_blockers(transcript)
        topics = self._extract_topics(transcript)
        projects = self._extract_projects(transcript)

        summary = self._generate_summary(transcript)

        return {
            "summary": summary,
            "participants": participants,
            "projects": projects,
            "topics": topics,
            "decisions": decisions,
            "tasks": tasks,
            "risks": risks,
            "blockers": blockers,
            "questions": self._extract_questions(transcript),
            "documents": self._extract_documents(transcript),
        }

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from transcript patterns like 'Name:' or '[Name]'."""
        patterns = [
            r'^([A-Z][a-z]+ [A-Z][a-z]+)\s*:',
            r'^\[([A-Z][a-z]+ [A-Z][a-z]+)\]',
            r'^([A-Z][a-z]+)\s*:',
        ]
        speakers = set()
        for line in text.split('\n'):
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    name = match.group(1).strip()
                    if len(name) > 2 and name not in {'The', 'We', 'It', 'This'}:
                        speakers.add(name)
        return list(speakers)[:10]

    def _extract_decisions(self, text: str) -> List[Dict]:
        """Extract decision statements."""
        decision_patterns = [
            r'(?:we decided|decision:|decided to|agreed to|will use|going with|chose to)\s+([^.!?\n]+)',
            r'(?:the decision is|final decision:|conclusion:)\s+([^.!?\n]+)',
        ]
        decisions = []
        for pattern in decision_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:5]:
                decisions.append({
                    "title": match.strip()[:100],
                    "description": match.strip(),
                    "assigned_to": None,
                    "pros": [],
                    "cons": [],
                    "reasons": [],
                })
        return decisions

    def _extract_tasks(self, text: str) -> List[Dict]:
        """Extract action items and tasks."""
        task_patterns = [
            r'(?:action item:|todo:|will|needs to|should|must)\s+([^.!?\n]+)',
            r'([A-Z][a-z]+)\s+(?:will|needs to|should)\s+([^.!?\n]+)',
        ]
        tasks = []
        for pattern in task_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:8]:
                title = (match if isinstance(match, str) else ' '.join(match)).strip()
                tasks.append({
                    "title": title[:150],
                    "description": title,
                    "assigned_to": None,
                    "due_date": None,
                    "status": "open",
                })
        return tasks

    def _extract_risks(self, text: str) -> List[str]:
        """Extract risk statements."""
        patterns = [
            r'(?:risk:|concern:|worried about|risk of|might break|could fail)\s+([^.!?\n]+)',
        ]
        risks = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            risks.extend([m.strip()[:200] for m in matches[:5]])
        return risks

    def _extract_blockers(self, text: str) -> List[str]:
        """Extract blockers."""
        patterns = [
            r'(?:blocked by|blocker:|blocking us|can\'t proceed|waiting on)\s+([^.!?\n]+)',
        ]
        blockers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            blockers.extend([m.strip()[:200] for m in matches[:5]])
        return blockers

    def _extract_topics(self, text: str) -> List[str]:
        """Extract main topics via keyword frequency."""
        tech_terms = [
            'authentication', 'authorization', 'api', 'database', 'kubernetes',
            'docker', 'microservices', 'oauth', 'jwt', 'ci/cd', 'deployment',
            'security', 'performance', 'scalability', 'migration', 'refactor',
            'sprint', 'architecture', 'infrastructure', 'monitoring', 'logging',
        ]
        text_lower = text.lower()
        found = [t for t in tech_terms if t in text_lower]
        return found[:8]

    def _extract_projects(self, text: str) -> List[str]:
        """Extract project names (capitalized noun phrases)."""
        # Look for "Project X" patterns or capitalized multi-word names
        patterns = [
            r'(?:Project|project)\s+([A-Z][a-zA-Z]+)',
            r'\b([A-Z][a-zA-Z]+ (?:Platform|Service|System|App|API|Module|Dashboard))\b',
        ]
        projects = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            projects.extend(matches)
        return list(set(projects))[:5]

    def _extract_questions(self, text: str) -> List[str]:
        """Extract open questions."""
        questions = []
        for line in text.split('\n'):
            line = line.strip()
            if line.endswith('?') and len(line) > 10:
                questions.append(line[:200])
        return questions[:5]

    def _extract_documents(self, text: str) -> List[str]:
        """Extract document or URL references."""
        patterns = [
            r'(?:confluence|jira|notion|docs?|ticket|PR|RFC|spec)\s*[:#]?\s*([A-Z0-9\-/]+)',
            r'https?://\S+',
        ]
        docs = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            docs.extend([m.strip()[:200] for m in matches[:5]])
        return docs

    def _generate_summary(self, text: str) -> str:
        """Generate a basic summary from the first few lines."""
        lines = [l.strip() for l in text.split('\n') if l.strip()][:5]
        return ' '.join(lines)[:500] if lines else "Meeting transcript"


extraction_service = ExtractionService()

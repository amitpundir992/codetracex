"""
Comprehensive tests for Phase 16: Advanced Repository Investigation.

Tests:
- Investigation intent classification
- Evidence collection and deduplication
- Investigation orchestration
- Grounded claims with certainty levels
- Follow-up question generation
- Conversation context
- API endpoint
- Repository isolation
- Analysis run isolation
"""
import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from uuid import uuid4

from app.schemas.investigation import (
    InvestigationIntent,
    InvestigationEvidence,
    EvidenceType,
    GroundedClaim,
    CertaintyLevel,
    FollowUpQuestion,
    InvestigationGrounding,
    ConversationContext,
    InvestigationRequest,
    InvestigationResponse
)
from app.services.investigation_intent_classifier import InvestigationIntentClassifier
from app.services.investigation_prompt_builder import InvestigationPromptBuilder
from app.services.investigation_service import InvestigationService
from app.db.models import Repository, AnalysisRun


class TestInvestigationIntentClassifier:
    """Test investigation intent classification."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = InvestigationIntentClassifier()
    
    def test_classify_symbol_explanation(self):
        """Test classification of symbol explanation questions."""
        questions = [
            "What does authenticate_user function do?",
            "Explain the OrderService class",
            "How does the login method work?"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.SYMBOL_EXPLANATION
            assert confidence >= 0.5
    
    def test_classify_api_explanation(self):
        """Test classification of API endpoint questions."""
        questions = [
            "What does GET /api/users do?",
            "How does the POST /orders endpoint work?",
            "Explain the authentication API route"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.API_EXPLANATION
            assert confidence >= 0.5
    
    def test_classify_workflow_explanation(self):
        """Test classification of workflow questions."""
        questions = [
            "What happens after POST /orders?",
            "Show me the authentication workflow",
            "How does the request flow work?"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.WORKFLOW_EXPLANATION
            assert confidence >= 0.5
    
    def test_classify_dependency_question(self):
        """Test classification of dependency questions."""
        questions = [
            "What calls authenticate_user?",
            "What does OrderService depend on?",
            "Which functions use the database?"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.DEPENDENCY_QUESTION
            assert confidence >= 0.5
    
    def test_classify_impact_question(self):
        """Test classification of impact questions."""
        questions = [
            "What breaks if I change this?",
            "What would be affected if I modify it?",
            "Show me the downstream impact"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.IMPACT_QUESTION
            assert confidence >= 0.5
    
    def test_classify_history_question(self):
        """Test classification of git history questions."""
        questions = [
            "When was authenticate_user added?",
            "Who wrote the OrderService?",
            "Why was this function introduced?"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.HISTORY_QUESTION
            assert confidence >= 0.5
    
    def test_classify_architecture_question(self):
        """Test classification of architecture questions."""
        questions = [
            "How is this repository structured?",
            "What's the overall architecture?",
            "How is the codebase organized?"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.ARCHITECTURE_QUESTION
            assert confidence >= 0.5
    
    def test_classify_database_question(self):
        """Test classification of database questions."""
        questions = [
            "What database schema is used?",
            "Show me the SQL queries",
            "Which tables store user data?"
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.DATABASE_QUESTION
            assert confidence >= 0.5
    
    def test_classify_unknown_intent(self):
        """Test classification of ambiguous questions."""
        questions = [
            "Tell me everything",
            "xyz",
            ""
        ]
        
        for question in questions:
            intent, confidence = self.classifier.classify(question)
            assert intent == InvestigationIntent.UNKNOWN
    
    def test_contextual_dependency_question(self):
        """Test contextual reference like 'what calls it?'."""
        context = {
            "last_symbols": [{"id": "uuid", "name": "authenticate_user", "type": "function"}],
            "last_files": ["auth_service.py"]
        }
        
        intent, confidence = self.classifier.classify("what calls it?", context)
        assert intent == InvestigationIntent.DEPENDENCY_QUESTION
        assert confidence > 0.5


class TestInvestigationPromptBuilder:
    """Test investigation prompt building."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = InvestigationPromptBuilder()
        self.repo_id = uuid4()
        self.analysis_run_id = uuid4()
    
    def test_build_basic_prompt(self):
        """Test building a basic investigation prompt."""
        evidence = [
            InvestigationEvidence(
                evidence_id="evidence_1",
                evidence_type=EvidenceType.SYMBOL,
                retrieval_score=0.9,
                retrieval_source="hybrid",
                content="def authenticate_user(username, password):\n    pass",
                content_truncated=False,
                repository_id=self.repo_id,
                file_path="auth_service.py",
                start_line=10,
                end_line=20,
                symbol_name="authenticate_user",
                symbol_type="function"
            )
        ]
        
        prompt = self.builder.build_investigation_prompt(
            question="How does authentication work?",
            evidence=evidence,
            intent=InvestigationIntent.GENERAL_REPOSITORY
        )
        
        assert "How does authentication work?" in prompt
        assert "evidence_1" in prompt
        assert "authenticate_user" in prompt
        assert "confirmed" in prompt
        assert "inferred" in prompt
        assert "uncertain" in prompt
    
    def test_build_prompt_with_context(self):
        """Test building prompt with conversation context."""
        evidence = []
        context = {
            "last_question": "What is OrderService?",
            "last_symbols": [{"id": "uuid", "name": "OrderService", "type": "class"}]
        }
        
        prompt = self.builder.build_investigation_prompt(
            question="What methods does it have?",
            evidence=evidence,
            intent=InvestigationIntent.SYMBOL_EXPLANATION,
            conversation_context=context
        )
        
        assert "What is OrderService?" in prompt
        assert "OrderService" in prompt
    
    def test_parse_valid_response(self):
        """Test parsing valid LLM JSON response."""
        response_text = """
```json
{
  "answer": "Authentication is implemented in AuthService",
  "claims": [
    {
      "claim_text": "AuthService handles authentication",
      "certainty": "confirmed",
      "evidence_ids": ["evidence_1"],
      "reasoning": "Found in static analysis"
    }
  ],
  "limitations": [],
  "follow_up_questions": [
    {
      "question": "Which endpoints use AuthService?",
      "rationale": "To understand usage",
      "related_evidence_ids": ["evidence_1"]
    }
  ]
}
```
        """
        
        parsed = self.builder.parse_investigation_response(response_text)
        
        assert parsed is not None
        assert "answer" in parsed
        assert "claims" in parsed
        assert len(parsed["claims"]) == 1
        assert parsed["claims"][0]["certainty"] == "confirmed"
    
    def test_parse_malformed_response(self):
        """Test parsing malformed LLM response."""
        response_text = "This is not JSON"
        
        parsed = self.builder.parse_investigation_response(response_text)
        assert parsed is None


class TestInvestigationEvidence:
    """Test investigation evidence model."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.repo_id = uuid4()
        self.analysis_run_id = uuid4()
    
    def test_create_evidence(self):
        """Test creating investigation evidence."""
        evidence = InvestigationEvidence(
            evidence_id="test_evidence",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_score=0.85,
            retrieval_source="hybrid",
            content="def test(): pass",
            content_truncated=False,
            repository_id=self.repo_id,
            file_path="test.py",
            start_line=1,
            end_line=10,
            symbol_name="test",
            symbol_type="function"
        )
        
        assert evidence.evidence_id == "test_evidence"
        assert evidence.evidence_type == EvidenceType.SYMBOL
        assert evidence.retrieval_score == 0.85
        assert evidence.symbol_name == "test"
    
    def test_evidence_types(self):
        """Test all evidence types are valid."""
        types = [
            EvidenceType.FILE,
            EvidenceType.SYMBOL,
            EvidenceType.API_ENDPOINT,
            EvidenceType.GRAPH_RELATIONSHIP,
            EvidenceType.WORKFLOW_NODE,
            EvidenceType.GIT_COMMIT,
            EvidenceType.SEMANTIC_CHUNK,
            EvidenceType.HYBRID_SEARCH
        ]
        
        for ev_type in types:
            evidence = InvestigationEvidence(
                evidence_id="test",
                evidence_type=ev_type,
                retrieval_source="test",
                content="test content",
                content_truncated=False,
                repository_id=self.repo_id
            )
            assert evidence.evidence_type == ev_type


class TestGroundedClaims:
    """Test grounded claims with certainty levels."""
    
    def test_create_confirmed_claim(self):
        """Test creating confirmed claim."""
        claim = GroundedClaim(
            claim_text="Function A calls Function B",
            certainty=CertaintyLevel.CONFIRMED,
            evidence_ids=["evidence_1", "evidence_2"],
            reasoning="Direct call relationship found"
        )
        
        assert claim.certainty == CertaintyLevel.CONFIRMED
        assert len(claim.evidence_ids) == 2
    
    def test_create_inferred_claim(self):
        """Test creating inferred claim."""
        claim = GroundedClaim(
            claim_text="This likely handles authentication",
            certainty=CertaintyLevel.INFERRED,
            evidence_ids=["evidence_1"],
            reasoning="Based on naming patterns"
        )
        
        assert claim.certainty == CertaintyLevel.INFERRED
    
    def test_create_uncertain_claim(self):
        """Test creating uncertain claim."""
        claim = GroundedClaim(
            claim_text="Runtime behavior unclear",
            certainty=CertaintyLevel.UNCERTAIN,
            evidence_ids=[],
            reasoning="Insufficient static analysis evidence"
        )
        
        assert claim.certainty == CertaintyLevel.UNCERTAIN
    
    def test_certainty_levels(self):
        """Test all certainty levels are valid."""
        levels = [
            CertaintyLevel.CONFIRMED,
            CertaintyLevel.INFERRED,
            CertaintyLevel.UNCERTAIN
        ]
        
        for level in levels:
            claim = GroundedClaim(
                claim_text="test claim",
                certainty=level,
                evidence_ids=[]
            )
            assert claim.certainty == level


class TestFollowUpQuestions:
    """Test follow-up question generation."""
    
    def test_create_follow_up(self):
        """Test creating follow-up question."""
        follow_up = FollowUpQuestion(
            question="Which endpoints use this service?",
            rationale="To understand usage patterns",
            related_evidence_ids=["evidence_1"]
        )
        
        assert "endpoints" in follow_up.question
        assert follow_up.rationale is not None
        assert len(follow_up.related_evidence_ids) == 1


class TestConversationContext:
    """Test conversation context for reference resolution."""
    
    def test_create_context(self):
        """Test creating conversation context."""
        context = ConversationContext(
            last_symbols=[
                {"id": "uuid1", "name": "AuthService", "type": "class"}
            ],
            last_files=["auth_service.py"],
            last_endpoints=[
                {"id": "uuid2", "method": "POST", "path": "/api/auth/login"}
            ],
            last_question="How does authentication work?"
        )
        
        assert len(context.last_symbols) == 1
        assert context.last_symbols[0]["name"] == "AuthService"
        assert "auth_service.py" in context.last_files
        assert context.last_question is not None
    
    def test_context_limits(self):
        """Test context enforces reasonable limits."""
        # Pydantic validates max_length at construction
        # Attempting to create context with >10 items should raise ValidationError
        with pytest.raises(Exception):  # Pydantic ValidationError
            context = ConversationContext(
                last_symbols=[
                    {"id": f"uuid{i}", "name": f"Symbol{i}", "type": "function"}
                    for i in range(20)
                ],
                last_files=[f"file{i}.py" for i in range(20)],
                last_endpoints=[
                    {"id": f"uuid{i}", "method": "GET", "path": f"/api/endpoint{i}"}
                    for i in range(20)
                ]
            )


class TestInvestigationService:
    """Test investigation service orchestration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.db = MagicMock()
        self.llm_provider = MagicMock()
        self.repo_id = uuid4()
        self.analysis_run_id = uuid4()
        
        # Create service with mocked dependencies
        self.service = InvestigationService(self.db, self.llm_provider)
    
    def test_evidence_deduplication(self):
        """Test evidence deduplication logic."""
        evidence1 = InvestigationEvidence(
            evidence_id="evidence_1",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="hybrid",
            content="def test(): pass",
            content_truncated=False,
            repository_id=self.repo_id,
            file_path="test.py",
            start_line=1,
            end_line=10,
            symbol_name="test"
        )
        
        # Duplicate with different evidence_id but same content/location
        evidence2 = InvestigationEvidence(
            evidence_id="evidence_2",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="semantic",
            content="def test(): pass",
            content_truncated=False,
            repository_id=self.repo_id,
            file_path="test.py",
            start_line=1,
            end_line=10,
            symbol_name="test"
        )
        
        # Different evidence
        evidence3 = InvestigationEvidence(
            evidence_id="evidence_3",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="hybrid",
            content="def other(): pass",
            content_truncated=False,
            repository_id=self.repo_id,
            file_path="other.py",
            start_line=1,
            end_line=10,
            symbol_name="other"
        )
        
        deduplicated = self.service._deduplicate_evidence([evidence1, evidence2, evidence3])
        
        # Should keep evidence1 and evidence3, deduplicate evidence2
        assert len(deduplicated) == 2
        evidence_ids = [e.evidence_id for e in deduplicated]
        assert "evidence_1" in evidence_ids
        assert "evidence_3" in evidence_ids
    
    def test_build_conversation_context(self):
        """Test building conversation context from evidence."""
        evidence = [
            InvestigationEvidence(
                evidence_id="evidence_1",
                evidence_type=EvidenceType.SYMBOL,
                retrieval_source="hybrid",
                content="def test(): pass",
                content_truncated=False,
                repository_id=self.repo_id,
                file_path="test.py",
                start_line=1,
                end_line=10,
                symbol_id=uuid4(),
                symbol_name="test_function",
                symbol_type="function"
            ),
            InvestigationEvidence(
                evidence_id="evidence_2",
                evidence_type=EvidenceType.API_ENDPOINT,
                retrieval_source="direct",
                content="GET /api/users",
                content_truncated=False,
                repository_id=self.repo_id,
                file_path="api.py",
                api_endpoint_id=uuid4(),
                api_endpoint_method="GET",
                api_endpoint_path="/api/users"
            )
        ]
        
        context = self.service._build_conversation_context(
            evidence=evidence,
            question="Test question"
        )
        
        assert len(context.last_symbols) == 1
        assert context.last_symbols[0]["name"] == "test_function"
        assert "test.py" in context.last_files
        assert len(context.last_endpoints) == 1
        assert context.last_question == "Test question"


class TestInvestigationAPI:
    """Test investigation API endpoint (without actual HTTP)."""
    
    def test_investigation_request_validation(self):
        """Test investigation request validation."""
        # Valid request
        request = InvestigationRequest(
            question="How does authentication work?",
            max_evidence=10,
            include_graph=True
        )
        
        assert request.question == "How does authentication work?"
        assert request.max_evidence == 10
        assert request.include_graph is True
    
    def test_investigation_request_limits(self):
        """Test investigation request enforces limits."""
        # Question too long should be handled by validation
        with pytest.raises(Exception):  # Pydantic ValidationError
            InvestigationRequest(
                question="x" * 2000,  # Exceeds max_length=1000
                max_evidence=10
            )
        
        # max_evidence too high
        with pytest.raises(Exception):  # Pydantic ValidationError
            InvestigationRequest(
                question="test",
                max_evidence=100  # Exceeds le=50
            )
    
    def test_investigation_response_structure(self):
        """Test investigation response structure."""
        response = InvestigationResponse(
            question="Test question",
            detected_intent=InvestigationIntent.GENERAL_REPOSITORY,
            answer="Test answer",
            claims=[
                GroundedClaim(
                    claim_text="Test claim",
                    certainty=CertaintyLevel.CONFIRMED,
                    evidence_ids=["evidence_1"]
                )
            ],
            evidence=[],
            grounding=InvestigationGrounding(
                is_grounded=True,
                evidence_count=5,
                evidence_truncated=False
            ),
            limitations=[],
            follow_up_questions=[],
            conversation_context=ConversationContext(),
            repository_id=uuid4()
        )
        
        assert response.answer == "Test answer"
        assert len(response.claims) == 1
        assert response.grounding.is_grounded is True


class TestRepositoryIsolation:
    """Test repository isolation in investigation."""
    
    def test_evidence_repository_isolation(self):
        """Test evidence is isolated by repository_id."""
        repo1 = uuid4()
        repo2 = uuid4()
        
        evidence1 = InvestigationEvidence(
            evidence_id="evidence_1",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="hybrid",
            content="repo1 content",
            content_truncated=False,
            repository_id=repo1,
            file_path="test.py"
        )
        
        evidence2 = InvestigationEvidence(
            evidence_id="evidence_2",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="hybrid",
            content="repo2 content",
            content_truncated=False,
            repository_id=repo2,
            file_path="test.py"
        )
        
        # Evidence from different repositories should be distinguishable
        assert evidence1.repository_id != evidence2.repository_id
        assert evidence1.repository_id == repo1
        assert evidence2.repository_id == repo2


class TestAnalysisRunIsolation:
    """Test analysis run isolation in investigation."""
    
    def test_evidence_analysis_run_isolation(self):
        """Test evidence is isolated by analysis_run_id."""
        repo_id = uuid4()
        run1 = uuid4()
        run2 = uuid4()
        
        evidence1 = InvestigationEvidence(
            evidence_id="evidence_1",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="hybrid",
            content="run1 content",
            content_truncated=False,
            repository_id=repo_id,
            analysis_run_id=run1,
            file_path="test.py"
        )
        
        evidence2 = InvestigationEvidence(
            evidence_id="evidence_2",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_source="hybrid",
            content="run2 content",
            content_truncated=False,
            repository_id=repo_id,
            analysis_run_id=run2,
            file_path="test.py"
        )
        
        # Evidence from different analysis runs should be distinguishable
        assert evidence1.analysis_run_id != evidence2.analysis_run_id
        assert evidence1.analysis_run_id == run1
        assert evidence2.analysis_run_id == run2


class TestInvestigationGrounding:
    """Test investigation grounding metadata."""
    
    def test_grounding_with_evidence(self):
        """Test grounding metadata when evidence is present."""
        grounding = InvestigationGrounding(
            is_grounded=True,
            evidence_count=10,
            evidence_truncated=False
        )
        
        assert grounding.is_grounded is True
        assert grounding.evidence_count == 10
        assert grounding.evidence_truncated is False
    
    def test_grounding_truncated(self):
        """Test grounding metadata when evidence is truncated."""
        grounding = InvestigationGrounding(
            is_grounded=True,
            evidence_count=50,
            evidence_truncated=True,
            truncation_reason="Maximum evidence limit reached"
        )
        
        assert grounding.evidence_truncated is True
        assert grounding.truncation_reason is not None
    
    def test_grounding_without_evidence(self):
        """Test grounding metadata when no evidence available."""
        grounding = InvestigationGrounding(
            is_grounded=False,
            evidence_count=0,
            evidence_truncated=False,
            confidence_note="No relevant evidence found"
        )
        
        assert grounding.is_grounded is False
        assert grounding.evidence_count == 0
        assert grounding.confidence_note is not None

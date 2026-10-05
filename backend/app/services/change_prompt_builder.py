"""
Change Prompt Builder for Phase 18: Pull Request & Change Intelligence.

This service builds prompts for LLM-based change explanation with explicit
grounding constraints.

Architecture Philosophy:

    GROUNDED LLM REASONING
    
    The LLM must:
    - Use ONLY supplied evidence
    - NOT invent files, symbols, APIs, tests
    - NOT invent runtime behavior
    - Distinguish facts from inference
    - Explicitly state insufficient evidence
    - NOT expose secrets
    
    The prompt explicitly instructs the LLM on these constraints.
    
    Evidence Format:
    - File changes (deterministic)
    - Symbol changes (with uncertainty)
    - API impacts (with evidence)
    - Workflow impacts (bounded)
    - Dependency impacts (truncated if needed)
    - Risk signals (deterministic)
    
    Output Format:
    - Summary
    - Technical changes
    - Reviewer attention points
    - Testing considerations
    - Potential impact
    - Uncertainty / insufficient evidence

Security:
    - No secret exposure
    - No credential leakage
    - Safe error handling
"""
from typing import List, Dict, Optional, Any
import logging

from app.schemas.change_analysis import (
    ChangedFile, ChangedSymbol, AffectedEndpoint, AffectedWorkflow,
    DependencyImpact, RelevantTest, ChangeRisk, ChangeEvidence,
    PRMetadata
)

logger = logging.getLogger(__name__)


class ChangePromptBuilder:
    """
    Service for building grounded change analysis prompts.
    
    Constructs prompts that explicitly constrain LLM behavior to
    prevent invention and ensure grounding in repository evidence.
    """
    
    MAX_FILES_IN_PROMPT = 30
    MAX_SYMBOLS_IN_PROMPT = 40
    MAX_EVIDENCE_ITEMS = 50
    
    def __init__(self):
        """Initialize prompt builder."""
        pass
    
    def _format_pr_metadata(self, pr_metadata: Optional[PRMetadata]) -> str:
        """
        Format PR metadata for prompt.
        
        Args:
            pr_metadata: Optional PR metadata
            
        Returns:
            Formatted string
        """
        if not pr_metadata:
            return ""
        
        parts = [
            "## Pull Request Metadata\n",
            f"**PR #{pr_metadata.number}: {pr_metadata.title}**\n",
            f"Author: {pr_metadata.author}\n",
            f"State: {pr_metadata.state}\n",
            f"Base: {pr_metadata.base_ref} → Head: {pr_metadata.head_ref}\n",
        ]
        
        if pr_metadata.body:
            # Truncate long descriptions
            body = pr_metadata.body[:500]
            if len(pr_metadata.body) > 500:
                body += "..."
            parts.append(f"\nDescription:\n{body}\n")
        
        return "\n".join(parts)
    
    def _format_file_changes(self, changed_files: List[ChangedFile]) -> str:
        """
        Format file changes for prompt.
        
        Args:
            changed_files: List of changed files
            
        Returns:
            Formatted string
        """
        if not changed_files:
            return "No file changes detected.\n"
        
        parts = [f"## File Changes ({len(changed_files)} files)\n"]
        
        # Group by change type
        added = [f for f in changed_files if f.change_type.value == "added"]
        modified = [f for f in changed_files if f.change_type.value == "modified"]
        deleted = [f for f in changed_files if f.change_type.value == "deleted"]
        renamed = [f for f in changed_files if f.change_type.value == "renamed"]
        
        if added:
            parts.append(f"\n**Added ({len(added)}):**")
            for f in added[:self.MAX_FILES_IN_PROMPT]:
                lang = f" [{f.language}]" if f.language else ""
                parts.append(f"- {f.path}{lang} (+{f.additions})")
        
        if modified:
            parts.append(f"\n**Modified ({len(modified)}):**")
            for f in modified[:self.MAX_FILES_IN_PROMPT]:
                lang = f" [{f.language}]" if f.language else ""
                parts.append(f"- {f.path}{lang} (+{f.additions}, -{f.deletions})")
        
        if deleted:
            parts.append(f"\n**Deleted ({len(deleted)}):**")
            for f in deleted[:self.MAX_FILES_IN_PROMPT]:
                parts.append(f"- {f.path} (-{f.deletions})")
        
        if renamed:
            parts.append(f"\n**Renamed ({len(renamed)}):**")
            for f in renamed[:self.MAX_FILES_IN_PROMPT]:
                parts.append(f"- {f.old_path} → {f.path}")
        
        total_shown = len(added[:self.MAX_FILES_IN_PROMPT]) + len(modified[:self.MAX_FILES_IN_PROMPT]) + \
                      len(deleted[:self.MAX_FILES_IN_PROMPT]) + len(renamed[:self.MAX_FILES_IN_PROMPT])
        
        if total_shown < len(changed_files):
            parts.append(f"\n*...and {len(changed_files) - total_shown} more files*")
        
        return "\n".join(parts)
    
    def _format_symbol_changes(self, changed_symbols: List[ChangedSymbol]) -> str:
        """
        Format symbol changes for prompt.
        
        Args:
            changed_symbols: List of changed symbols
            
        Returns:
            Formatted string
        """
        if not changed_symbols:
            return "No symbol-level changes identified.\n"
        
        parts = [f"## Symbol Changes ({len(changed_symbols)} symbols)\n"]
        parts.append("*Note: Symbol modification detection has uncertainty without semantic diff.*\n")
        
        # Group by change type
        added = [s for s in changed_symbols if s.change_type.value == "added"]
        modified = [s for s in changed_symbols if s.change_type.value == "modified"]
        deleted = [s for s in changed_symbols if s.change_type.value == "deleted"]
        
        if added:
            parts.append(f"\n**Added ({len(added)}):**")
            for s in added[:self.MAX_SYMBOLS_IN_PROMPT]:
                public = " [PUBLIC]" if s.is_public else ""
                parts.append(f"- {s.symbol_type}: {s.qualified_name}{public}")
        
        if modified:
            parts.append(f"\n**Potentially Modified ({len(modified)}):**")
            for s in modified[:self.MAX_SYMBOLS_IN_PROMPT]:
                public = " [PUBLIC]" if s.is_public else ""
                parts.append(f"- {s.symbol_type}: {s.qualified_name}{public}")
        
        if deleted:
            parts.append(f"\n**Deleted ({len(deleted)}):**")
            for s in deleted[:self.MAX_SYMBOLS_IN_PROMPT]:
                parts.append(f"- {s.symbol_type}: {s.qualified_name}")
        
        total_shown = len(added[:self.MAX_SYMBOLS_IN_PROMPT]) + len(modified[:self.MAX_SYMBOLS_IN_PROMPT]) + \
                      len(deleted[:self.MAX_SYMBOLS_IN_PROMPT])
        
        if total_shown < len(changed_symbols):
            parts.append(f"\n*...and {len(changed_symbols) - total_shown} more symbols*")
        
        return "\n".join(parts)
    
    def _format_affected_apis(self, affected_endpoints: List[AffectedEndpoint]) -> str:
        """
        Format affected API endpoints for prompt.
        
        Args:
            affected_endpoints: List of affected endpoints
            
        Returns:
            Formatted string
        """
        if not affected_endpoints:
            return "No API endpoints identified as affected.\n"
        
        parts = [f"## Affected API Endpoints ({len(affected_endpoints)})\n"]
        
        for endpoint in affected_endpoints[:20]:
            directly = " [DIRECTLY AFFECTED]" if endpoint.directly_affected else " [INDIRECTLY AFFECTED]"
            handler = f" (handler: {endpoint.handler})" if endpoint.handler else ""
            parts.append(f"- {endpoint.method} {endpoint.route}{handler}{directly}")
        
        if len(affected_endpoints) > 20:
            parts.append(f"\n*...and {len(affected_endpoints) - 20} more endpoints*")
        
        return "\n".join(parts)
    
    def _format_affected_workflows(self, affected_workflows: List[AffectedWorkflow]) -> str:
        """
        Format affected workflows for prompt.
        
        Args:
            affected_workflows: List of affected workflows
            
        Returns:
            Formatted string
        """
        if not affected_workflows:
            return "No workflows identified as affected.\n"
        
        parts = [f"## Affected Workflows ({len(affected_workflows)})\n"]
        
        for workflow in affected_workflows[:10]:
            parts.append(
                f"- {workflow.entry_point}: {len(workflow.changed_nodes)}/{workflow.total_nodes} nodes affected"
            )
            if workflow.changed_nodes:
                nodes = ", ".join(workflow.changed_nodes[:5])
                if len(workflow.changed_nodes) > 5:
                    nodes += f", ...and {len(workflow.changed_nodes) - 5} more"
                parts.append(f"  Changed nodes: {nodes}")
        
        if len(affected_workflows) > 10:
            parts.append(f"\n*...and {len(affected_workflows) - 10} more workflows*")
        
        return "\n".join(parts)
    
    def _format_dependency_impact(self, dependency_impact: DependencyImpact) -> str:
        """
        Format dependency impact for prompt.
        
        Args:
            dependency_impact: Dependency impact data
            
        Returns:
            Formatted string
        """
        parts = ["## Dependency Impact\n"]
        
        parts.append(f"Traversal depth: {dependency_impact.traversal_depth}")
        if dependency_impact.truncated:
            parts.append("**WARNING: Results truncated due to graph size limits**\n")
        
        if dependency_impact.affected_callers:
            parts.append(f"\n**Affected Callers ({len(dependency_impact.affected_callers)}):**")
            for caller in dependency_impact.affected_callers[:15]:
                parts.append(f"- {caller}")
            if len(dependency_impact.affected_callers) > 15:
                parts.append(f"*...and {len(dependency_impact.affected_callers) - 15} more*")
        
        if dependency_impact.affected_callees:
            parts.append(f"\n**Affected Callees ({len(dependency_impact.affected_callees)}):**")
            for callee in dependency_impact.affected_callees[:15]:
                parts.append(f"- {callee}")
            if len(dependency_impact.affected_callees) > 15:
                parts.append(f"*...and {len(dependency_impact.affected_callees) - 15} more*")
        
        if dependency_impact.affected_files:
            parts.append(f"\n**Affected Files ({len(dependency_impact.affected_files)}):**")
            for file_path in dependency_impact.affected_files[:10]:
                parts.append(f"- {file_path}")
            if len(dependency_impact.affected_files) > 10:
                parts.append(f"*...and {len(dependency_impact.affected_files) - 10} more*")
        
        return "\n".join(parts)
    
    def _format_relevant_tests(self, relevant_tests: List[RelevantTest]) -> str:
        """
        Format relevant tests for prompt.
        
        Args:
            relevant_tests: List of relevant tests
            
        Returns:
            Formatted string
        """
        if not relevant_tests:
            return "No tests identified as potentially relevant.\n"
        
        parts = [f"## Potentially Relevant Tests ({len(relevant_tests)})\n"]
        parts.append("*Note: Test relevance is based on heuristics, not execution.*\n")
        
        for test in relevant_tests[:20]:
            relationship = test.relationship.replace('_', ' ')
            parts.append(
                f"- {test.file_path} ({relationship}, confidence: {test.confidence})"
            )
        
        if len(relevant_tests) > 20:
            parts.append(f"\n*...and {len(relevant_tests) - 20} more tests*")
        
        return "\n".join(parts)
    
    def _format_risk_assessment(self, risk: ChangeRisk) -> str:
        """
        Format risk assessment for prompt.
        
        Args:
            risk: Risk assessment data
            
        Returns:
            Formatted string
        """
        parts = [
            "## Risk Assessment\n",
            f"**Risk Level: {risk.risk_level.upper()}**",
            f"Risk Score: {risk.risk_score}/100\n"
        ]
        
        if risk.signals:
            parts.append(f"**Risk Signals ({len(risk.signals)}):**")
            for signal in risk.signals:
                parts.append(f"\n- **{signal.signal_type}** [{signal.severity}]")
                parts.append(f"  {signal.description}")
                if signal.evidence:
                    for evidence in signal.evidence[:3]:
                        parts.append(f"  - {evidence}")
        
        return "\n".join(parts)
    
    def build_change_prompt(
        self,
        pr_metadata: Optional[PRMetadata],
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol],
        affected_endpoints: List[AffectedEndpoint],
        affected_workflows: List[AffectedWorkflow],
        dependency_impact: DependencyImpact,
        relevant_tests: List[RelevantTest],
        risk: ChangeRisk
    ) -> str:
        """
        Build a grounded change analysis prompt.
        
        Args:
            pr_metadata: Optional PR metadata
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            affected_endpoints: List of affected endpoints
            affected_workflows: List of affected workflows
            dependency_impact: Dependency impact data
            relevant_tests: List of relevant tests
            risk: Risk assessment
            
        Returns:
            Complete prompt string
        """
        prompt_parts = []
        
        # System instructions
        prompt_parts.append("""# Change Analysis Task

You are analyzing a code change in a repository. Your task is to provide a comprehensive, grounded explanation of the change based ONLY on the supplied evidence.

## Critical Constraints

**You MUST:**
- Use ONLY the evidence provided below
- Distinguish between confirmed facts and reasonable inference
- Explicitly state when evidence is insufficient
- Acknowledge uncertainty where symbol changes are marked as uncertain

**You MUST NOT:**
- Invent files, symbols, APIs, or tests not mentioned in the evidence
- Claim runtime behavior without evidence
- Guess at implementation details
- Expose secrets, credentials, or sensitive data
- Make claims not supported by the evidence

## Output Format

Provide your analysis in the following sections:

### Summary
A concise 2-3 sentence summary of what changed.

### Technical Changes
Detailed explanation of the technical changes made. Reference specific files, symbols, and changes from the evidence.

### Reviewer Attention
Key points that a code reviewer should pay special attention to. Focus on risk signals, affected APIs, and potential breaking changes.

### Testing Considerations
What testing should be considered? Reference identified tests and gaps in test coverage where evident.

### Potential Impact
What are the potential impacts based on dependency analysis and affected workflows? Be specific about affected endpoints and callers.

### Uncertainty
What cannot be determined from the available evidence? Where is more information needed?

---

# Evidence
""")
        
        # Add PR metadata if available
        if pr_metadata:
            prompt_parts.append(self._format_pr_metadata(pr_metadata))
        
        # Add change metadata
        total_insertions = sum(f.additions for f in changed_files)
        total_deletions = sum(f.deletions for f in changed_files)
        prompt_parts.append(f"\n## Change Statistics")
        prompt_parts.append(f"Files changed: {len(changed_files)}")
        prompt_parts.append(f"Symbols changed: {len(changed_symbols)}")
        prompt_parts.append(f"Lines changed: +{total_insertions} -{total_deletions}\n")
        
        # Add detailed evidence
        prompt_parts.append(self._format_file_changes(changed_files))
        prompt_parts.append("\n")
        prompt_parts.append(self._format_symbol_changes(changed_symbols))
        prompt_parts.append("\n")
        prompt_parts.append(self._format_affected_apis(affected_endpoints))
        prompt_parts.append("\n")
        prompt_parts.append(self._format_affected_workflows(affected_workflows))
        prompt_parts.append("\n")
        prompt_parts.append(self._format_dependency_impact(dependency_impact))
        prompt_parts.append("\n")
        prompt_parts.append(self._format_relevant_tests(relevant_tests))
        prompt_parts.append("\n")
        prompt_parts.append(self._format_risk_assessment(risk))
        
        prompt_parts.append("\n\n---\n\nProvide your analysis now:")
        
        prompt = "\n".join(prompt_parts)
        
        logger.info(f"Built change analysis prompt ({len(prompt)} characters)")
        
        return prompt

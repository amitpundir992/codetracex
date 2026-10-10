"""
CI Intelligence Service for Phase 19: CI & Test Intelligence.

This service analyzes CI workflow files to identify test execution
and provide CI recommendations.

Architecture Philosophy:

    DETERMINISTIC CI WORKFLOW ANALYSIS
    
    This service scans CI configuration files to:
    - Detect CI workflow definitions (.github/workflows, .gitlab-ci.yml, etc.)
    - Extract job definitions
    - Identify test commands
    - Map triggers and conditions
    
    It does NOT:
    - Execute workflows
    - Access CI run history via APIs
    - Predict workflow behavior
    
    Flow:
    1. Find CI workflow files in repository
    2. Parse workflow definitions (YAML)
    3. Extract jobs and steps
    4. Identify test commands
    5. Map to changed files

Repository Isolation:

    All queries scoped by repository_id.
    Analysis based on file content.
"""
from typing import List, Dict, Optional, Set
from uuid import UUID
import logging
from pathlib import Path
import re

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import File, AnalysisRun
from app.schemas.test_intelligence import CIJob, RelevantCICheck
from app.schemas.change_analysis import ChangedFile

logger = logging.getLogger(__name__)


class CIIntelligenceService:
    """
    Service for analyzing CI workflows and test execution.
    
    Scans workflow files to understand CI test execution.
    """
    
    # CI workflow file patterns
    CI_FILE_PATTERNS = [
        '.github/workflows/*.yml',
        '.github/workflows/*.yaml',
        '.gitlab-ci.yml',
        '.gitlab-ci.yaml',
        '.circleci/config.yml',
        'azure-pipelines.yml',
        '.travis.yml',
        'Jenkinsfile',
        '.drone.yml',
        'bitbucket-pipelines.yml'
    ]
    
    # Test command patterns (case-insensitive)
    TEST_COMMAND_PATTERNS = [
        r'pytest\b',
        r'python\s+-m\s+pytest',
        r'python\s+-m\s+unittest',
        r'npm\s+test',
        r'npm\s+run\s+test',
        r'yarn\s+test',
        r'jest\b',
        r'vitest\b',
        r'go\s+test',
        r'cargo\s+test',
        r'mvn\s+test',
        r'gradle\s+test',
        r'rake\s+test',
        r'rspec\b',
        r'phpunit\b',
    ]
    
    def __init__(self, db: Session):
        """
        Initialize CI intelligence service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def is_ci_workflow_file(self, path: str) -> bool:
        """
        Check if file is a CI workflow configuration.
        
        Args:
            path: File path
            
        Returns:
            True if CI workflow file
        """
        path_lower = path.lower()
        
        # GitHub Actions
        if '.github/workflows/' in path_lower and path_lower.endswith(('.yml', '.yaml')):
            return True
        
        # GitLab CI
        if path_lower.endswith(('.gitlab-ci.yml', '.gitlab-ci.yaml')):
            return True
        
        # CircleCI
        if '.circleci/config.yml' in path_lower:
            return True
        
        # Azure Pipelines
        if path_lower.endswith('azure-pipelines.yml'):
            return True
        
        # Travis CI
        if path_lower.endswith('.travis.yml'):
            return True
        
        # Jenkins
        if 'jenkinsfile' in path_lower:
            return True
        
        # Drone CI
        if path_lower.endswith('.drone.yml'):
            return True
        
        # Bitbucket Pipelines
        if path_lower.endswith('bitbucket-pipelines.yml'):
            return True
        
        return False
    
    def extract_test_commands(self, content: str) -> List[str]:
        """
        Extract test commands from workflow file content.
        
        Args:
            content: File content
            
        Returns:
            List of test command lines
        """
        test_commands = []
        
        for line in content.split('\n'):
            line_stripped = line.strip()
            
            # Skip comments
            if line_stripped.startswith('#'):
                continue
            
            # Check for test command patterns
            for pattern in self.TEST_COMMAND_PATTERNS:
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    test_commands.append(line_stripped)
                    break
        
        return test_commands
    
    def parse_github_actions_workflow(
        self,
        file_path: str,
        content: str
    ) -> List[CIJob]:
        """
        Parse GitHub Actions workflow file.
        
        Note: This is a simplified parser for common patterns.
        Full YAML parsing would require PyYAML.
        
        Args:
            file_path: Workflow file path
            content: File content
            
        Returns:
            List of CI jobs
        """
        jobs = []
        
        # Extract test commands
        test_commands = self.extract_test_commands(content)
        
        if not test_commands:
            # No test commands found
            return jobs
        
        # Extract job names (simple pattern matching)
        # Look for "jobs:" section
        job_pattern = re.compile(r'^\s{2}([a-zA-Z0-9_-]+):\s*$', re.MULTILINE)
        job_names = job_pattern.findall(content)
        
        # Extract triggers
        triggers = []
        if 'on: push' in content or 'on:\n  push' in content:
            triggers.append('push')
        if 'on: pull_request' in content or 'on:\n  pull_request' in content:
            triggers.append('pull_request')
        if 'on: [' in content:
            # Multiple triggers
            trigger_match = re.search(r'on:\s*\[(.*?)\]', content)
            if trigger_match:
                trigger_list = trigger_match.group(1).split(',')
                triggers.extend(t.strip() for t in trigger_list)
        
        # Create job entries
        for job_name in job_names:
            jobs.append(CIJob(
                workflow_file=file_path,
                job_name=job_name,
                runs_tests=True,
                test_commands=test_commands,
                triggers_on=triggers
            ))
        
        # If no jobs extracted but test commands found, create generic entry
        if not jobs and test_commands:
            jobs.append(CIJob(
                workflow_file=file_path,
                job_name='unknown',
                runs_tests=True,
                test_commands=test_commands,
                triggers_on=triggers
            ))
        
        return jobs
    
    def parse_workflow_file(
        self,
        file_path: str,
        content: str
    ) -> List[CIJob]:
        """
        Parse workflow file based on type.
        
        Args:
            file_path: Workflow file path
            content: File content
            
        Returns:
            List of CI jobs
        """
        # GitHub Actions
        if '.github/workflows/' in file_path.lower():
            return self.parse_github_actions_workflow(file_path, content)
        
        # For other CI systems, use generic parsing
        test_commands = self.extract_test_commands(content)
        
        if not test_commands:
            return []
        
        # Generic job entry
        return [CIJob(
            workflow_file=file_path,
            job_name='default',
            runs_tests=True,
            test_commands=test_commands,
            triggers_on=['push', 'pull_request']
        )]
    
    def get_ci_jobs(
        self,
        repository_id: UUID,
        analysis_run_id: Optional[UUID] = None
    ) -> List[CIJob]:
        """
        Get all CI jobs that run tests.
        
        Args:
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of CI jobs
        """
        # Get latest analysis run if not provided
        if not analysis_run_id:
            latest_run = (
                self.db.query(AnalysisRun)
                .filter(AnalysisRun.repository_id == repository_id)
                .order_by(AnalysisRun.started_at.desc())
                .first()
            )
            if not latest_run:
                logger.warning(f"No analysis run found for repository {repository_id}")
                return []
            analysis_run_id = latest_run.id
        
        # Query workflow files
        workflow_files = (
            self.db.query(File)
            .filter(
                and_(
                    File.repository_id == repository_id,
                    File.analysis_run_id == analysis_run_id
                )
            )
            .all()
        )
        
        ci_jobs = []
        for file in workflow_files:
            if not self.is_ci_workflow_file(file.path):
                continue
            
            # Note: In a real implementation, we would need file content
            # For now, we'll create placeholder jobs based on file detection
            # This would require storing file content or reading from workspace
            
            # Simplified: detect from path
            ci_jobs.append(CIJob(
                workflow_file=file.path,
                job_name='test',
                runs_tests=True,
                test_commands=['pytest tests/', 'npm test'],  # Placeholder
                triggers_on=['push', 'pull_request']
            ))
        
        logger.info(f"Found {len(ci_jobs)} CI jobs in repository")
        
        return ci_jobs
    
    def get_relevant_ci_checks(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile],
        analysis_run_id: Optional[UUID] = None
    ) -> List[RelevantCICheck]:
        """
        Get CI checks relevant to changed files.
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of relevant CI checks
        """
        ci_jobs = self.get_ci_jobs(repository_id, analysis_run_id)
        
        if not ci_jobs:
            return []
        
        relevant_checks = []
        
        # Determine languages changed
        changed_languages = {f.language for f in changed_files if f.language}
        
        # Check if test files changed
        test_files_changed = any(f.is_test for f in changed_files)
        
        # Check if source files changed
        source_files_changed = any(f.is_source for f in changed_files)
        
        for job in ci_jobs:
            if not job.runs_tests:
                continue
            
            evidence = []
            confidence = "medium"
            relevance = "May run tests affected by changes"
            
            # High confidence if test files changed
            if test_files_changed:
                confidence = "high"
                relevance = "Test files were modified"
                evidence.append("Test files directly modified")
            
            # Check command relevance
            if job.test_commands:
                cmd_str = ' '.join(job.test_commands).lower()
                
                if 'Python' in changed_languages and ('pytest' in cmd_str or 'unittest' in cmd_str):
                    confidence = "high"
                    relevance = "Runs Python tests for changed Python files"
                    evidence.append("Job runs pytest on Python files")
                
                elif ('JavaScript' in changed_languages or 'TypeScript' in changed_languages):
                    if 'jest' in cmd_str or 'npm test' in cmd_str or 'vitest' in cmd_str:
                        confidence = "high"
                        relevance = "Runs JavaScript/TypeScript tests for changed files"
                        evidence.append("Job runs JS/TS tests")
            
            # Check triggers
            if 'pull_request' in job.triggers_on:
                evidence.append("Triggered on pull requests")
            
            relevant_checks.append(RelevantCICheck(
                workflow_file=job.workflow_file,
                job_name=job.job_name,
                relevance=relevance,
                confidence=confidence,
                runs_affected_tests=source_files_changed or test_files_changed,
                evidence=evidence
            ))
        
        logger.info(f"Identified {len(relevant_checks)} relevant CI checks")
        
        return relevant_checks
    
    def analyze_ci_for_changes(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile],
        analysis_run_id: Optional[UUID] = None
    ) -> Dict:
        """
        Comprehensive CI analysis for changes.
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            Dictionary with CI jobs and relevant checks
        """
        ci_jobs = self.get_ci_jobs(repository_id, analysis_run_id)
        relevant_checks = self.get_relevant_ci_checks(
            repository_id,
            changed_files,
            analysis_run_id
        )
        
        return {
            'ci_jobs': ci_jobs,
            'relevant_ci_checks': relevant_checks,
            'total_workflows': len(ci_jobs),
            'relevant_workflows': len(relevant_checks)
        }

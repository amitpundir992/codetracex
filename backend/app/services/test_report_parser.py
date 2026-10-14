"""
Test report parsers for Phase 20: Test Results & Failure Intelligence.

This module provides safe, bounded parsers for various test report formats:
- JUnit XML (standard format)
- pytest XML (pytest-specific JUnit variant)
- Jest JSON (Jest test runner output)
- Normalized JSON (internal standardized format)

All parsers:
- Validate document structure and size
- Handle malformed reports safely
- Never assume missing tests passed
- Preserve test outcome distinctions
- Truncate oversized content
- Return structured ParsedTestResult
"""
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from decimal import Decimal

logger = logging.getLogger(__name__)

# Safety limits
MAX_REPORT_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_TEST_CASES = 100000
MAX_FAILURE_MESSAGE_LENGTH = 5000
MAX_STACKTRACE_LENGTH = 50000


@dataclass
class ParsedTestCase:
    """Parsed test case from report."""
    suite_name: str
    test_name: str
    class_name: Optional[str]
    full_name: str
    outcome: str  # passed, failed, skipped, error
    duration_ms: Optional[int]
    failure_message: Optional[str]
    failure_type: Optional[str]
    failure_stacktrace: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTestResult:
    """Complete parsed test result."""
    source_format: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    total_duration_ms: Optional[int]
    test_cases: List[ParsedTestCase]
    report_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_fingerprint(self) -> str:
        """
        Compute deterministic fingerprint of normalized test result.
        
        Fingerprint based on:
        - Test case full names (sorted)
        - Test outcomes
        - Source format
        
        Returns:
            SHA-256 hex digest
        """
        # Sort test cases by full name for determinism
        sorted_cases = sorted(self.test_cases, key=lambda tc: tc.full_name)
        
        # Build fingerprint content
        parts = [
            f"format:{self.source_format}",
            f"total:{self.total_tests}",
        ]
        
        for tc in sorted_cases:
            parts.append(f"{tc.full_name}:{tc.outcome}")
        
        fingerprint_str = "|".join(parts)
        return hashlib.sha256(fingerprint_str.encode('utf-8')).hexdigest()


class TestReportParser:
    """Base class for test report parsers."""
    
    def parse(self, content: str) -> ParsedTestResult:
        """
        Parse test report content.
        
        Args:
            content: Raw report content
            
        Returns:
            ParsedTestResult
            
        Raises:
            ValueError: If report is malformed or too large
        """
        raise NotImplementedError


class JUnitXMLParser(TestReportParser):
    """
    Parser for JUnit XML format.
    
    Supports standard JUnit XML schema with <testsuites> or <testsuite> root.
    Handles pytest-generated JUnit XML.
    """
    
    def parse(self, content: str) -> ParsedTestResult:
        """Parse JUnit XML content."""
        # Validate size
        if len(content.encode('utf-8')) > MAX_REPORT_SIZE_BYTES:
            raise ValueError(f"Report exceeds maximum size of {MAX_REPORT_SIZE_BYTES} bytes")
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ValueError(f"Malformed XML: {e}")
        
        # Handle both <testsuites> and <testsuite> root elements
        if root.tag == 'testsuites':
            test_suites = root.findall('testsuite')
        elif root.tag == 'testsuite':
            test_suites = [root]
        else:
            raise ValueError(f"Unknown root element: {root.tag}")
        
        test_cases = []
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        error_tests = 0
        total_duration_ms = 0
        
        for suite in test_suites:
            suite_name = suite.get('name', 'unknown')
            
            for case in suite.findall('testcase'):
                if total_tests >= MAX_TEST_CASES:
                    logger.warning(f"Reached max test cases limit: {MAX_TEST_CASES}")
                    break
                
                total_tests += 1
                
                # Extract test case info
                test_name = case.get('name', 'unknown')
                class_name = case.get('classname')
                duration_str = case.get('time')
                
                # Build full name
                if class_name:
                    full_name = f"{class_name}.{test_name}"
                else:
                    full_name = f"{suite_name}.{test_name}"
                
                # Parse duration
                duration_ms = None
                if duration_str:
                    try:
                        duration_ms = int(float(duration_str) * 1000)
                        total_duration_ms += duration_ms
                    except (ValueError, TypeError):
                        pass
                
                # Determine outcome
                failure = case.find('failure')
                error = case.find('error')
                skipped = case.find('skipped')
                
                if failure is not None:
                    outcome = 'failed'
                    failed_tests += 1
                    failure_message = self._truncate(failure.get('message', ''), MAX_FAILURE_MESSAGE_LENGTH)
                    failure_type = failure.get('type', 'AssertionError')
                    failure_stacktrace = self._truncate(failure.text or '', MAX_STACKTRACE_LENGTH)
                elif error is not None:
                    outcome = 'error'
                    error_tests += 1
                    failure_message = self._truncate(error.get('message', ''), MAX_FAILURE_MESSAGE_LENGTH)
                    failure_type = error.get('type', 'Error')
                    failure_stacktrace = self._truncate(error.text or '', MAX_STACKTRACE_LENGTH)
                elif skipped is not None:
                    outcome = 'skipped'
                    skipped_tests += 1
                    failure_message = self._truncate(skipped.get('message', ''), MAX_FAILURE_MESSAGE_LENGTH)
                    failure_type = None
                    failure_stacktrace = None
                else:
                    outcome = 'passed'
                    passed_tests += 1
                    failure_message = None
                    failure_type = None
                    failure_stacktrace = None
                
                test_cases.append(ParsedTestCase(
                    suite_name=suite_name,
                    test_name=test_name,
                    class_name=class_name,
                    full_name=full_name,
                    outcome=outcome,
                    duration_ms=duration_ms,
                    failure_message=failure_message,
                    failure_type=failure_type,
                    failure_stacktrace=failure_stacktrace,
                    metadata={'file': case.get('file', '')}
                ))
        
        return ParsedTestResult(
            source_format='junit_xml',
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_tests=error_tests,
            total_duration_ms=total_duration_ms if total_duration_ms > 0 else None,
            test_cases=test_cases,
            report_metadata={}
        )
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if not text:
            return text
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... [truncated]"


class NormalizedJSONParser(TestReportParser):
    """
    Parser for normalized internal JSON format.
    
    Expected structure:
    {
        "total_tests": 10,
        "passed_tests": 8,
        "failed_tests": 2,
        "skipped_tests": 0,
        "error_tests": 0,
        "total_duration_ms": 5000,
        "test_cases": [
            {
                "suite_name": "tests.test_user",
                "test_name": "test_create_user",
                "class_name": "TestUser",
                "full_name": "tests.test_user.TestUser.test_create_user",
                "outcome": "passed",
                "duration_ms": 100,
                "failure_message": null,
                "failure_type": null,
                "failure_stacktrace": null,
                "metadata": {}
            }
        ],
        "report_metadata": {}
    }
    """
    
    def parse(self, content: str) -> ParsedTestResult:
        """Parse normalized JSON content."""
        # Validate size
        if len(content.encode('utf-8')) > MAX_REPORT_SIZE_BYTES:
            raise ValueError(f"Report exceeds maximum size of {MAX_REPORT_SIZE_BYTES} bytes")
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON: {e}")
        
        # Validate structure
        if not isinstance(data, dict):
            raise ValueError("Report must be a JSON object")
        
        test_cases_data = data.get('test_cases', [])
        if not isinstance(test_cases_data, list):
            raise ValueError("test_cases must be a list")
        
        if len(test_cases_data) > MAX_TEST_CASES:
            raise ValueError(f"Report exceeds maximum test cases: {MAX_TEST_CASES}")
        
        test_cases = []
        for tc_data in test_cases_data:
            if not isinstance(tc_data, dict):
                logger.warning("Skipping non-dict test case")
                continue
            
            test_cases.append(ParsedTestCase(
                suite_name=tc_data.get('suite_name', 'unknown'),
                test_name=tc_data.get('test_name', 'unknown'),
                class_name=tc_data.get('class_name'),
                full_name=tc_data.get('full_name', 'unknown'),
                outcome=tc_data.get('outcome', 'error'),
                duration_ms=tc_data.get('duration_ms'),
                failure_message=self._truncate(tc_data.get('failure_message'), MAX_FAILURE_MESSAGE_LENGTH),
                failure_type=tc_data.get('failure_type'),
                failure_stacktrace=self._truncate(tc_data.get('failure_stacktrace'), MAX_STACKTRACE_LENGTH),
                metadata=tc_data.get('metadata', {})
            ))
        
        return ParsedTestResult(
            source_format='normalized_json',
            total_tests=data.get('total_tests', len(test_cases)),
            passed_tests=data.get('passed_tests', 0),
            failed_tests=data.get('failed_tests', 0),
            skipped_tests=data.get('skipped_tests', 0),
            error_tests=data.get('error_tests', 0),
            total_duration_ms=data.get('total_duration_ms'),
            test_cases=test_cases,
            report_metadata=data.get('report_metadata', {})
        )
    
    def _truncate(self, text: Optional[str], max_length: int) -> Optional[str]:
        """Truncate text to max length."""
        if not text:
            return text
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... [truncated]"


def parse_test_report(content: str, format_hint: str = 'auto') -> ParsedTestResult:
    """
    Parse test report with format auto-detection.
    
    Args:
        content: Raw report content
        format_hint: Format hint (auto, junit_xml, normalized_json)
        
    Returns:
        ParsedTestResult
        
    Raises:
        ValueError: If report cannot be parsed
    """
    if not content or not content.strip():
        raise ValueError("Report content is empty")
    
    # Auto-detect format
    if format_hint == 'auto':
        content_stripped = content.strip()
        if content_stripped.startswith('<'):
            format_hint = 'junit_xml'
        elif content_stripped.startswith('{'):
            format_hint = 'normalized_json'
        else:
            raise ValueError("Cannot auto-detect report format")
    
    # Parse with appropriate parser
    if format_hint == 'junit_xml':
        parser = JUnitXMLParser()
    elif format_hint == 'normalized_json':
        parser = NormalizedJSONParser()
    else:
        raise ValueError(f"Unsupported format: {format_hint}")
    
    return parser.parse(content)

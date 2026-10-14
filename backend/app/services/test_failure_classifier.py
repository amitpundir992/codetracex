"""
Failure classification service for Phase 20: Test Results & Failure Intelligence.

This service provides deterministic classification of test failures based on
explicit evidence from failure messages, stack traces, and error types.

Classification is rule-based and transparent. When evidence is insufficient,
the classification is marked as 'unknown' with appropriate confidence.
"""
import logging
import re
from typing import Optional, Tuple, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class FailureClassifier:
    """
    Deterministic test failure classifier.
    
    Classifies failures into categories based on explicit patterns:
    - assertion: Assertion failures
    - import_error: Import or module loading errors
    - setup_error: Test setup or teardown errors
    - timeout: Test timeouts
    - dependency_error: Dependency or environment errors
    - network_error: Network or external service errors
    - unknown: Insufficient evidence for classification
    """
    
    # Assertion patterns
    ASSERTION_PATTERNS = [
        r'AssertionError',
        r'assert\s+',
        r'assertEqual',
        r'assertNotEqual',
        r'assertTrue',
        r'assertFalse',
        r'expect\(.*\)\.to',
        r'Expected.*but got',
        r'expected.*actual',
    ]
    
    # Import error patterns
    IMPORT_ERROR_PATTERNS = [
        r'ImportError',
        r'ModuleNotFoundError',
        r'Cannot find module',
        r'No module named',
        r'Failed to load module',
        r'import .* failed',
    ]
    
    # Setup/teardown error patterns
    SETUP_ERROR_PATTERNS = [
        r'setUp.*failed',
        r'tearDown.*failed',
        r'beforeEach.*failed',
        r'afterEach.*failed',
        r'beforeAll.*failed',
        r'afterAll.*failed',
        r'fixture.*failed',
        r'@pytest\.fixture',
    ]
    
    # Timeout patterns
    TIMEOUT_PATTERNS = [
        r'TimeoutError',
        r'timeout',
        r'timed out',
        r'exceeded.*time',
        r'took too long',
    ]
    
    # Dependency error patterns
    DEPENDENCY_ERROR_PATTERNS = [
        r'DatabaseError',
        r'Connection.*refused',
        r'ECONNREFUSED',
        r'Cannot connect to',
        r'Service unavailable',
        r'Redis.*error',
        r'PostgreSQL.*error',
    ]
    
    # Network error patterns
    NETWORK_ERROR_PATTERNS = [
        r'NetworkError',
        r'ConnectionError',
        r'RequestException',
        r'HTTP.*error',
        r'404.*Not Found',
        r'500.*Internal Server Error',
        r'ENOTFOUND',
        r'getaddrinfo.*failed',
    ]
    
    def classify_failure(
        self,
        failure_message: Optional[str],
        failure_type: Optional[str],
        failure_stacktrace: Optional[str]
    ) -> Tuple[str, Decimal, List[str]]:
        """
        Classify test failure based on available evidence.
        
        Args:
            failure_message: Short failure message
            failure_type: Exception type or error type
            failure_stacktrace: Full stack trace
            
        Returns:
            Tuple of (classification, confidence, evidence_list)
            - classification: One of the FailureClassification enum values
            - confidence: Decimal 0.00 to 1.00
            - evidence_list: List of evidence strings explaining classification
        """
        if not failure_message and not failure_type and not failure_stacktrace:
            return ('unknown', Decimal('0.00'), ['No failure information available'])
        
        # Combine all available text for pattern matching
        combined_text = ' '.join(filter(None, [
            failure_type or '',
            failure_message or '',
            failure_stacktrace or ''
        ]))
        
        evidence = []
        
        # Check patterns in priority order
        
        # 1. Assertion failures (most common)
        if self._matches_patterns(combined_text, self.ASSERTION_PATTERNS):
            evidence.append('Failure message/type matches assertion pattern')
            if failure_type and 'assert' in failure_type.lower():
                evidence.append(f'Error type indicates assertion: {failure_type}')
                return ('assertion', Decimal('0.95'), evidence)
            return ('assertion', Decimal('0.85'), evidence)
        
        # 2. Import errors
        if self._matches_patterns(combined_text, self.IMPORT_ERROR_PATTERNS):
            evidence.append('Failure message/type matches import error pattern')
            if failure_type and 'import' in failure_type.lower():
                evidence.append(f'Error type indicates import: {failure_type}')
                return ('import_error', Decimal('0.95'), evidence)
            return ('import_error', Decimal('0.85'), evidence)
        
        # 3. Setup/teardown errors
        if self._matches_patterns(combined_text, self.SETUP_ERROR_PATTERNS):
            evidence.append('Failure message/stacktrace matches setup/teardown pattern')
            return ('setup_error', Decimal('0.80'), evidence)
        
        # 4. Timeout errors
        if self._matches_patterns(combined_text, self.TIMEOUT_PATTERNS):
            evidence.append('Failure message/type matches timeout pattern')
            if failure_type and 'timeout' in failure_type.lower():
                evidence.append(f'Error type indicates timeout: {failure_type}')
                return ('timeout', Decimal('0.95'), evidence)
            return ('timeout', Decimal('0.85'), evidence)
        
        # 5. Dependency errors (database, redis, etc.)
        if self._matches_patterns(combined_text, self.DEPENDENCY_ERROR_PATTERNS):
            evidence.append('Failure message/type matches dependency error pattern')
            return ('dependency_error', Decimal('0.75'), evidence)
        
        # 6. Network errors
        if self._matches_patterns(combined_text, self.NETWORK_ERROR_PATTERNS):
            evidence.append('Failure message/type matches network error pattern')
            return ('network_error', Decimal('0.75'), evidence)
        
        # No patterns matched
        evidence.append('No classification pattern matched')
        if failure_type:
            evidence.append(f'Error type: {failure_type}')
        
        return ('unknown', Decimal('0.50'), evidence)
    
    def _matches_patterns(self, text: str, patterns: List[str]) -> bool:
        """
        Check if text matches any of the given regex patterns.
        
        Args:
            text: Text to search
            patterns: List of regex patterns
            
        Returns:
            True if any pattern matches
        """
        if not text:
            return False
        
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            except re.error as e:
                logger.warning(f"Invalid regex pattern {pattern}: {e}")
                continue
        
        return False
    
    def classify_multiple_failures(
        self,
        test_cases: List[dict]
    ) -> List[Tuple[str, Decimal, List[str]]]:
        """
        Classify multiple test failures in batch.
        
        Args:
            test_cases: List of test case dicts with failure info
            
        Returns:
            List of (classification, confidence, evidence) tuples
        """
        results = []
        
        for test_case in test_cases:
            classification, confidence, evidence = self.classify_failure(
                failure_message=test_case.get('failure_message'),
                failure_type=test_case.get('failure_type'),
                failure_stacktrace=test_case.get('failure_stacktrace')
            )
            results.append((classification, confidence, evidence))
        
        return results

"""
Sanity tests for Phase 20: Test Results & Failure Intelligence

Verifies basic functionality without requiring database.
"""
import pytest
from app.services.test_report_parser import (
    parse_test_report,
    JUnitXMLParser,
    NormalizedJSONParser
)
from app.services.test_failure_classifier import FailureClassifier
from decimal import Decimal


def test_parse_junit_xml():
    """Test JUnit XML parsing."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
    <testsuite name="tests.test_user" tests="2" failures="1" errors="0" skipped="0">
        <testcase name="test_create_user" classname="tests.test_user.TestUser" time="0.123">
        </testcase>
        <testcase name="test_delete_user" classname="tests.test_user.TestUser" time="0.456">
            <failure message="AssertionError: Expected 200, got 404" type="AssertionError">
Traceback (most recent call last):
  File "tests/test_user.py", line 42, in test_delete_user
    assert response.status_code == 200
AssertionError: Expected 200, got 404
            </failure>
        </testcase>
    </testsuite>
</testsuites>"""
    
    result = parse_test_report(xml_content, 'junit_xml')
    
    assert result.source_format == 'junit_xml'
    assert result.total_tests == 2
    assert result.passed_tests == 1
    assert result.failed_tests == 1
    assert result.skipped_tests == 0
    assert result.error_tests == 0
    assert len(result.test_cases) == 2
    
    # Check passed test
    passed_test = result.test_cases[0]
    assert passed_test.test_name == 'test_create_user'
    assert passed_test.outcome == 'passed'
    assert passed_test.duration_ms == 123
    
    # Check failed test
    failed_test = result.test_cases[1]
    assert failed_test.test_name == 'test_delete_user'
    assert failed_test.outcome == 'failed'
    assert failed_test.duration_ms == 456
    assert failed_test.failure_message is not None
    assert 'AssertionError' in failed_test.failure_message
    assert failed_test.failure_type == 'AssertionError'
    assert failed_test.failure_stacktrace is not None


def test_parse_normalized_json():
    """Test normalized JSON parsing."""
    json_content = """{
    "total_tests": 1,
    "passed_tests": 0,
    "failed_tests": 1,
    "skipped_tests": 0,
    "error_tests": 0,
    "total_duration_ms": 500,
    "test_cases": [
        {
            "suite_name": "tests.test_api",
            "test_name": "test_endpoint",
            "class_name": "TestAPI",
            "full_name": "tests.test_api.TestAPI.test_endpoint",
            "outcome": "failed",
            "duration_ms": 500,
            "failure_message": "Connection refused",
            "failure_type": "ConnectionError",
            "failure_stacktrace": "Traceback...",
            "metadata": {"file": "tests/test_api.py"}
        }
    ]
}"""
    
    result = parse_test_report(json_content, 'normalized_json')
    
    assert result.source_format == 'normalized_json'
    assert result.total_tests == 1
    assert result.passed_tests == 0
    assert result.failed_tests == 1
    assert len(result.test_cases) == 1
    
    test_case = result.test_cases[0]
    assert test_case.full_name == "tests.test_api.TestAPI.test_endpoint"
    assert test_case.outcome == "failed"
    assert test_case.failure_message == "Connection refused"


def test_parse_auto_detect_xml():
    """Test auto-detection of XML format."""
    xml_content = """<testsuites><testsuite name="test" tests="1"></testsuite></testsuites>"""
    result = parse_test_report(xml_content, 'auto')
    assert result.source_format == 'junit_xml'


def test_parse_auto_detect_json():
    """Test auto-detection of JSON format."""
    json_content = """{"total_tests": 0, "test_cases": []}"""
    result = parse_test_report(json_content, 'auto')
    assert result.source_format == 'normalized_json'


def test_parse_malformed_xml():
    """Test handling of malformed XML."""
    malformed_xml = """<testsuites><testsuite name="test" tests="1">"""
    
    with pytest.raises(ValueError, match="Malformed XML"):
        parse_test_report(malformed_xml, 'junit_xml')


def test_parse_empty_content():
    """Test handling of empty content."""
    with pytest.raises(ValueError, match="empty"):
        parse_test_report("", 'auto')


def test_fingerprint_determinism():
    """Test that fingerprints are deterministic."""
    xml_content = """<?xml version="1.0"?>
<testsuites>
    <testsuite name="test" tests="1">
        <testcase name="test_one" classname="TestClass" time="0.1"></testcase>
    </testsuite>
</testsuites>"""
    
    result1 = parse_test_report(xml_content, 'junit_xml')
    result2 = parse_test_report(xml_content, 'junit_xml')
    
    fingerprint1 = result1.compute_fingerprint()
    fingerprint2 = result2.compute_fingerprint()
    
    assert fingerprint1 == fingerprint2
    assert len(fingerprint1) == 64  # SHA-256 hex


def test_failure_classifier_assertion():
    """Test classification of assertion failures."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message="Expected 5, got 3",
        failure_type="AssertionError",
        failure_stacktrace="assert x == 5"
    )
    
    assert classification == 'assertion'
    assert confidence >= Decimal('0.85')
    assert len(evidence) > 0


def test_failure_classifier_import_error():
    """Test classification of import errors."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message="No module named 'requests'",
        failure_type="ModuleNotFoundError",
        failure_stacktrace="import requests"
    )
    
    assert classification == 'import_error'
    assert confidence >= Decimal('0.85')


def test_failure_classifier_timeout():
    """Test classification of timeout errors."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message="Test timed out after 30 seconds",
        failure_type="TimeoutError",
        failure_stacktrace="TimeoutError: exceeded time limit"
    )
    
    assert classification == 'timeout'
    assert confidence >= Decimal('0.85')


def test_failure_classifier_network():
    """Test classification of network errors."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message="HTTP 404 Not Found",
        failure_type="RequestException",
        failure_stacktrace="requests.exceptions.RequestException: HTTP error"
    )
    
    assert classification == 'network_error'
    assert confidence >= Decimal('0.75')


def test_failure_classifier_dependency():
    """Test classification of dependency errors."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message="Connection refused",
        failure_type="ConnectionError",
        failure_stacktrace="Cannot connect to database"
    )
    
    assert classification == 'dependency_error'
    assert confidence >= Decimal('0.75')


def test_failure_classifier_unknown():
    """Test classification of unknown errors."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message="Something went wrong",
        failure_type="CustomError",
        failure_stacktrace=""
    )
    
    assert classification == 'unknown'
    assert confidence == Decimal('0.50')


def test_failure_classifier_no_evidence():
    """Test classification with no evidence."""
    classifier = FailureClassifier()
    
    classification, confidence, evidence = classifier.classify_failure(
        failure_message=None,
        failure_type=None,
        failure_stacktrace=None
    )
    
    assert classification == 'unknown'
    assert confidence == Decimal('0.00')
    assert 'No failure information' in evidence[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

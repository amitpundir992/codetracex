"""
API endpoints for Phase 22: Test-to-Code Traceability & Coverage Intelligence.

This module provides REST API endpoints for comprehensive test-to-code
traceability, including bidirectional mappings and relationship evidence.
"""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Repository, AnalysisRun
from app.schemas.test_intelligence import AffectedTest
from app.services.test_traceability_service import TestTraceabilityService

logger = logging.getLogger(__name__)

router = APIRouter()


# Response schemas for Phase 22
from pydantic import BaseModel, Field


class SourceTraceabilityResponse(BaseModel):
    """Response for source file traceability."""
    repository_id: UUID
    source_file: str
    analysis_run_id: Optional[UUID]
    total_related_tests: int = Field(..., ge=0)
    related_tests: List[AffectedTest]
    
    class Config:
        json_schema_extra = {
            "example": {
                "repository_id": "550e8400-e29b-41d4-a716-446655440001",
                "source_file": "services/user_service.py",
                "analysis_run_id": "550e8400-e29b-41d4-a716-446655440002",
                "total_related_tests": 3,
                "related_tests": []
            }
        }


class SymbolTraceabilityResponse(BaseModel):
    """Response for symbol traceability."""
    repository_id: UUID
    symbol_name: str
    file_path: Optional[str]
    analysis_run_id: Optional[UUID]
    total_related_tests: int = Field(..., ge=0)
    related_tests: List[AffectedTest]
    
    class Config:
        json_schema_extra = {
            "example": {
                "repository_id": "550e8400-e29b-41d4-a716-446655440001",
                "symbol_name": "create_user",
                "file_path": "services/user_service.py",
                "analysis_run_id": "550e8400-e29b-41d4-a716-446655440002",
                "total_related_tests": 2,
                "related_tests": []
            }
        }


class RelatedSourceFile(BaseModel):
    """Related source file for a test."""
    source_file: str
    relationship_type: str
    confidence: str
    evidence: List[str]
    imported_symbols: List[str]


class TestTraceabilityResponse(BaseModel):
    """Response for test file traceability."""
    repository_id: UUID
    test_file: str
    analysis_run_id: Optional[UUID]
    total_related_sources: int = Field(..., ge=0)
    related_sources: List[RelatedSourceFile]
    
    class Config:
        json_schema_extra = {
            "example": {
                "repository_id": "550e8400-e29b-41d4-a716-446655440001",
                "test_file": "tests/test_user_service.py",
                "analysis_run_id": "550e8400-e29b-41d4-a716-446655440002",
                "total_related_sources": 2,
                "related_sources": []
            }
        }


@router.get(
    "/repositories/{repository_id}/traceability/source-to-tests",
    response_model=SourceTraceabilityResponse,
    summary="Get tests related to a source file",
    description="""
Find all tests that relate to a specific source file.

This endpoint provides bidirectional traceability from source code to tests.

**Relationship Types:**
- `direct_import`: Test directly imports symbols from this file (high confidence)
- `indirect_import`: Test imports module containing this file (medium confidence)
- `module_sibling`: Test follows naming convention for this file (medium confidence)
- `path_pattern`: Test name suggests relationship (low confidence)

**Evidence:**
- Each relationship includes specific evidence explaining the connection
- Confidence levels: high, medium, low
- Imported symbols listed when available

**Requirements:**
- Repository must exist and be analyzed
- Source file must exist in repository

**Note:** This is static analysis based on imports and naming conventions,
not runtime code coverage.
"""
)
async def get_tests_for_source_file(
    repository_id: UUID,
    source_file: str = Query(..., description="Source file path"),
    analysis_run_id: Optional[UUID] = Query(None, description="Optional analysis run UUID"),
    db: Session = Depends(get_db)
) -> SourceTraceabilityResponse:
    """
    Get all tests related to a source file.
    
    Args:
        repository_id: Repository UUID
        source_file: Source file path
        analysis_run_id: Optional analysis run UUID
        db: Database session
        
    Returns:
        Source traceability response with related tests
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Validate analysis run if provided
    if analysis_run_id:
        analysis_run = db.query(AnalysisRun).filter(
            AnalysisRun.id == analysis_run_id,
            AnalysisRun.repository_id == repository_id
        ).first()
        
        if not analysis_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis run {analysis_run_id} not found in repository {repository_id}"
            )
    
    try:
        # Get traceability service
        traceability_service = TestTraceabilityService(db)
        
        # Find related tests
        related_tests = traceability_service.get_tests_for_source_file(
            repository_id=repository_id,
            source_file_path=source_file,
            analysis_run_id=analysis_run_id
        )
        
        logger.info(
            f"Found {len(related_tests)} tests for source file {source_file} "
            f"in repository {repository_id}"
        )
        
        return SourceTraceabilityResponse(
            repository_id=repository_id,
            source_file=source_file,
            analysis_run_id=analysis_run_id,
            total_related_tests=len(related_tests),
            related_tests=related_tests
        )
    
    except Exception as e:
        logger.error(f"Failed to get tests for source file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tests for source file: {str(e)}"
        )


@router.get(
    "/repositories/{repository_id}/traceability/symbol-to-tests",
    response_model=SymbolTraceabilityResponse,
    summary="Get tests related to a symbol",
    description="""
Find all tests that relate to a specific symbol (function, class, method).

This endpoint provides symbol-level traceability.

**Relationship Types:**
- `direct_import`: Test directly imports this symbol (high confidence)
- `path_pattern`: Test name mentions this symbol (low confidence)

**Evidence:**
- Each relationship includes specific evidence explaining the connection
- Confidence levels: high, medium, low

**Requirements:**
- Repository must exist and be analyzed
- Symbol should exist in repository

**Note:** This is static analysis based on imports and naming conventions.
Symbol name matching is case-insensitive for pattern matching.
"""
)
async def get_tests_for_symbol(
    repository_id: UUID,
    symbol_name: str = Query(..., description="Symbol name (function, class, method)"),
    file_path: Optional[str] = Query(None, description="Optional file path to disambiguate symbol"),
    analysis_run_id: Optional[UUID] = Query(None, description="Optional analysis run UUID"),
    db: Session = Depends(get_db)
) -> SymbolTraceabilityResponse:
    """
    Get all tests related to a symbol.
    
    Args:
        repository_id: Repository UUID
        symbol_name: Symbol name
        file_path: Optional file path to disambiguate
        analysis_run_id: Optional analysis run UUID
        db: Database session
        
    Returns:
        Symbol traceability response with related tests
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Validate analysis run if provided
    if analysis_run_id:
        analysis_run = db.query(AnalysisRun).filter(
            AnalysisRun.id == analysis_run_id,
            AnalysisRun.repository_id == repository_id
        ).first()
        
        if not analysis_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis run {analysis_run_id} not found in repository {repository_id}"
            )
    
    try:
        # Get traceability service
        traceability_service = TestTraceabilityService(db)
        
        # Find related tests
        related_tests = traceability_service.get_tests_for_symbol(
            repository_id=repository_id,
            symbol_name=symbol_name,
            file_path=file_path,
            analysis_run_id=analysis_run_id
        )
        
        logger.info(
            f"Found {len(related_tests)} tests for symbol '{symbol_name}' "
            f"in repository {repository_id}"
        )
        
        return SymbolTraceabilityResponse(
            repository_id=repository_id,
            symbol_name=symbol_name,
            file_path=file_path,
            analysis_run_id=analysis_run_id,
            total_related_tests=len(related_tests),
            related_tests=related_tests
        )
    
    except Exception as e:
        logger.error(f"Failed to get tests for symbol: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tests for symbol: {str(e)}"
        )


@router.get(
    "/repositories/{repository_id}/traceability/test-to-sources",
    response_model=TestTraceabilityResponse,
    summary="Get source files related to a test",
    description="""
Find all source files that a test file relates to.

This endpoint provides reverse traceability from tests to source code.

**Relationship Types:**
- `direct_import`: Test imports from this source file (high confidence)
- `module_sibling`: Test follows naming convention (medium confidence)

**Evidence:**
- Each relationship includes specific evidence explaining the connection
- Imported symbols listed when available

**Requirements:**
- Repository must exist and be analyzed
- Test file must exist in repository

**Note:** This is static analysis based on imports and naming conventions.
Helps understand what code a test exercises.
"""
)
async def get_source_files_for_test(
    repository_id: UUID,
    test_file: str = Query(..., description="Test file path"),
    analysis_run_id: Optional[UUID] = Query(None, description="Optional analysis run UUID"),
    db: Session = Depends(get_db)
) -> TestTraceabilityResponse:
    """
    Get all source files related to a test.
    
    Args:
        repository_id: Repository UUID
        test_file: Test file path
        analysis_run_id: Optional analysis run UUID
        db: Database session
        
    Returns:
        Test traceability response with related sources
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Validate analysis run if provided
    if analysis_run_id:
        analysis_run = db.query(AnalysisRun).filter(
            AnalysisRun.id == analysis_run_id,
            AnalysisRun.repository_id == repository_id
        ).first()
        
        if not analysis_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis run {analysis_run_id} not found in repository {repository_id}"
            )
    
    try:
        # Get traceability service
        traceability_service = TestTraceabilityService(db)
        
        # Find related sources
        related_sources_data = traceability_service.get_source_files_for_test(
            repository_id=repository_id,
            test_file_path=test_file,
            analysis_run_id=analysis_run_id
        )
        
        # Convert to Pydantic models
        related_sources = [
            RelatedSourceFile(
                source_file=src["source_file"],
                relationship_type=src["relationship_type"],
                confidence=src["confidence"],
                evidence=src["evidence"],
                imported_symbols=src["imported_symbols"]
            )
            for src in related_sources_data
        ]
        
        logger.info(
            f"Found {len(related_sources)} source files for test {test_file} "
            f"in repository {repository_id}"
        )
        
        return TestTraceabilityResponse(
            repository_id=repository_id,
            test_file=test_file,
            analysis_run_id=analysis_run_id,
            total_related_sources=len(related_sources),
            related_sources=related_sources
        )
    
    except Exception as e:
        logger.error(f"Failed to get source files for test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get source files for test: {str(e)}"
        )

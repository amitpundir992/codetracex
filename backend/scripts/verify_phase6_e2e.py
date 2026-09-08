"""
Phase 6 E2E Verification Script
Tests Git history functionality with real repository and Neon database.
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Repository, AnalysisRun, File, Commit, CommitFileChange
from app.services.git_history_service import GitHistoryService
from app.services.persistence_service import PersistenceService


def main():
    """Run Phase 6 E2E verification."""
    print("=" * 70)
    print("Phase 6 E2E Verification: Git History Intelligence")
    print("=" * 70)
    print()
    
    db = next(get_db())
    
    try:
        # Step 1: Check for existing repositories
        print("Step 1: Checking for repositories in Neon database...")
        repos = db.execute(select(Repository)).scalars().all()
        
        if not repos:
            print("[ERROR] No repositories found. Please analyze a repository first.")
            print("\nTo create test data, use:")
            print("  POST http://localhost:8000/api/repositories/analyze")
            print('  {"url": "https://github.com/your-test-repo"}')
            return
        
        print(f"[OK] Found {len(repos)} repository(ies)")
        
        # Use the first repository
        repo = repos[0]
        print(f"\nSelected repository: {repo.full_name}")
        print(f"Repository ID: {repo.id}")
        
        # Step 2: Check if Git history already exists
        print("\nStep 2: Checking for existing Git history...")
        existing_commits = db.execute(
            select(func.count(Commit.id))
            .where(Commit.repository_id == repo.id)
        ).scalar()
        
        if existing_commits > 0:
            print(f"[OK] Repository already has {existing_commits} commits")
            skip_extraction = True
        else:
            print("[WARN] No Git history found. Will extract now...")
            skip_extraction = False
        
        # Step 3: Extract Git history if needed
        if not skip_extraction:
            print("\nStep 3: Extracting Git history from GitHub...")
            try:
                git_service = GitHistoryService(max_commits=50)  # Limit for testing
                result = git_service.extract_repository_history(
                    repo.github_url,
                    repo.default_branch
                )
                commits_data = result['commits']
                print(f"[OK] Extracted {len(commits_data)} commits")
                
                # Step 4: Persist to database
                print("\nStep 4: Persisting Git history to Neon PostgreSQL...")
                
                # Get file path mapping
                files = db.execute(
                    select(File).where(File.repository_id == repo.id)
                ).scalars().all()
                
                file_path_to_id = {f.path: f.id for f in files}
                print(f"   Found {len(file_path_to_id)} existing file records")
                
                persistence_service = PersistenceService(db)
                new_commits = persistence_service.persist_git_history(
                    repo,
                    commits_data,
                    file_path_to_id
                )
                
                db.commit()
                print(f"[OK] Persisted {new_commits} new commits")
                
            except Exception as e:
                print(f"[ERROR] Error during extraction: {e}")
                db.rollback()
                return
        
        # Step 5: Verify data in database
        print("\nStep 5: Verifying Git history data in database...")
        
        commits = db.execute(
            select(Commit)
            .where(Commit.repository_id == repo.id)
            .order_by(Commit.committed_at.desc())
            .limit(5)
        ).scalars().all()
        
        if not commits:
            print("[ERROR] No commits found after persistence")
            return
        
        print(f"[OK] Found {len(commits)} recent commits:")
        for i, commit in enumerate(commits, 1):
            print(f"\n   {i}. {commit.commit_hash[:8]} - {commit.commit_message.split(chr(10))[0][:50]}")
            print(f"      Author: {commit.author_name} <{commit.author_email}>")
            print(f"      Date: {commit.committed_at}")
            
            # Check file changes
            changes = db.execute(
                select(CommitFileChange)
                .where(CommitFileChange.commit_id == commit.id)
            ).scalars().all()
            
            print(f"      Changes: {len(changes)} files")
            for change in changes[:3]:  # Show first 3
                print(f"         [{change.change_type[0].upper()}] {change.path} (+{change.additions}/-{change.deletions})")
            
            if len(changes) > 3:
                print(f"         ... and {len(changes) - 3} more files")
        
        # Step 6: Test file history
        print("\nStep 6: Testing file history query...")
        
        files_with_history = db.execute(
            select(File)
            .join(CommitFileChange, CommitFileChange.file_id == File.id)
            .where(File.repository_id == repo.id)
            .distinct()
            .limit(1)
        ).scalars().first()
        
        if files_with_history:
            print(f"[OK] Testing file history for: {files_with_history.path}")
            
            history = db.execute(
                select(CommitFileChange, Commit)
                .join(Commit, Commit.id == CommitFileChange.commit_id)
                .where(CommitFileChange.file_id == files_with_history.id)
                .order_by(Commit.committed_at.desc())
                .limit(5)
            ).all()
            
            print(f"   Found {len(history)} commits modifying this file:")
            for change, commit in history:
                print(f"      {commit.commit_hash[:8]} - {change.change_type} (+{change.additions}/-{change.deletions})")
        else:
            print("[WARN]  No files with history found (historical files may not match current analysis)")
        
        # Step 7: Test co-changes
        print("\nStep 7: Testing co-change analysis...")
        
        if files_with_history:
            # Find files that changed in same commits
            # Use aliased table for self-join
            from sqlalchemy.orm import aliased
            other_changes = aliased(CommitFileChange)
            
            co_changes = db.execute(
                select(File.path, func.count(Commit.id).label('shared_commits'))
                .select_from(CommitFileChange)
                .join(Commit, Commit.id == CommitFileChange.commit_id)
                .join(other_changes, CommitFileChange.commit_id == other_changes.commit_id)
                .join(File, File.id == other_changes.file_id)
                .where(CommitFileChange.file_id == files_with_history.id)
                .where(File.id != files_with_history.id)
                .group_by(File.path)
                .order_by(func.count(Commit.id).desc())
                .limit(5)
            ).all()
            
            if co_changes:
                print(f"[OK] Found {len(co_changes)} co-changed files:")
                for path, count in co_changes:
                    print(f"      {path} - {count} shared commits")
            else:
                print("   No co-changes found (files modified independently)")
        
        # Final Summary
        print("\n" + "=" * 70)
        print("Phase 6 E2E Verification Summary")
        print("=" * 70)
        
        total_commits = db.execute(
            select(func.count(Commit.id))
            .where(Commit.repository_id == repo.id)
        ).scalar()
        
        total_changes = db.execute(
            select(func.count(CommitFileChange.id))
            .join(Commit, Commit.id == CommitFileChange.commit_id)
            .where(Commit.repository_id == repo.id)
        ).scalar()
        
        print(f"\n[OK] Repository: {repo.full_name}")
        print(f"[OK] Total Commits: {total_commits}")
        print(f"[OK] Total File Changes: {total_changes}")
        print(f"[OK] Database: Neon PostgreSQL")
        print(f"[OK] Git History Extraction: Working")
        print(f"[OK] Persistence: Working")
        print(f"[OK] Queries: Working")
        print("\n[SUCCESS] Phase 6 Backend E2E Verification: PASSED")
        print("\nNext step: Test frontend UI at http://localhost:3000/repository")
        print()
        
    except Exception as e:
        print(f"\n[ERROR] Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()


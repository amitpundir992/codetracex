"""
Tests for Git history extraction and persistence (Phase 6).

These tests use a real temporary Git repository with deterministic history
to verify Git history extraction, persistence, and API functionality.

Test Repository Structure:
    Commit 1: Add file_a.py
    Commit 2: Modify file_a.py, add file_b.js
    Commit 3: Modify file_a.py, modify file_b.js
    Commit 4: Rename file_b.js to file_c.js
    Commit 5: Delete file_a.py
"""
import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.git_history_service import GitHistoryService, GitCommandError
from app.services.persistence_service import PersistenceService
from app.db.models import Repository, Commit, CommitFileChange, ChangeType


class TestGitRepository:
    """
    Helper class to create a deterministic test Git repository.
    """
    
    def __init__(self):
        self.temp_dir = None
        self.repo_path = None
    
    def create(self) -> Path:
        """
        Create a temporary Git repository with deterministic history.
        
        Returns:
            Path to repository root
        """
        self.temp_dir = tempfile.mkdtemp(prefix='test_git_')
        self.repo_path = Path(self.temp_dir)
        
        # Initialize Git repository
        subprocess.run(['git', 'init'], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        # Commit 1: Add file_a.py
        file_a = self.repo_path / 'file_a.py'
        file_a.write_text('def function_a():\n    pass\n')
        subprocess.run(['git', 'add', 'file_a.py'], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Add file_a.py'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        # Commit 2: Modify file_a.py, add file_b.js
        file_a.write_text('def function_a():\n    return "modified"\n\ndef function_b():\n    pass\n')
        file_b = self.repo_path / 'file_b.js'
        file_b.write_text('function funcB() {\n  console.log("b");\n}\n')
        subprocess.run(['git', 'add', '.'], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Modify file_a, add file_b'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        # Commit 3: Modify both files
        file_a.write_text('def function_a():\n    return "modified again"\n\ndef function_b():\n    pass\n')
        file_b.write_text('function funcB() {\n  console.log("modified");\n}\n')
        subprocess.run(['git', 'add', '.'], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Modify both files'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        # Commit 4: Rename file_b.js to file_c.js
        subprocess.run(['git', 'mv', 'file_b.js', 'file_c.js'], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Rename file_b to file_c'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        # Commit 5: Delete file_a.py
        subprocess.run(['git', 'rm', 'file_a.py'], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Delete file_a'],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )
        
        return self.repo_path
    
    def cleanup(self):
        """Clean up temporary repository."""
        if self.temp_dir and Path(self.temp_dir).exists():
            try:
                # On Windows, Git may lock files - retry with onerror handler
                def handle_remove_readonly(func, path, exc):
                    """Error handler for Windows readonly file issues."""
                    import stat
                    import os
                    if not os.access(path, os.W_OK):
                        os.chmod(path, stat.S_IWUSR)
                        func(path)
                    else:
                        raise
                
                shutil.rmtree(self.temp_dir, onerror=handle_remove_readonly)
            except Exception as e:
                # Log but don't fail - temp files will be cleaned up by OS
                import warnings
                warnings.warn(f"Failed to clean up temp directory: {e}")


@pytest.fixture
def test_git_repo():
    """
    Pytest fixture that creates a test Git repository.
    
    Yields:
        Path to test repository
    """
    repo = TestGitRepository()
    try:
        yield repo.create()
    finally:
        repo.cleanup()


@pytest.fixture
def git_service():
    """Pytest fixture for GitHistoryService."""
    return GitHistoryService(max_commits=100)


@pytest.fixture
def db_repository(db: Session):
    """Pytest fixture for test repository in database."""
    repository = Repository(
        owner='testowner',
        name='testrepo',
        full_name='testowner/testrepo',
        github_url='https://github.com/testowner/testrepo',
        default_branch='main'
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


class TestGitHistoryService:
    """Tests for GitHistoryService."""
    
    def test_extract_commits(self, git_service: GitHistoryService, test_git_repo: Path):
        """Test extracting commits from a Git repository."""
        commits = git_service.extract_commits(test_git_repo)
        
        # Should have 5 commits
        assert len(commits) == 5
        
        # Verify commit structure
        for commit in commits:
            assert 'commit_hash' in commit
            assert 'author_name' in commit
            assert 'author_email' in commit
            assert 'commit_message' in commit
            assert 'committed_at' in commit
            assert 'parent_hashes' in commit
            
            # Verify data types
            assert isinstance(commit['commit_hash'], str)
            assert len(commit['commit_hash']) == 40  # Full SHA
            assert isinstance(commit['author_name'], str)
            assert isinstance(commit['author_email'], str)
            assert isinstance(commit['committed_at'], datetime)
            assert isinstance(commit['parent_hashes'], list)
        
        # Verify commits are in chronological order (most recent first)
        assert 'Delete file_a' in commits[0]['commit_message']
        assert 'Add file_a.py' in commits[4]['commit_message']
    
    def test_extract_file_changes_added(self, git_service: GitHistoryService, test_git_repo: Path):
        """Test extracting file changes for added files."""
        commits = git_service.extract_commits(test_git_repo)
        
        # Find the first commit (Add file_a.py)
        first_commit = [c for c in commits if 'Add file_a.py' in c['commit_message']][0]
        
        file_changes = git_service.extract_file_changes(test_git_repo, first_commit['commit_hash'])
        
        # Should have 1 file change
        assert len(file_changes) == 1
        
        change = file_changes[0]
        assert change['path'] == 'file_a.py'
        assert change['change_type'] == 'added'
        assert change['additions'] > 0
        assert change['deletions'] == 0
    
    def test_extract_file_changes_modified(self, git_service: GitHistoryService, test_git_repo: Path):
        """Test extracting file changes for modified files."""
        commits = git_service.extract_commits(test_git_repo)
        
        # Find commit that modifies both files
        modify_commit = [c for c in commits if 'Modify both files' in c['commit_message']][0]
        
        file_changes = git_service.extract_file_changes(test_git_repo, modify_commit['commit_hash'])
        
        # Should have 2 file changes
        assert len(file_changes) == 2
        
        # Both should be modifications
        for change in file_changes:
            assert change['change_type'] == 'modified'
            assert change['additions'] > 0 or change['deletions'] > 0
    
    def test_extract_file_changes_renamed(self, git_service: GitHistoryService, test_git_repo: Path):
        """Test extracting file changes for renamed files."""
        commits = git_service.extract_commits(test_git_repo)
        
        # Find rename commit
        rename_commit = [c for c in commits if 'Rename file_b to file_c' in c['commit_message']][0]
        
        file_changes = git_service.extract_file_changes(test_git_repo, rename_commit['commit_hash'])
        
        # Should have 1 file change (rename)
        assert len(file_changes) == 1
        
        change = file_changes[0]
        assert change['change_type'] == 'renamed'
        assert change['old_path'] == 'file_b.js'
        assert change['new_path'] == 'file_c.js'
        assert change['path'] == 'file_c.js'
    
    def test_extract_file_changes_deleted(self, git_service: GitHistoryService, test_git_repo: Path):
        """Test extracting file changes for deleted files."""
        commits = git_service.extract_commits(test_git_repo)
        
        # Find delete commit
        delete_commit = [c for c in commits if 'Delete file_a' in c['commit_message']][0]
        
        file_changes = git_service.extract_file_changes(test_git_repo, delete_commit['commit_hash'])
        
        # Should have 1 file change (delete)
        assert len(file_changes) == 1
        
        change = file_changes[0]
        assert change['path'] == 'file_a.py'
        assert change['change_type'] == 'deleted'
        assert change['additions'] == 0
        assert change['deletions'] > 0
    
    def test_extract_repository_history_complete(
        self,
        git_service: GitHistoryService,
        test_git_repo: Path
    ):
        """Test extracting complete repository history with file changes."""
        # Note: extract_repository_history requires a GitHub URL and clones the repo,
        # so we'll test the component methods instead
        commits = git_service.extract_commits(test_git_repo)
        
        # Verify all commits have file changes extracted
        for commit in commits:
            file_changes = git_service.extract_file_changes(test_git_repo, commit['commit_hash'])
            commit['file_changes'] = file_changes
        
        # Verify each commit has file changes
        assert all('file_changes' in c for c in commits)
        assert all(len(c['file_changes']) > 0 for c in commits)


class TestGitHistoryPersistence:
    """Tests for Git history persistence."""
    
    def test_persist_git_history(
        self,
        git_service: GitHistoryService,
        test_git_repo: Path,
        db_repository: Repository,
        db: Session
    ):
        """Test persisting Git history to database."""
        # Extract commits
        commits = git_service.extract_commits(test_git_repo)
        
        # Extract file changes for each commit
        for commit in commits:
            commit['file_changes'] = git_service.extract_file_changes(
                test_git_repo,
                commit['commit_hash']
            )
        
        # Persist to database
        persistence_service = PersistenceService(db)
        new_commits = persistence_service.persist_git_history(
            db_repository,
            commits
        )
        
        # Verify all commits were persisted
        assert new_commits == 5
        
        # Query commits from database
        db_commits = db.query(Commit).filter(
            Commit.repository_id == db_repository.id
        ).all()
        
        assert len(db_commits) == 5
        
        # Verify commit data
        for db_commit in db_commits:
            assert db_commit.commit_hash is not None
            assert len(db_commit.commit_hash) == 40
            assert db_commit.author_name == 'Test User'
            assert db_commit.author_email == 'test@example.com'
            assert db_commit.commit_message is not None
            assert db_commit.committed_at is not None
    
    def test_persist_file_changes(
        self,
        git_service: GitHistoryService,
        test_git_repo: Path,
        db_repository: Repository,
        db: Session
    ):
        """Test persisting file changes to database."""
        # Extract and persist commits
        commits = git_service.extract_commits(test_git_repo)
        for commit in commits:
            commit['file_changes'] = git_service.extract_file_changes(
                test_git_repo,
                commit['commit_hash']
            )
        
        persistence_service = PersistenceService(db)
        persistence_service.persist_git_history(db_repository, commits)
        
        # Query file changes from database
        db_file_changes = db.query(CommitFileChange).join(
            Commit
        ).filter(
            Commit.repository_id == db_repository.id
        ).all()
        
        # Should have file changes for all commits
        assert len(db_file_changes) > 0
        
        # Verify change types are present
        change_types = {fc.change_type for fc in db_file_changes}
        assert ChangeType.ADDED in change_types
        assert ChangeType.MODIFIED in change_types
        assert ChangeType.DELETED in change_types
        assert ChangeType.RENAMED in change_types
    
    def test_duplicate_commit_handling(
        self,
        git_service: GitHistoryService,
        test_git_repo: Path,
        db_repository: Repository,
        db: Session
    ):
        """Test that duplicate commits are not persisted."""
        # Extract commits
        commits = git_service.extract_commits(test_git_repo)
        for commit in commits:
            commit['file_changes'] = git_service.extract_file_changes(
                test_git_repo,
                commit['commit_hash']
            )
        
        persistence_service = PersistenceService(db)
        
        # Persist commits first time
        new_commits_1 = persistence_service.persist_git_history(db_repository, commits)
        assert new_commits_1 == 5
        
        # Persist same commits again
        new_commits_2 = persistence_service.persist_git_history(db_repository, commits)
        assert new_commits_2 == 0  # No new commits
        
        # Verify total commits in database
        db_commits = db.query(Commit).filter(
            Commit.repository_id == db_repository.id
        ).all()
        
        assert len(db_commits) == 5  # Still only 5 commits
    
    def test_repository_isolation(
        self,
        git_service: GitHistoryService,
        test_git_repo: Path,
        db: Session
    ):
        """Test that commits are isolated per repository."""
        # Create two repositories
        repo1 = Repository(
            owner='owner1',
            name='repo1',
            full_name='owner1/repo1',
            github_url='https://github.com/owner1/repo1',
            default_branch='main'
        )
        repo2 = Repository(
            owner='owner2',
            name='repo2',
            full_name='owner2/repo2',
            github_url='https://github.com/owner2/repo2',
            default_branch='main'
        )
        db.add_all([repo1, repo2])
        db.commit()
        db.refresh(repo1)
        db.refresh(repo2)
        
        # Extract commits
        commits = git_service.extract_commits(test_git_repo)
        for commit in commits:
            commit['file_changes'] = git_service.extract_file_changes(
                test_git_repo,
                commit['commit_hash']
            )
        
        persistence_service = PersistenceService(db)
        
        # Persist to repo1
        persistence_service.persist_git_history(repo1, commits)
        
        # Persist to repo2
        persistence_service.persist_git_history(repo2, commits)
        
        # Verify repo1 has 5 commits
        repo1_commits = db.query(Commit).filter(
            Commit.repository_id == repo1.id
        ).all()
        assert len(repo1_commits) == 5
        
        # Verify repo2 has 5 commits
        repo2_commits = db.query(Commit).filter(
            Commit.repository_id == repo2.id
        ).all()
        assert len(repo2_commits) == 5
        
        # Verify commits are distinct
        repo1_ids = {c.id for c in repo1_commits}
        repo2_ids = {c.id for c in repo2_commits}
        assert repo1_ids.isdisjoint(repo2_ids)


class TestGitHistoryAPI:
    """Tests for Git history API endpoints."""
    
    @pytest.fixture
    def setup_history(
        self,
        git_service: GitHistoryService,
        test_git_repo: Path,
        db_repository: Repository,
        db: Session
    ):
        """Setup: Extract and persist Git history."""
        commits = git_service.extract_commits(test_git_repo)
        for commit in commits:
            commit['file_changes'] = git_service.extract_file_changes(
                test_git_repo,
                commit['commit_hash']
            )
        
        persistence_service = PersistenceService(db)
        persistence_service.persist_git_history(db_repository, commits)
        
        return db_repository
    
    def test_list_commits(self, client, setup_history, db: Session):
        """Test listing commits via API."""
        repository = setup_history
        
        response = client.get(f"/api/repositories/{repository.id}/commits")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'items' in data
        assert 'total' in data
        assert 'page' in data
        assert 'page_size' in data
        
        assert data['total'] == 5
        assert len(data['items']) == 5
        
        # Verify commit structure
        commit = data['items'][0]
        assert 'id' in commit
        assert 'commit_hash' in commit
        assert 'short_hash' in commit
        assert 'author_name' in commit
        assert 'subject' in commit
        assert 'committed_at' in commit
    
    def test_get_commit_detail(self, client, setup_history, db: Session):
        """Test getting commit details via API."""
        repository = setup_history
        
        # Get first commit
        commits = db.query(Commit).filter(
            Commit.repository_id == repository.id
        ).all()
        commit = commits[0]
        
        response = client.get(
            f"/api/repositories/{repository.id}/commits/{commit.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['id'] == str(commit.id)
        assert data['commit_hash'] == commit.commit_hash
        assert 'file_changes' in data
        assert 'total_additions' in data
        assert 'total_deletions' in data
        assert 'files_changed' in data
    
    def test_invalid_repository(self, client, db: Session):
        """Test API with invalid repository ID."""
        fake_uuid = uuid4()
        
        response = client.get(f"/api/repositories/{fake_uuid}/commits")
        
        assert response.status_code == 404
        assert 'not found' in response.json()['detail'].lower()
    
    def test_invalid_commit(self, client, setup_history):
        """Test API with invalid commit ID."""
        repository = setup_history
        fake_uuid = uuid4()
        
        response = client.get(
            f"/api/repositories/{repository.id}/commits/{fake_uuid}"
        )
        
        assert response.status_code == 404

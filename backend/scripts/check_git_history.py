"""
Quick script to check for repositories with Git history in the database.
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Repository, Commit


def main():
    """Check for repositories with Git history."""
    db = next(get_db())
    
    try:
        # Get all repositories
        repos = db.execute(select(Repository)).scalars().all()
        
        if not repos:
            print("No repositories found in database.")
            return
        
        print(f"\nFound {len(repos)} repository(ies) in database:\n")
        
        for repo in repos:
            # Count commits for this repository
            commit_count = db.execute(
                select(func.count(Commit.id))
                .where(Commit.repository_id == repo.id)
            ).scalar()
            
            print(f"Repository: {repo.full_name}")
            print(f"  ID: {repo.id}")
            print(f"  Git History: {commit_count} commits")
            print()
            
    finally:
        db.close()


if __name__ == "__main__":
    main()

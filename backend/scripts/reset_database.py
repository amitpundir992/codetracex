"""
Reset database to clean state.

This script:
1. Drops all tables
2. Drops all enum types
3. Drops alembic_version table

Use this when you need to start fresh with migrations.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.session import engine


def reset_database():
    """Drop all tables, enums, and alembic version."""
    with engine.connect() as conn:
        print("🗑️  Dropping all tables and types...")
        
        # Drop all tables
        drop_tables = """
        DROP TABLE IF EXISTS function_calls CASCADE;
        DROP TABLE IF EXISTS imports CASCADE;
        DROP TABLE IF EXISTS symbols CASCADE;
        DROP TABLE IF EXISTS relationships CASCADE;
        DROP TABLE IF EXISTS files CASCADE;
        DROP TABLE IF EXISTS analysis_runs CASCADE;
        DROP TABLE IF EXISTS repositories CASCADE;
        DROP TABLE IF EXISTS alembic_version CASCADE;
        """
        
        # Drop all enum types
        drop_types = """
        DROP TYPE IF EXISTS analysisstatus CASCADE;
        DROP TYPE IF EXISTS symboltype CASCADE;
        DROP TYPE IF EXISTS relationshiptype CASCADE;
        """
        
        try:
            conn.execute(text(drop_tables))
            conn.execute(text(drop_types))
            conn.commit()
            print("✅ Database reset complete!")
            print("\nNext steps:")
            print("1. Run: alembic upgrade head")
            print("2. This will create all tables fresh")
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()
            raise


if __name__ == "__main__":
    confirm = input("⚠️  This will DELETE ALL DATA in the database. Continue? (yes/no): ")
    if confirm.lower() == "yes":
        reset_database()
    else:
        print("Cancelled.")

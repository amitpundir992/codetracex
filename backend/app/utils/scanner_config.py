"""
Configuration for the file scanner.

Defines which directories and files to ignore, how to detect binary files,
and how to map file extensions to programming languages.
"""

# Directories to ignore during repository scanning
# These are typically generated directories, dependency caches, or version control
IGNORED_DIRECTORIES = {
    ".git",           # Git version control
    ".svn",           # Subversion version control
    ".hg",            # Mercurial version control
    "node_modules",   # Node.js dependencies
    ".next",          # Next.js build output
    "dist",           # Distribution/build output
    "build",          # Build output
    "out",            # Build output
    "coverage",       # Test coverage reports
    "__pycache__",    # Python bytecode cache
    ".pytest_cache",  # Pytest cache
    ".venv",          # Python virtual environment
    "venv",           # Python virtual environment
    "env",            # Python virtual environment
    "target",         # Rust/Java build output
    "vendor",         # Go/PHP dependencies
    ".gradle",        # Gradle build cache
    ".mvn",           # Maven cache
    "bin",            # Binary output (common in Java/C# projects)
    "obj",            # Object files (C#/.NET)
    ".nuget",         # NuGet package cache
    "packages",       # Package cache
    ".idea",          # IntelliJ IDEA settings
    ".vscode",        # VS Code settings (may contain workspace-specific settings)
    ".vs",            # Visual Studio settings
    ".cache",         # Generic cache directory
    ".tmp",           # Temporary files
    "tmp",            # Temporary files
    "temp",           # Temporary files
}

# File extensions that indicate binary/media files
# These should not be scanned for source code
BINARY_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff", ".tif",
    # Audio
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
    # Video
    ".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".m4v",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz", ".tgz",
    # Executables and libraries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".app",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # Database
    ".db", ".sqlite", ".sqlite3",
    # Other
    ".pyc", ".pyo", ".class", ".o", ".a", ".lib",
}

# File extensions that often contain secrets or sensitive data
# These should be scanned but handled carefully
SENSITIVE_FILE_PATTERNS = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "secrets.json",
    "credentials.json",
    ".npmrc",
    ".pypirc",
}

# Mapping of file extensions to programming languages
# This is a simplified mapping for Phase 2
# More sophisticated language detection can be added in future phases
LANGUAGE_MAP = {
    # Web
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".vue": "Vue",
    
    # Python
    ".py": "Python",
    ".pyx": "Cython",
    ".pyi": "Python",
    
    # Java/JVM
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".groovy": "Groovy",
    
    # C family
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".hxx": "C++",
    ".cs": "C#",
    
    # Rust
    ".rs": "Rust",
    
    # Go
    ".go": "Go",
    
    # Ruby
    ".rb": "Ruby",
    ".rake": "Ruby",
    
    # PHP
    ".php": "PHP",
    
    # Swift
    ".swift": "Swift",
    
    # Shell
    ".sh": "Shell",
    ".bash": "Bash",
    ".zsh": "Zsh",
    ".fish": "Fish",
    
    # R
    ".r": "R",
    ".R": "R",
    
    # SQL
    ".sql": "SQL",
    
    # Configuration and data
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".cfg": "Config",
    ".conf": "Config",
    
    # Markdown and documentation
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    
    # Other
    ".lua": "Lua",
    ".pl": "Perl",
    ".pm": "Perl",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".jl": "Julia",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
}


def is_binary_file(filename: str) -> bool:
    """
    Check if a file is likely binary based on its extension.
    
    Args:
        filename: Name or path of the file
        
    Returns:
        True if the file is binary, False otherwise
    """
    extension = get_file_extension(filename)
    return extension in BINARY_EXTENSIONS


def is_sensitive_file(filename: str) -> bool:
    """
    Check if a file might contain sensitive data.
    
    Args:
        filename: Name or path of the file
        
    Returns:
        True if the file might contain secrets, False otherwise
    """
    return filename in SENSITIVE_FILE_PATTERNS


def get_file_extension(filename: str) -> str:
    """
    Extract the file extension from a filename.
    
    Args:
        filename: Name or path of the file
        
    Returns:
        File extension including the dot (e.g., ".py"), or empty string if no extension
    """
    if "." not in filename:
        return ""
    
    return "." + filename.rsplit(".", 1)[1].lower()


def detect_language(filename: str) -> str | None:
    """
    Detect the programming language based on file extension.
    
    Args:
        filename: Name or path of the file
        
    Returns:
        Language name if detected, None otherwise
    """
    extension = get_file_extension(filename)
    return LANGUAGE_MAP.get(extension)

"""Production configuration with Azure DI + PostgreSQL + Claude."""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class AzureConfig:
    """Azure Document Intelligence configuration."""
    endpoint: str
    key: str
    model_id: str = "prebuilt-document"  # or "prebuilt-layout" for complex tables

    @classmethod
    def from_env(cls) -> Optional["AzureConfig"]:
        endpoint = os.environ.get("AZURE_DI_ENDPOINT")
        key = os.environ.get("AZURE_DI_KEY")
        if endpoint and key:
            return cls(endpoint=endpoint, key=key)
        return None


@dataclass
class PostgresConfig:
    """PostgreSQL configuration."""
    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def from_env(cls) -> Optional["PostgresConfig"]:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = int(os.environ.get("POSTGRES_PORT", "5432"))
        database = os.environ.get("POSTGRES_DB", "clinical_trials")
        user = os.environ.get("POSTGRES_USER")
        password = os.environ.get("POSTGRES_PASSWORD")
        if user and password:
            return cls(host=host, port=port, database=database, user=user, password=password)
        return None


@dataclass
class ClaudeConfig:
    """Claude API configuration."""
    api_key: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192

    @classmethod
    def from_env(cls) -> Optional["ClaudeConfig"]:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return cls(api_key=api_key)
        return None


@dataclass
class ProductionConfig:
    """Complete production configuration."""
    azure: Optional[AzureConfig]
    postgres: Optional[PostgresConfig]
    claude: Optional[ClaudeConfig]

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = None
    output_dir: Path = None

    def __post_init__(self):
        self.data_dir = self.base_dir / "data"
        self.output_dir = self.data_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls) -> "ProductionConfig":
        return cls(
            azure=AzureConfig.from_env(),
            postgres=PostgresConfig.from_env(),
            claude=ClaudeConfig.from_env(),
        )

    @property
    def database_url(self) -> str:
        """Get database URL - PostgreSQL if available, else SQLite."""
        if self.postgres:
            return self.postgres.url
        return f"sqlite:///{self.data_dir / 'database' / 'clinical_trials.db'}"

    def validate(self) -> dict:
        """Validate configuration and return status."""
        return {
            "azure_di": self.azure is not None,
            "postgresql": self.postgres is not None,
            "claude": self.claude is not None,
            "database_url": self.database_url,
        }


# Environment variable template
ENV_TEMPLATE = """
# Azure Document Intelligence
AZURE_DI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DI_KEY=your-azure-di-key

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=clinical_trials
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key
"""

"""Application configuration using pydantic-settings with Azure Key Vault support."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class AzureKeyVaultSettings(BaseSettings):
    """Load secrets from Azure Key Vault when vault_url is configured."""

    key_vault_url: str | None = Field(default=None, description="Azure Key Vault URL. If set, secrets are loaded from Key Vault.")

    def get_secret(self, secret_name: str) -> str | None:
        if not self.key_vault_url:
            return None
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=self.key_vault_url, credential=credential)
        return client.get_secret(secret_name).value


class AsyncApiSettings(BaseSettings):
    """Configuration for async (fire-and-forget) API services."""

    model_config = SettingsConfigDict(env_prefix="ASYNC_API_")

    base_url: str = "http://localhost:8080"
    timeout: float = 30.0
{%- if cookiecutter.auth_method == "bearer_token" %}
    api_key: str = ""
{%- endif %}


class DataServiceSettings(BaseSettings):
    """Configuration for data (CRUD) services."""

    model_config = SettingsConfigDict(env_prefix="DATA_SERVICE_")

    base_url: str = "http://localhost:8081"
    timeout: float = 30.0
{%- if cookiecutter.auth_method == "bearer_token" %}
    api_key: str = ""
{%- endif %}


class LogicServiceSettings(BaseSettings):
    """Configuration for logic (request-response) services."""

    model_config = SettingsConfigDict(env_prefix="LOGIC_SERVICE_")

    base_url: str = "http://localhost:8082"
    timeout: float = 30.0
{%- if cookiecutter.auth_method == "bearer_token" %}
    api_key: str = ""
{%- endif %}


class Settings(AzureKeyVaultSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Agent settings
    agent_name: str = "{{ cookiecutter.project_name }}"
    agent_instructions: str = "You are a helpful conversational AI assistant."

    # Azure OpenAI / Model provider settings
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
{%- if cookiecutter.model_provider == "pydantic_ai_custom" %}
    custom_model_api_key: str = ""
    custom_model_base_url: str = ""
    custom_model_name: str = ""
{%- endif %}

    # Memory settings
{%- if cookiecutter.memory_provider == "azure-foundry" %}
    foundry_project_endpoint: str = ""
    memory_store_name: str = "{{ cookiecutter.project_slug }}-memory"
{%- elif cookiecutter.memory_provider == "grafeo-memory" %}
    grafeo_memory_db_dir: str = "./memory"
    grafeo_memory_model: str = "openai:gpt-4o-mini"
{%- elif cookiecutter.memory_provider == "mem0" %}
    mem0_api_key: str = ""
{%- endif %}

    # Inbound auth (user identity for memory isolation)
    auth_enabled: bool = False
    auth_jwks_url: str = ""
    auth_audience: str = ""
    auth_issuer: str = ""

    # Human-in-the-loop settings
    hitl_approval_timeout: float = 300.0
    hitl_tools_requiring_approval: str = "send_quote_for_approval,update_preferences,create_entity"

    # Conversation history
    max_turns: int = 40

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    # Rate limiting (requests per minute / burst)
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10

    # Service configs
    async_api: AsyncApiSettings = AsyncApiSettings()
    data_service: DataServiceSettings = DataServiceSettings()
    logic_service: LogicServiceSettings = LogicServiceSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()

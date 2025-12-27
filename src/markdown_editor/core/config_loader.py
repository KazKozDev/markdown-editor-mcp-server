"""
Configuration loader with two-level system:
1. Local config (tool defaults)
2. Central config (overrides from main project)
"""

import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class LLMConfig:
    """LLM provider settings"""

    provider: str = "ollama"
    model: str = "qwen3:14b"
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    temperature: float = 0.3
    max_tokens: int = 4096
    api_key: Optional[str] = None


@dataclass
class JournalConfig:
    """Change journal settings"""

    enabled: bool = True
    persist: bool = True
    storage: str = "json"  # json, sqlite, memory
    path: str = "./journal.json"
    max_entries: int = 1000


@dataclass
class DocumentConfig:
    """Document processing settings"""

    parser: str = "marko"
    strict_validation: bool = True
    preserve_formatting: bool = True
    journal: JournalConfig = field(default_factory=JournalConfig)
    transactions_enabled: bool = True
    auto_rollback_on_error: bool = True


@dataclass
class AgentConfig:
    """Agent settings"""

    max_iterations: int = 10
    prompts_path: str = "./prompts/"
    log_operations: bool = True
    log_level: str = "INFO"


@dataclass
class Config:
    """Main tool configuration"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    document: DocumentConfig = field(default_factory=DocumentConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge of dictionaries.
    Values from override replace values from base.
    """
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def expand_env_vars(config: dict) -> dict:
    """
    Expands environment variables in config values.
    Format: ${VAR_NAME} or $VAR_NAME
    """
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = expand_env_vars(value)
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            result[key] = os.environ.get(env_var, value)
        elif isinstance(value, str) and value.startswith("$"):
            env_var = value[1:]
            result[key] = os.environ.get(env_var, value)
        else:
            result[key] = value
    return result


def load_yaml(path: Path) -> dict:
    """Load YAML file"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class ConfigLoader:
    """
    Configuration loader with support for:
    - Local defaults
    - Central config
    - Environment variables
    """

    def __init__(
        self,
        local_config_path: Optional[str] = None,
        central_config_path: Optional[str] = None,
        env_prefix: str = "DOCUMENT_TOOL_",
    ):

        self.env_prefix = env_prefix

        # Determine path to local config
        if local_config_path:
            self.local_path = Path(local_config_path)
        else:
            # Default - next to this file
            self.local_path = Path(__file__).parent.parent / "config" / "default.yaml"

        self.central_path = Path(central_config_path) if central_config_path else None

    def load(self) -> Config:
        """
        Load config with priorities:
        1. Code defaults
        2. Local config
        3. Central config (document_tool section)
        4. Environment variables
        """

        # 1. Load local config
        local_config = load_yaml(self.local_path)

        # 2. If central exists - merge
        if self.central_path and self.central_path.exists():
            central_config = load_yaml(self.central_path)

            # Take global LLM settings
            if "llm" in central_config:
                local_config = deep_merge(local_config, {"llm": central_config["llm"]})

            # Take specific document_tool settings
            if "document_tool" in central_config:
                local_config = deep_merge(local_config, central_config["document_tool"])

        # 3. Expand environment variables
        local_config = expand_env_vars(local_config)

        # 4. Apply environment variables with prefix
        local_config = self._apply_env_overrides(local_config)

        # 5. Build typed config
        return self._build_config(local_config)

    def _apply_env_overrides(self, config: dict) -> dict:
        """
        Apply overrides from environment variables.
        DOCUMENT_TOOL_LLM_MODEL=gpt-4 -> config["llm"]["model"] = "gpt-4"
        """
        for key, value in os.environ.items():
            if not key.startswith(self.env_prefix):
                continue

            # Remove prefix and split by _
            parts = key[len(self.env_prefix) :].lower().split("_")

            # Navigate through config
            current = config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set value
            final_key = parts[-1]
            # Try to convert to number
            try:
                current[final_key] = int(value)
            except ValueError:
                try:
                    current[final_key] = float(value)
                except ValueError:
                    if value.lower() in ("true", "false"):
                        current[final_key] = value.lower() == "true"
                    else:
                        current[final_key] = value

        return config

    def _build_config(self, raw: dict) -> Config:
        """Build typed config from dictionary"""

        # LLM
        llm_raw = raw.get("llm", {})
        llm = LLMConfig(
            provider=llm_raw.get("provider", "ollama"),
            model=llm_raw.get("model", "qwen3:14b"),
            base_url=llm_raw.get("base_url", "http://localhost:11434"),
            timeout=llm_raw.get("timeout", 120),
            temperature=llm_raw.get("temperature", 0.3),
            max_tokens=llm_raw.get("max_tokens", 4096),
            api_key=llm_raw.get("api_key"),
        )

        # Journal
        doc_raw = raw.get("document", {})
        journal_raw = doc_raw.get("journal", {})
        journal = JournalConfig(
            enabled=journal_raw.get("enabled", True),
            persist=journal_raw.get("persist", True),
            storage=journal_raw.get("storage", "json"),
            path=journal_raw.get("path", "./journal.json"),
            max_entries=journal_raw.get("max_entries", 1000),
        )

        # Document
        document = DocumentConfig(
            parser=doc_raw.get("parser", "marko"),
            strict_validation=doc_raw.get("strict_validation", True),
            preserve_formatting=doc_raw.get("preserve_formatting", True),
            journal=journal,
            transactions_enabled=doc_raw.get("transactions", {}).get("enabled", True),
            auto_rollback_on_error=doc_raw.get("transactions", {}).get(
                "auto_rollback_on_error", True
            ),
        )

        # Agent
        agent_raw = raw.get("agent", {})
        agent = AgentConfig(
            max_iterations=agent_raw.get("max_iterations", 10),
            prompts_path=agent_raw.get("prompts_path", "./prompts/"),
            log_operations=agent_raw.get("log_operations", True),
            log_level=agent_raw.get("log_level", "INFO"),
        )

        return Config(llm=llm, document=document, agent=agent)


def load_config(central_config_path: Optional[str] = None) -> Config:
    """
    Convenient function for loading config.

    Usage:
        # Local config only
        config = load_config()

        # With central config
        config = load_config("/path/to/central/config.yaml")
    """
    loader = ConfigLoader(central_config_path=central_config_path)
    return loader.load()


if __name__ == "__main__":
    # Load test
    config = load_config()
    print(f"LLM Provider: {config.llm.provider}")
    print(f"Model: {config.llm.model}")
    print(f"Base URL: {config.llm.base_url}")
    print(f"Parser: {config.document.parser}")

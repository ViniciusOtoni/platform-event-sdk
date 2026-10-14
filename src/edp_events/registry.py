"""Registro dos JSON Schemas do domínio no Azure Schema Registry (ADR-0003).

O runtime é efêmero (ADR-0010): o registry é recriado vazio a cada ``env up``. Por isso o PRODUTOR
registra seus schemas ao iniciar, de forma idempotente (mesmo conteúdo => mesmo id). A governança
(lint, compatibilidade) acontece antes, no CI, via platform-contracts-tooling (ADR-0005).

Requer o extra ``eventhubs`` e a role ``Schema Registry Contributor`` no schema group do domínio.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_schemas(path: str | Path) -> dict[str, str]:
    """``{tipo_de_evento: definição JSON canônica}`` a partir de ``<tipo>.schema.json``."""
    out = {}
    for file in sorted(Path(path).glob("*.schema.json")):
        schema = json.loads(file.read_text(encoding="utf-8"))
        out[file.name.removesuffix(".schema.json")] = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    return out


def register_schemas(
    schemas_dir: str | Path,
    fully_qualified_namespace: str,
    group: str,
    credential=None,
    client=None,
) -> dict[str, str]:
    """Registra cada schema (nome = tipo do evento) e retorna ``{tipo: schema_id}``."""
    if client is None:
        from azure.identity import DefaultAzureCredential
        from azure.schemaregistry import SchemaRegistryClient

        client = SchemaRegistryClient(fully_qualified_namespace, credential or DefaultAzureCredential())

    from azure.schemaregistry import SchemaFormat

    ids = {}
    for event_type, definition in load_schemas(schemas_dir).items():
        props = client.register_schema(group, event_type, definition, SchemaFormat.JSON)
        ids[event_type] = props.id
        log.info("Schema %s registrado no grupo %s (id=%s)", event_type, group, props.id)
    return ids

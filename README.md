# platform-event-sdk (`edp-events`)

SDK Python da plataforma de dados event-driven. Ele entrega aos domínios a **publicação confiável de eventos de integração**, sem que cada time reimplemente o padrão:

| Módulo | O que faz | ADR |
|---|---|---|
| `edp_events.naming` | Valida o tipo `<dominio>.<agregado>.<evento>.v<n>`, deriva o event hub `<dominio>.<agregado>.v<n>` e rejeita eventos CRUD (`*.atualizado`) | 0008 |
| `edp_events.envelope` | CloudEvents 1.0 (JSON) com as extensões `aggregateid`, `aggregateversion` e `traceparent` | 0003 |
| `edp_events.schema` | Valida o `data` contra o JSON Schema do contrato, antes de gravar | 0003, 0005 |
| `edp_events.outbox` | **Transactional Outbox**: tabela, gravação na mesma transação e relay com `FOR UPDATE SKIP LOCKED` | 0002 |
| `edp_events.publishers.eventhubs` | Publica no Event Hubs com Entra ID (Workload Identity), usando `partition_key` = id do agregado | 0003, 0008 |

## Instalação

Os wheels são publicados como **assets de GitHub Release**, porque o GitHub Packages não suporta PyPI:

```bash
pip install "edp-events[eventhubs] @ https://github.com/ViniciusOtoni/platform-event-sdk/releases/download/v0.1.0/edp_events-0.1.0-py3-none-any.whl"
```

## Uso

```python
from sqlalchemy import MetaData
from edp_events import SchemaValidator, add_to_outbox, new_event, register_outbox

metadata = MetaData()                    # o mesmo metadata dos modelos do serviço (Alembic enxerga a outbox)
outbox = register_outbox(metadata)
validator = SchemaValidator.from_directory("contracts/schemas")

with Session() as session, session.begin():          # UMA transação
    session.add(pedido)                                # estado do agregado
    add_to_outbox(session, outbox, new_event(         # evento de integração
        type="pedidos.pedido.criado.v1",
        source="/dominios/pedidos/pedidos-api",
        aggregate="pedido",
        aggregate_id=pedido.pedido_id,
        aggregate_version=pedido.versao,
        data={...},
    ), validator)
```

O worker do relay roda num Deployment separado:

```python
from edp_events import OutboxRelay
from edp_events.publishers.eventhubs import EventHubsPublisher

OutboxRelay(Session, outbox, EventHubsPublisher("evhns-edp-dev-xxxxx.servicebus.windows.net")).run_forever()
```

## Garantias e responsabilidades

- **At-least-once:** se o relay cair entre publicar e marcar o evento como publicado, ele republica. Os consumidores **devem** deduplicar pelo `id` do evento.
- **Ordem por agregado:** o relay lê os eventos por `created_at` e **interrompe o lote no primeiro erro**, para não publicar a versão N+1 antes da N. O Event Hubs mantém a ordem dentro da partição.
- **Fora do contrato não sai:** com o `validator`, um evento inválido gera exceção, e a transação de negócio sofre rollback junto.
- **Sem segredos:** o publisher usa `DefaultAzureCredential`, ou seja, Workload Identity no AKS e `az login` localmente.

## Por que AMQP e não Kafka para publicar?

O namespace expõe os dois protocolos. O SDK `azure-eventhub` (AMQP) autentica nativamente com Entra ID e aceita `partition_key` sem configuração extra. O endpoint Kafka continua disponível para consumidores como o Spark.

## Desenvolvimento

```bash
pip install -e ".[dev,eventhubs]"
ruff check . && pytest
```

Para lançar uma versão: atualize `version` no `pyproject.toml` e crie a tag `vX.Y.Z`. O CD publica o wheel e move a tag `v0`/`v1`.

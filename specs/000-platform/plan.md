# Platform Foundation — plan

## Estrategia

Implementar de dentro hacia afuera:

1. contratos;
2. dataset/generator;
3. core + outbox;
4. fraud engine local;
5. Azure hot path;
6. Azure cold path;
7. AWS digital layer;
8. GenAI/portal;
9. IaC/CI/CD;
10. pruebas end-to-end.

## Decisiones físicas Student

- PostgreSQL local.
- AWS Lambda BFF.
- Event Hubs.
- un Container App `fraud-engine` inicialmente.
- Azure SQL compartido por schemas para profiles/cases.
- Service Bus para HIGH.
- ADLS para lake.
- Synapse/OpenAI bajo demanda.

## Interfaces

- `TransactionPosted.v1`
- `FraudScore.v1`
- `CreateFraudCase.v1`
- `AnalystDecision.v1`

## Verificación

Cada fase debe producir tests + evidencia antes de desplegar la siguiente capa.

# Prompt — AWS Digital Layer eficiente

Implementa/despliega la capa AWS para `<OBJETIVO>` sin alterar la división AWS/on-prem/Azure.

Lee solo:
- Source of Truth;
- spec relevante;
- `infra/aws/sam`;
- código `src/aws-digital` afectado.

Baseline Student:
- S3 + CloudFront;
- API Gateway HTTP API;
- Cognito;
- una Lambda BFF.

No añadas ECS/Fargate, RDS, MSK, ElastiCache u otros servicios salvo ADR/requirement explícito.

Proceso:
1. `sam validate`/equivalente;
2. tests locales;
3. plan de cambios;
4. deploy mínimo;
5. smoke test;
6. reportar recursos/costos persistentes y teardown.

WAF se activa cuando la task sea demostrar/perfilar el control perimetral; no bloquea el desarrollo funcional temprano.

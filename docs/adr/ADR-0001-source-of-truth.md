# ADR-0001 — Fuente de verdad única

**Estado:** Accepted  
**Fecha:** 2026-09-20

## Contexto

Los primeros avances contienen decisiones correctas pero repetidas con pequeñas variaciones sobre Functions/Container Apps, casos MEDIUM/HIGH, profile stores, backend AWS y servicios de producción vs Student.

## Decisión

`docs/00_SOURCE_OF_TRUTH.md` será el único baseline arquitectónico. Specs, contratos, IaC y código son derivados. Cambios de arquitectura requieren ADR.

## Consecuencias

- Menos contradicciones entre agentes/equipo.
- Las specs se vuelven ejecutables y acotadas.
- Un agente no puede “mejorar” el diseño introduciendo otro stack silenciosamente.

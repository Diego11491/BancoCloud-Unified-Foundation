# ADR-0002 — Consolidación física para Student

**Estado:** Accepted  
**Fecha:** 2026-09-20

## Contexto

El diagrama lógico separa stream processing, scoring, profiles y case management. Desplegar cada bloque como servicio independiente consume tiempo, complejidad y crédito sin aportar valor al MVP.

## Decisión

- Stream Processor + Scoring + Policy pueden co-existir inicialmente en un Container App `fraud-engine`.
- Profiles y Cases comparten una Azure SQL Database con schemas separados.
- Se mantienen interfaces lógicas para poder dividirlos después.

## Consecuencias

Menor costo y superficie operativa, sin perder claridad arquitectónica.

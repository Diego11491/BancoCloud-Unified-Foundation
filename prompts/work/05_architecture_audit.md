# Prompt — Auditoría de coherencia arquitectónica

Audita el repositorio contra `docs/00_SOURCE_OF_TRUTH.md`.

No empieces leyendo todo. Primero revisa:
- Source of Truth;
- ADRs modificados recientemente;
- specs activas;
- `git diff` o cambios desde el último baseline.

Busca específicamente:
1. responsabilidades movidas entre AWS/on-prem/Azure;
2. servicios cloud nuevos sin ADR;
3. duplicación de contratos;
4. MEDIUM creando casos sin policy aprobada;
5. GenAI dentro del scoring;
6. labels/leakage dentro del evento;
7. secretos/PII/logs sensibles;
8. recursos Student que contradicen LITE;
9. incompatibilidad producer/consumer;
10. documentación divergente.

Clasifica hallazgos como BLOCKER, HIGH, MEDIUM, LOW.
No corrijas automáticamente un BLOCKER arquitectónico: propone el diff/ADR primero.

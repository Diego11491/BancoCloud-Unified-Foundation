# Azure Student Lite - Deployment preflight

## Estado

Completado el 29 de septiembre de 2026 sobre una suscripción Azure for Students
con rol Owner. Esta fase valida la infraestructura declarada, pero no despliega
los servicios de la arquitectura.

## Alcance validado

- Región seleccionada: `brazilsouth`.
- Resource Group: `rg-bancocloud-student-lite`.
- Sufijo de recursos: `dv260929`.
- Proveedores requeridos: registrados.
- Resource Group creado con etiquetas de proyecto, ambiente, responsable y
  expiración.
- Plantilla: `infra/azure/bicep/main-lite.bicep`.
- Validación ARM completa: `Succeeded`.
- Recursos reales después del preflight: `0`.

## Resultado de What-If

| Tipo de cambio | Cantidad | Evaluación |
| --- | ---: | --- |
| Create | 22 | Esperado |
| Unsupported | 2 | Dependencias RBAC calculadas en despliegue |
| Modify | 0 | Sin cambios destructivos |
| Delete | 0 | Sin cambios destructivos |

Los dos elementos `Unsupported` corresponden a asignaciones RBAC cuyo
identificador depende del `principalId` de la identidad administrada
`bc-workload-dv260929`. Ese valor solo existe después de crear la identidad.
La validación ARM completa sí comprobó permisos y estructura de la plantilla.

Las asignaciones afectadas son:

1. Acceso de la identidad administrada al Event Hub
   `transaction-posted-v1`.
2. Acceso de la identidad administrada al contenedor
   `eventhub-checkpoints`.

## Decisión del gate

El preflight se considera aprobado porque:

- la validación ARM terminó en `Succeeded`;
- no existen cambios `Delete` ni `Modify`;
- los únicos cambios no evaluables son dependencias de identidad conocidas;
- el Resource Group permanece sin recursos desplegados;
- no se utilizaron connection strings ni claves compartidas;
- la integración conserva Managed Identity y RBAC.

## Restricciones

- Este documento no demuestra un despliegue de producción.
- No contiene identificadores de suscripción, contraseñas ni secretos.
- No debe ejecutarse `az deployment group create` sin revisar antes el costo y
  el orden de despliegue.
- Los recursos deben eliminarse o desactivarse al terminar la evidencia de la
  demostración, respetando la etiqueta de expiración.

## Próximo gate

El corte controlado por costo ya está definido mediante feature flags en
`main-lite.bicep`. La siguiente acción es ejecutar el preflight descrito en
`08_AZURE_COST_CONTROLLED_SLICE.md` y confirmar mediante un nuevo what-if que
solo Managed Identity, Storage/Data Lake, Event Hubs y RBAC mínimo están activos.
Este documento sigue siendo evidencia del preview completo anterior; no debe
reinterpretarse como resultado del nuevo corte hasta ejecutar ese gate.

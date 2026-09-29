# Azure STUDENT LITE: preparación y despliegue por gates

## Estado

`infra/azure/bicep/messaging-lite.bicep` define Event Hubs Standard, Service Bus Standard y ADLS Gen2 Bronze/Silver/Gold con una zona lateral Quarantine privada. **No es una plantilla de la solución Azure completa**: Container App, Azure SQL, ACR, Key Vault, identidad, telemetría y adaptadores Event Hubs/Service Bus son tareas separadas. No ejecutar un despliegue creyendo que el pipeline está conectado.

El despliegue se ejecutará en dos etapas conforme a ADR-0005: primero la plataforma
sin workloads; después de construir y publicar una imagen inmutable, se despliegan
los Container Apps. `main-lite.bicep` no debe interpretarse todavía como un
despliegue end-to-end.

Quarantine recibe únicamente registros rechazados por validación antes de Silver.
La plantilla aplica una retención configurable de 1 a 90 días (30 por defecto).
Cada writer futuro debe conservar `reason_code`, referencia del input, timestamp y
versión del validador sin copiar secretos ni datos personales directos.

## Requisitos y control de costos

Suscripción académica autorizada; región con cuotas confirmadas; Azure CLI y Bicep; owner y expiry del laboratorio. Event Hubs y Service Bus generan costo aunque no haya tráfico. SQL/ACR y otros componentes también pueden persistir costo. Antes de crear recursos, registrar el presupuesto, el listado de nombres y el horario de destrucción.

## Validar antes de crear

```bash
az login
az account show --query "{name:name,id:id}" -o json
az bicep build --file infra/azure/bicep/messaging-lite.bicep
az bicep lint --file infra/azure/bicep/messaging-lite.bicep
az group create --name <grupo_demo> --location <region_confirmada> --tags project=bancocloud environment=student-lite owner=<owner> expiry=<AAAA-MM-DD>
az deployment group what-if --resource-group <grupo_demo> --template-file infra/azure/bicep/messaging-lite.bicep --parameters suffix=<sufijo_unico> owner=<owner> expiry=<AAAA-MM-DD>
```

`az group create` crea únicamente el grupo; si se exige un preview sin mutaciones de ningún tipo, usar un grupo existente. Revisar precio, SKU y restricciones regionales antes de continuar. Desplegar solamente tras cerrar Fase 2 y aprobar el `what-if`:

```bash
az deployment group create --resource-group <grupo_demo> --template-file infra/azure/bicep/messaging-lite.bicep --parameters suffix=<sufijo_unico> owner=<owner> expiry=<AAAA-MM-DD>
```

Para conectar el sistema: (1) usar una identidad adecuada para el productor Core→Event Hubs; (2) ejecutar el fraud engine en Container Apps consumiendo Event Hubs con checkpoint duradero; (3) persistir perfiles/casos en Azure SQL con schemas separados; (4) HIGH→Service Bus→case service con clave `transaction_id + policy_version`; (5) Bronze mediante consumidor ligero o Capture solo en DEMO FULL; (6) prueba de replay. Los mecanismos de identidad y conectividad deben aprobarse antes del despliegue. No copiar `.env` local a Azure ni habilitar SQL público sin un diseño de acceso.

## Verificación y cierre

Reconciliar `Bronze = Silver + Quarantine + duplicados`, forzar un registro inválido
y comprobar que no alcance Gold; después forzar reentrega de HIGH y comprobar
exactamente un caso. Verificar `correlation_id`, versiones de política/modelo y la
retención efectiva de Quarantine. Registrar recursos que queden activos. Para
eliminar un grupo **dedicado a esta demo**, revisar `az resource list -g <grupo_demo>`
y después usar `az group delete --name <grupo_demo>` cuando termine la sesión. No
eliminar grupos compartidos.

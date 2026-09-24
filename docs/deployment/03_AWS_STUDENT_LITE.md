# AWS STUDENT LITE: precondiciones del canal digital

## Componentes autorizados

Web estática S3/CloudFront, Cognito para clientes, API Gateway HTTP API y Lambda BFF. WAF se habilita en DEMO FULL si el costo y la validación lo justifican. La capa AWS nunca escribe directamente la verdad transaccional ni cambia el score Azure.

## Gate de conectividad

El core actual escucha exclusivamente en `127.0.0.1` y usa `X-Demo-Key`. **No se debe desplegar Lambda ni publicar la API hasta definir y probar una ruta segura AWS→core**, autenticación entre cargas y rate limiting. Estas decisiones físicas no están cerradas en los adjuntos; el ADR debe fijar URL de demo, terminación TLS, verificación de identidad, exposición, restricciones de origen y teardown. Exponer un puerto local o insertar claves largas en Lambda/API Gateway sería un atajo incompatible con el diseño.

## Secuencia cuando el gate esté cerrado

1. Crear spec de canal y ADR de conectividad; integrar BFF con `POST /transfers` sin saltarse el outbox.
2. Crear SAM/CloudFormation con Cognito User Pool, authorizer JWT del HTTP API y una Lambda BFF; frontend S3 privado mediante CloudFront OAC en stack separado.
3. Probar localmente contrato, authz negativa, idempotencia y propagación de `correlation_id`.
4. Ejecutar `sam validate --lint` y `sam build`; revisar el change set antes de `sam deploy`.
5. Registrar costos persistentes, hacer smoke end-to-end y borrar stacks demo al terminar.

No hay stack AWS ni endpoint público en este paquete. Su creación antes de cerrar el gate convertiría instrucciones en una promesa funcional falsa.

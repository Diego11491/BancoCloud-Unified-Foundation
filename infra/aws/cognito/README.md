# BancoCloud Cognito DEV Infrastructure

## Purpose
This stack deploys an isolated Amazon Cognito environment tailored for local development of the BancoCloud Mobile app and the SAM BFF.
It provisions the User Pool, the Public Mobile App Client (with PKCE Authorization Code flow), and a Cognito Managed Login domain.

## Deployment Command (FUTURE PHASE)
Do not deploy yet. In a future authorized phase, deployment will be done using the AWS CLI or SAM CLI against the target region (`us-east-1`):

```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name bancocloud-cognito-dev \
  --parameter-overrides DomainPrefix="bancocloud-auth-dev-${RANDOM}"
```

## Creating the Demo User

DO NOT EXECUTE THIS SECTION UNTIL:
- Cognito DEV stack has been deployed
- UserPoolId has been obtained from CloudFormation Outputs
- the demo username has been chosen
- AUTH-03D has been explicitly authorized

In a future authorized phase, the Demo User must be created administratively to assign the immutable `custom:customer_ref` claim required by the BFF backend. Do not allow Mobile to provide this ID.

Ensure you provide a strong password interactively or via an environment variable to avoid shell history leaks.

Example conceptual assignment (placeholders MUST be replaced with actual runtime values after AUTH-03C deployment):

```powershell
$UserPoolId = "<OUTPUT_FROM_DEPLOYED_COGNITO_STACK>"
$Username   = "<DEV_USERNAME>"
$env:BANCOCLOUD_DEMO_TEMP_PASSWORD = Read-Host "Temporary Cognito password" -MaskInput

aws cognito-idp admin-create-user \
  --user-pool-id $UserPoolId \
  --username $Username \
  --user-attributes Name="custom:customer_ref",Value="007796d7-43a4-50c7-8093-1a7caf001771" Name="email",Value=$Username \
  --temporary-password $env:BANCOCLOUD_DEMO_TEMP_PASSWORD \
  --message-action SUPPRESS

# Clean up variables
Remove-Item Env:\BANCOCLOUD_DEMO_TEMP_PASSWORD
```

The first login strategy uses a `TEMPORARY_PASSWORD` flow. When using `AdminCreateUser` with a temporary password, the user will be prompted with a `NEW_PASSWORD_REQUIRED` flow (first-login password-change) by Managed Login. Only after this flow is completed is the user fully usable.

Alternatively, for a deterministic DEV account without interactive first-time setup, the password can be set permanently using:
```powershell
aws cognito-idp admin-set-user-password \
  --user-pool-id $UserPoolId \
  --username $Username \
  --password $env:BANCOCLOUD_DEMO_PERM_PASSWORD \
  --permanent
```

## Outputs
After deployment, configure the environment variables using the CloudFormation outputs:
- `UserPoolId`: Maps to `EXPO_PUBLIC_COGNITO_USER_POOL_ID`
- `UserPoolClientId`: Maps to `EXPO_PUBLIC_COGNITO_APP_CLIENT_ID`
- `CognitoRegion`: Maps to `EXPO_PUBLIC_COGNITO_REGION`
- `CognitoIssuer`: Maps to `COGNITO_ISSUER` (BFF)
- `CognitoDomain`: Maps to `EXPO_PUBLIC_COGNITO_DOMAIN`

## Teardown Implications
The User Pool has been configured with `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain`. Deleting the CloudFormation stack will intentionally leave the User Pool intact to prevent the accidental loss of development identity state (users). To fully clean up the environment, the User Pool and Cognito Domain must be explicitly deleted via the AWS Console or AWS CLI after the stack is destroyed.

## Cost Caveats
**EXPECTED_WITHIN_FREE_TIER_WITH_NONZERO_RISK**
For current eligible Cognito Lite/Essentials usage, the applicable free-tier allowance is currently 10,000 MAU, subject to AWS account, tier and pricing conditions.

Development usage is expected to remain low, but non-zero AWS cost risk exists.

Additional services such as SMS, SES, Lambda triggers or other AWS resources may incur separate charges if enabled.

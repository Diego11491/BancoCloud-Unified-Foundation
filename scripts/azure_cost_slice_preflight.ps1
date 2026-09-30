[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ResourceGroup,

    [Parameter(Mandatory)]
    [string]$Location,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]{6,12}$')]
    [string]$Suffix,

    [Parameter(Mandatory)]
    [ValidateLength(2, 64)]
    [string]$Owner,

    [Parameter(Mandatory)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$Expiry,

    [string]$LocalIntegrationPrincipalId = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-NativeSuccess {
    param([Parameter(Mandatory)][string]$Operation)

    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

function ConvertFrom-AzJson {
    param([Parameter(Mandatory)][object[]]$Lines)

    $raw = $Lines -join [Environment]::NewLine

    try {
        return $raw | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        $start = $raw.IndexOf('{')
        $end = $raw.LastIndexOf('}')

        if ($start -lt 0 -or $end -le $start) {
            throw 'Azure CLI did not return a JSON document.'
        }

        return $raw.Substring($start, $end - $start + 1) |
            ConvertFrom-Json -ErrorAction Stop
    }
}

if ($null -eq (Get-Command az -ErrorAction SilentlyContinue)) {
    throw 'Azure CLI is required.'
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$template = Join-Path $repositoryRoot 'infra\azure\bicep\main-lite.bicep'
$tempDirectory = Join-Path (
    [System.IO.Path]::GetTempPath()
) "bancocloud-cost-slice-$([guid]::NewGuid().ToString('N'))"
$compiledTemplate = Join-Path $tempDirectory 'main-lite.json'

$deploymentParameters = @(
    "suffix=$Suffix",
    "location=$Location",
    "owner=$Owner",
    "expiry=$Expiry",
    'deployEventStreaming=true',
    'deployDataLake=true',
    'deploySql=false',
    'deployServiceBus=false',
    'deployObservability=false',
    'deployContainerRegistry=false',
    'deployKeyVault=false',
    "localIntegrationPrincipalId=$LocalIntegrationPrincipalId"
)

try {
    New-Item -ItemType Directory -Path $tempDirectory -Force | Out-Null

    $account = ConvertFrom-AzJson @(
        & az account show --output json
    )
    Assert-NativeSuccess 'Azure account lookup'

    if ($account.state -ne 'Enabled') {
        throw 'The active Azure subscription is not enabled.'
    }

    $signedInObjectId = & az ad signed-in-user show --query id --output tsv
    Assert-NativeSuccess 'Signed-in user lookup'

    $subscriptionScope = "/subscriptions/$($account.id)"
    $effectiveRoles = @(
        & az role assignment list `
            --assignee-object-id $signedInObjectId `
            --scope $subscriptionScope `
            --include-inherited `
            --include-groups `
            --fill-principal-name false `
            --query '[].roleDefinitionName' `
            --output tsv |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    Assert-NativeSuccess 'Subscription role lookup'

    if ($effectiveRoles -notcontains 'Owner') {
        throw 'The active subscription is not the verified Owner subscription.'
    }

    $requiredProviders = @(
        'Microsoft.ManagedIdentity',
        'Microsoft.EventHub',
        'Microsoft.Storage',
        'Microsoft.Authorization'
    )

    foreach ($provider in $requiredProviders) {
        $providerState = & az provider show `
            --namespace $provider `
            --query registrationState `
            --output tsv
        Assert-NativeSuccess "Provider lookup: $provider"

        if ($providerState.Trim() -ne 'Registered') {
            throw "Required provider $provider is not registered."
        }
    }

    $groupExists = & az group exists --name $ResourceGroup --output tsv
    Assert-NativeSuccess 'Resource Group lookup'

    if ($groupExists.Trim().ToLowerInvariant() -ne 'true') {
        throw "Resource Group $ResourceGroup does not exist."
    }

    $groupLocation = & az group show `
        --name $ResourceGroup `
        --query location `
        --output tsv
    Assert-NativeSuccess 'Resource Group location lookup'

    if ($groupLocation.Trim().ToLowerInvariant() -ne $Location.ToLowerInvariant()) {
        throw "Resource Group location is $groupLocation, not $Location."
    }

    $resourceIds = @(
        & az resource list `
            --resource-group $ResourceGroup `
            --query '[].id' `
            --output tsv |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    Assert-NativeSuccess 'Resource inventory'

    if ($resourceIds.Count -ne 0) {
        throw 'The preflight requires an empty dedicated Resource Group.'
    }

    & az bicep lint --file $template --no-restore
    Assert-NativeSuccess 'Bicep lint'

    & az bicep build `
        --file $template `
        --outfile $compiledTemplate `
        --no-restore
    Assert-NativeSuccess 'Bicep build'

    $validateArgs = @(
        'deployment', 'group', 'validate',
        '--name', 'bancocloud-cost-slice-validation',
        '--resource-group', $ResourceGroup,
        '--template-file', $template,
        '--parameters'
    ) + $deploymentParameters + @('--output', 'json')

    $validation = ConvertFrom-AzJson @(& az @validateArgs)
    Assert-NativeSuccess 'ARM validation'

    if ($validation.properties.provisioningState -ne 'Succeeded') {
        throw 'ARM validation did not reach Succeeded.'
    }

    $whatIfArgs = @(
        'deployment', 'group', 'what-if',
        '--name', 'bancocloud-cost-slice-whatif',
        '--resource-group', $ResourceGroup,
        '--template-file', $template,
        '--parameters'
    ) + $deploymentParameters + @(
        '--result-format', 'ResourceIdOnly',
        '--no-pretty-print',
        '--output', 'json'
    )

    $whatIf = ConvertFrom-AzJson @(& az @whatIfArgs)
    Assert-NativeSuccess 'ARM what-if'

    $changes = if ($whatIf.PSObject.Properties.Name -contains 'changes') {
        @($whatIf.changes)
    }
    elseif (
        $whatIf.PSObject.Properties.Name -contains 'properties' -and
        $whatIf.properties.PSObject.Properties.Name -contains 'changes'
    ) {
        @($whatIf.properties.changes)
    }
    else {
        @()
    }

    if ($changes.Count -eq 0) {
        throw 'What-if returned no changes for an empty Resource Group.'
    }

    $destructive = @(
        $changes |
        Where-Object { $_.changeType -in @('Delete', 'Modify') }
    )

    if ($destructive.Count -gt 0) {
        throw 'What-if contains Delete or Modify changes.'
    }

    $forbiddenFragments = @(
        '/providers/Microsoft.Sql/',
        '/providers/Microsoft.ServiceBus/',
        '/providers/Microsoft.ContainerRegistry/',
        '/providers/Microsoft.OperationalInsights/',
        '/providers/Microsoft.Insights/',
        '/providers/Microsoft.KeyVault/'
    )

    $forbidden = @(
        $changes |
        Where-Object {
            $resourceId = [string]$_.resourceId
            @(
                $forbiddenFragments |
                Where-Object {
                    $resourceId.IndexOf(
                        $_,
                        [System.StringComparison]::OrdinalIgnoreCase
                    ) -ge 0
                }
            ).Count -gt 0
        }
    )

    if ($forbidden.Count -gt 0) {
        $forbidden |
            Select-Object changeType, resourceId |
            Format-Table -Wrap -AutoSize
        throw 'The cost slice contains a disabled resource type.'
    }

    $requiredFragments = @(
        '/providers/Microsoft.ManagedIdentity/',
        '/providers/Microsoft.EventHub/',
        '/providers/Microsoft.Storage/'
    )

    foreach ($fragment in $requiredFragments) {
        $matchingChanges = @(
            $changes |
            Where-Object {
                ([string]$_.resourceId).IndexOf(
                    $fragment,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0
            }
        )

        if ($matchingChanges.Count -eq 0) {
            throw "What-if is missing required resource family $fragment."
        }
    }

    $unsupportedOutsideRbac = @(
        $changes |
        Where-Object {
            $_.changeType -eq 'Unsupported' -and
            ([string]$_.resourceId) -notmatch 'Microsoft.Authorization/roleAssignments'
        }
    )

    if ($unsupportedOutsideRbac.Count -gt 0) {
        throw 'What-if contains an unsupported change outside known RBAC dependencies.'
    }

    $resourcesAfterWhatIf = @(
        & az resource list `
            --resource-group $ResourceGroup `
            --query '[].id' `
            --output tsv |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    Assert-NativeSuccess 'Post-what-if resource inventory'

    if ($resourcesAfterWhatIf.Count -ne 0) {
        throw 'Resources appeared in the group during a non-deploying preflight.'
    }

    Write-Host "`n=== AZURE COST-CONTROLLED SLICE ==="
    $changes |
        Group-Object changeType |
        Sort-Object Name |
        Select-Object `
            @{Name='ChangeType';Expression={$_.Name}},
            @{Name='Count';Expression={$_.Count}} |
        Format-Table -AutoSize

    Write-Host 'ARM validation: PASS'
    Write-Host 'Delete/Modify: 0'
    Write-Host 'SQL/Service Bus/ACR/Observability/Key Vault: DISABLED'
    Write-Host 'Resources deployed by preflight: 0'
    Write-Host 'T5-AZURE-COST-CONTROLLED-SLICE PREFLIGHT: PASS'
}
finally {
    if (Test-Path -LiteralPath $tempDirectory) {
        Remove-Item -LiteralPath $tempDirectory -Recurse -Force
    }
}

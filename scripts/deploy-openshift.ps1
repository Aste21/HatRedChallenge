# Deploy the current local sources to the Autonomous CFO hackathon cluster.
[CmdletBinding(SupportsShouldProcess)]
param([hashtable]$BuildVersions)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = Split-Path $PSScriptRoot -Parent
$manifests = Join-Path $repo 'deploy/cfo'
$buildScript = Join-Path $PSScriptRoot 'build-openshift.ps1'
$acceptance = Join-Path $PSScriptRoot 'evaluate-cfo.py'
$namespace = 'cfo-ai'

function Invoke-Oc {
    & oc @args
    if ($LASTEXITCODE -ne 0) { throw "oc $($args -join ' ') failed (exit $LASTEXITCODE)" }
}

Get-Command oc, git, tar.exe -CommandType Application -ErrorAction Stop | Out-Null
$server = Invoke-Oc whoami --show-server
$identity = Invoke-Oc whoami
Write-Host "Cluster $server | user $identity | project $namespace"

$components = @('backend','instruments','frontend')
if (-not $PSCmdlet.ShouldProcess("$server ($namespace)", 'Build and deploy the three CFO components, then run acceptance')) {
    Invoke-Oc create --dry-run=client -o name -f (Join-Path $manifests 'builds.yaml') `
        -f (Join-Path $manifests 'backend.yaml') -f (Join-Path $manifests 'instruments.yaml') `
        -f (Join-Path $manifests 'frontend.yaml') -f (Join-Path $manifests 'access.yaml') `
        -f (Join-Path $manifests 'network.yaml') -f (Join-Path $manifests 'app-session-template.yaml')
    return
}

$project = Invoke-Oc get namespace $namespace --ignore-not-found -o name
if (-not $project) {
    "apiVersion: v1`nkind: Namespace`nmetadata:`n  name: cfo-ai`n  labels:`n    opendatahub.io/dashboard: 'true'" | oc apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the CFO project' }
}

Invoke-Oc apply -f (Join-Path $manifests 'builds.yaml')
$images = @{}
foreach ($component in $components) {
    if ($BuildVersions) {
        $version = $BuildVersions[$component]
        if ("$version" -notmatch '^[1-9][0-9]*$') { throw "Missing build number for $component" }
        $build = Invoke-Oc get "build/cfo-$component-$version" -n $namespace -o json | Out-String | ConvertFrom-Json
        $digest = $build.status.output.to.imageDigest
        if ($build.status.phase -ne 'Complete' -or $digest -notmatch '^sha256:[a-f0-9]{64}$' -or
            $build.spec.output.to.name -ne "cfo-${component}:release") {
            throw "Invalid release build for $component"
        }
        $images[$component] = "image-registry.openshift-image-registry.svc:5000/$namespace/cfo-$component@$digest"
        continue
    }
    Write-Host "Building cfo-$component"
    $options = @{ Component = $component; WaitForImage = $true }
    if ($component -eq 'instruments') { $options.BackendImage = $images.backend }
    $images[$component] = & $buildScript @options
}

Invoke-Oc apply -f (Join-Path $manifests 'access.yaml') -f (Join-Path $manifests 'network.yaml')
$cookie = Invoke-Oc get secret cfo-app-session -n $namespace --ignore-not-found -o name
if (-not $cookie) {
    $generated = Invoke-Oc process --local -f (Join-Path $manifests 'app-session-template.yaml') -o json
    $generated | oc create -n $namespace -f -
    $createFailed = $LASTEXITCODE -ne 0
    Remove-Variable generated
    if ($createFailed -and -not (Invoke-Oc get secret cfo-app-session -n $namespace --ignore-not-found -o name)) {
        throw 'Application session secret creation failed'
    }
}

# Kustomize replaces mutable image tags with this run's digests before the first rollout.
# Hashing the manifest containing the ConfigMap also reloads environment variables on updates.
$scratch = Join-Path ([IO.Path]::GetTempPath()) ("cfo-release-" + [guid]::NewGuid())
$null = New-Item -ItemType Directory -Path $scratch
$files = @('backend.yaml','instruments.yaml','frontend.yaml')
try {
    foreach ($file in $files) {
        Copy-Item -LiteralPath (Join-Path $manifests $file) -Destination $scratch
    }
    $spec = @{
        apiVersion = 'kustomize.config.k8s.io/v1beta1'
        kind = 'Kustomization'
        resources = @('backend.yaml', 'instruments.yaml')
        commonAnnotations = @{ 'cfo/config-sha256' = (Get-FileHash (Join-Path $scratch 'backend.yaml')).Hash }
        images = @(foreach ($component in $components) {
            $name, $digest = $images[$component] -split '@', 2
            @{ name = $name; digest = $digest }
        })
    }
    [IO.File]::WriteAllText((Join-Path $scratch 'kustomization.yaml'), ($spec | ConvertTo-Json -Depth 6))
    Invoke-Oc apply -n $namespace -k $scratch
    foreach ($component in @('backend','instruments')) {
        Invoke-Oc rollout status "deployment/cfo-$component" -n $namespace --timeout=10m
    }
    # The public landing must only reach the account-aware backend and its separate demo database.
    $spec.resources = @('frontend.yaml')
    [IO.File]::WriteAllText((Join-Path $scratch 'kustomization.yaml'), ($spec | ConvertTo-Json -Depth 6))
    Invoke-Oc apply -n $namespace -k $scratch
} finally {
    foreach ($file in ($files + 'kustomization.yaml')) {
        $path = Join-Path $scratch $file
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
    Remove-Item -LiteralPath $scratch
}
Invoke-Oc rollout status deployment/cfo-frontend -n $namespace --timeout=10m
Invoke-Oc wait '--for=jsonpath={.status.ingress[0].conditions[0].status}=True' route/autonomous-cfo -n $namespace --timeout=2m
$routeHost = Invoke-Oc get route autonomous-cfo -n $namespace -o 'jsonpath={.spec.host}'
Write-Host "CFO application: https://$routeHost/"

Get-Content -Raw -Encoding UTF8 -LiteralPath $acceptance | oc exec -i -n $namespace deploy/cfo-backend -- python -
if ($LASTEXITCODE -ne 0) { throw 'CFO acceptance failed. Review the preceding results and the MLflow run.' }
Write-Host 'CFO deployment and acceptance completed.'

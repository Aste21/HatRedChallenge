[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('frontend','backend','instruments')][string]$Component,
    [switch]$WaitForImage,
    [ValidatePattern('^image-registry\.openshift-image-registry\.svc:5000/cfo-ai/cfo-backend@sha256:[a-f0-9]{64}$')]
    [string]$BackendImage
)
$ErrorActionPreference = 'Stop'
if ($BackendImage -and $Component -ne 'instruments') { throw 'Only instruments inherits the backend image.' }
$repo = Split-Path $PSScriptRoot -Parent
$sourceDir = if ($Component -eq 'instruments') { 'instrument_recommendation_agent' } else { $Component }
$dir = Join-Path $repo $sourceDir
$scratch = Join-Path ([IO.Path]::GetTempPath()) ("cfo-" + [guid]::NewGuid())
$archive = Join-Path $scratch 'sources.tar.gz'
$instrumentDockerfile = Join-Path $scratch 'Dockerfile.openshift'
# Only ship application sources, including uncommitted local edits.
switch ($Component) {
    backend {
        $files = @('Dockerfile','pyproject.toml')
        $paths = @('app/*.py','app/knowledge/*/company_knowledge.md')
    }
    instruments {
        $files = @('requirements.txt')
        $paths = @('app/*.py')
    }
    frontend {
        $files = @('Dockerfile','package.json','package-lock.json','.npmrc','tsconfig.json','vite.config.ts')
        $paths = @('src','static')
    }
}
$listed = git -c core.quotepath=false -C $dir ls-files --cached --others --exclude-standard -- @paths
if ($LASTEXITCODE -ne 0) { throw 'Could not enumerate application sources' }
$files += @($listed | Where-Object { Test-Path -LiteralPath (Join-Path $dir $_) -PathType Leaf })
$null = New-Item -ItemType Directory -Path $scratch
try {
    $tarArgs = @('-czf', $archive, '-C', $dir) + $files
    if ($Component -eq 'instruments') {
        $dockerfile = Get-Content -LiteralPath (Join-Path $dir 'Dockerfile.openshift') -Raw
        if (-not $BackendImage) {
            $digest = oc get imagestreamtag cfo-backend:release -n cfo-ai -o 'jsonpath={.image.metadata.name}'
            if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^sha256:[a-f0-9]{64}$') {
                throw 'Build the release backend first or pass -BackendImage'
            }
            $BackendImage = "image-registry.openshift-image-registry.svc:5000/cfo-ai/cfo-backend@$digest"
        }
        $base = 'FROM image-registry.openshift-image-registry.svc:5000/cfo-ai/cfo-backend:release'
        if (-not $dockerfile.StartsWith($base + "`n") -and -not $dockerfile.StartsWith($base + "`r`n")) {
            throw 'The instrument Dockerfile has an unexpected base image'
        }
        $dockerfile = $dockerfile.Replace($base, "FROM $BackendImage")
        [IO.File]::WriteAllText($instrumentDockerfile, $dockerfile, [Text.UTF8Encoding]::new($false))
        $tarArgs += @('-C', $scratch, 'Dockerfile.openshift')
    }
    & tar.exe @tarArgs
    if ($LASTEXITCODE -ne 0) { throw 'Build archive failed' }

    $startArgs = @('start-build', "cfo-$Component", '-n', 'cfo-ai', "--from-archive=$archive")
    if ($WaitForImage) { $startArgs += @('--wait','-o','name') }
    $build = & oc @startArgs
    if ($LASTEXITCODE -ne 0) { throw "OpenShift build failed for cfo-$Component. $build" }
    if (-not $WaitForImage) { return $build }

    $imageDigest = oc get $build -n cfo-ai -o 'jsonpath={.status.output.to.imageDigest}'
    if ($LASTEXITCODE -ne 0 -or $imageDigest -notmatch '^sha256:[a-f0-9]{64}$') {
        throw "No published image digest for $build"
    }
    Write-Host "$build completed"
    return "image-registry.openshift-image-registry.svc:5000/cfo-ai/cfo-${Component}@$imageDigest"
} finally {
    foreach ($file in @($archive, $instrumentDockerfile, $scratch)) {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    }
}

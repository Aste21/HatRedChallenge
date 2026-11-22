# Reopen an approved proposal on the shared Amalfi demo account.
[CmdletBinding()]
param([string]$ProposalId, [switch]$Preview)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$mode = if ($Preview) { 'preview' } else { 'reset' }
$arguments = @('exec', '-i', '-n', 'cfo-ai', 'deployment/cfo-backend', '-c', 'backend', '--', 'python', '-', $mode)
if ($ProposalId) { $arguments += $ProposalId }
Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'reset-demo-approval.py') | oc @arguments
if ($LASTEXITCODE -ne 0) { throw "Demo approval $mode failed (oc exit $LASTEXITCODE)." }

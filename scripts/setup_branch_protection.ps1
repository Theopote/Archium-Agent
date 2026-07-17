# Configure branch protection on master (requires gh CLI + repo admin).
$ErrorActionPreference = "Stop"

$Repo = if ($env:ARCHIUM_GITHUB_REPO) { $env:ARCHIUM_GITHUB_REPO } else { "Theopote/Archium-Agent" }
$Branch = if ($env:ARCHIUM_PROTECTED_BRANCH) { $env:ARCHIUM_PROTECTED_BRANCH } else { "master" }
$ChecksRaw = if ($env:ARCHIUM_CI_CHECKS) { $env:ARCHIUM_CI_CHECKS } else { "test (3.11),test (3.12)" }

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "gh CLI not found. Install from https://cli.github.com/ or use docs/branch-protection.md (Web UI)."
}

$contexts = @($ChecksRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })

$payload = @{
    required_status_checks = @{
        strict   = $true
        contexts = $contexts
    }
    enforce_admins                    = $true
    required_pull_request_reviews     = $null
    restrictions                      = $null
    required_linear_history           = $false
    allow_force_pushes                = $false
    allow_deletions                   = $false
    block_creations                   = $false
    required_conversation_resolution  = $false
} | ConvertTo-Json -Depth 5 -Compress

Write-Host "Applying branch protection to ${Repo}:${Branch}"
Write-Host "Required checks: $($contexts -join ', ')"

$payload | gh api "repos/$Repo/branches/$Branch/protection" -X PUT --input -

Write-Host "Done. Verify at: https://github.com/$Repo/settings/branches"

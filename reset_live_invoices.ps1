<#
.SYNOPSIS
    Convenience wrapper to reset LIVE_UPLOAD invoices in PayFlow AI.
.DESCRIPTION
    Runs backend/scripts/reset_live_invoices.py inside the running backend Docker container.
    By default runs a dry-run preview.
.PARAMETER Execute
    Switches from preview to execution mode.
.PARAMETER Confirm
    Must equal 'DELETE_ALL_LIVE_UPLOADS' to proceed with execution.
.EXAMPLE
    .\reset_live_invoices.ps1
    (Displays dry run preview)
.EXAMPLE
    .\reset_live_invoices.ps1 -Execute -Confirm DELETE_ALL_LIVE_UPLOADS
    (Performs backup and safely deletes all LIVE_UPLOAD records)
#>
[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$Confirm = ""
)

$argsList = @("exec", "payflow-ai-backend-1", "python", "scripts/reset_live_invoices.py")
if ($Execute) {
    $argsList += "--execute"
    $argsList += "--confirm"
    $argsList += $Confirm
}

& docker $argsList


$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$hostEntry = "127.0.0.54 api.notifyr.io dashboard.notifyr.io notifyr.io"
$comment = "# Added for Notifyr testing"

$hostsContent = Get-Content -Path $hostsFile

if ($hostsContent -notmatch "127\.0\.0\.54") {
    # Append comment and entry
    Add-Content -Path $hostsFile -Value $comment
    Add-Content -Path $hostsFile -Value $hostEntry
    Write-Output "Hosts file updated."
} else {
    Write-Output "Entry already exists in hosts file."
}

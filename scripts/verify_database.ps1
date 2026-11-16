param(
  [string]$Service = "postgres",
  [string]$ComposeProject = "dockyarddemo"
)
$ErrorActionPreference = 'Stop'
docker compose -p $ComposeProject ps $Service | Out-Host
$complete = $false
for ($attempt = 1; $attempt -le 90; $attempt++) {
  $loaded = docker compose -p $ComposeProject exec -T $Service psql -At -U logistics -d logistics -c "SELECT count(*) FROM resource_utilization_metrics;"
  if ($loaded.Trim() -eq '10') { $complete = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $complete) { throw "Baseline initialization did not complete within 180 seconds." }
docker compose -p $ComposeProject exec -T $Service psql -v ON_ERROR_STOP=1 -U logistics -d logistics -f /workspace/database/verify.sql

$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\.."
$Build = Join-Path $Root "build\lambda"
$Dist = Join-Path $Root "dist"

Remove-Item $Build -Recurse -Force -ErrorAction SilentlyContinue
New-Item $Build -ItemType Directory -Force | Out-Null
New-Item $Dist -ItemType Directory -Force | Out-Null

python -m pip install `
    "boto3>=1.35,<2" "fastapi>=0.115,<1" "mangum>=0.19,<1" `
    "pydantic>=2.10,<3" "pydantic-settings>=2.6,<3" `
    "psycopg[binary,pool]>=3.2,<4" `
    --target $Build --upgrade
Copy-Item "$Root\app" $Build -Recurse
Copy-Item "$Root\db" $Build -Recurse
Copy-Item "$Root\lambda_function.py" $Build
Copy-Item "$Root\lambda_api.py" $Build

$Zip = Join-Path $Dist "lambda.zip"
Remove-Item $Zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$Build\*" -DestinationPath $Zip
Write-Host "Created $Zip"

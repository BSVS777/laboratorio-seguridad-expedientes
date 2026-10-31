# Ejecuta TODO: pruebas unitarias + servidor + pruebas de API + resumen.
# Uso (desde esta carpeta):  powershell -ExecutionPolicy Bypass -File .\ejecutar_todo.ps1
Set-Location $PSScriptRoot
$log = New-Object System.Collections.Generic.List[string]
function Escribir($Texto, $Color) {
    $log.Add($Texto)
    if ($Color) { Write-Host $Texto -ForegroundColor $Color } else { Write-Host $Texto }
}
$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { Write-Host "No se encontro Python"; exit 1 }

Escribir "`n=== 1) PRUEBAS UNITARIAS ===" "Cyan"
# unittest escribe en stderr: se mezcla con stdout para que quede en la evidencia.
$salidaUnit = @(& $py -m unittest discover -s tests -v 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } })
$unitOk = ($LASTEXITCODE -eq 0)
foreach ($linea in $salidaUnit) { Escribir $linea "" }

Escribir "`n=== 2) PRUEBAS DE API (127.0.0.1:8765) ===" "Cyan"
$srv = Start-Process $py -ArgumentList "servidor.py" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2

function Llamar($Metodo, $Ruta, $Token, $Cuerpo) {
    $a = @("-s", "-w", "`n%{http_code}", "-X", $Metodo)
    if ($Token) { $a += @("-H", "Authorization: Bearer $Token") }
    if ($Cuerpo) {
        $tmp = [IO.Path]::GetTempFileName()
        [IO.File]::WriteAllText($tmp, $Cuerpo, (New-Object Text.UTF8Encoding $false))
        $a += @("-H", "Content-Type: application/json", "--data-binary", "@$tmp")
    }
    $a += "http://127.0.0.1:8765$Ruta"
    $salida = @(& curl.exe @a)
    $codigo = [int]$salida[-1]
    $texto = if ($salida.Count -gt 1) { ($salida[0..($salida.Count - 2)] -join "`n") } else { "" }
    [pscustomobject]@{ Codigo = $codigo; Cuerpo = $texto }
}

# Descripcion, metodo, ruta, token, cuerpo, codigo esperado, texto que NO debe aparecer
$casos = @(
    @("Salud",                                   "GET",  "/health",                "",           "",              200, ""),
    @("Ana lee su expediente",                   "GET",  "/expedientes/101",       "lab-ana",    "",              200, ""),
    @("Ana NO lee expediente de Luis",           "GET",  "/expedientes/202",       "lab-ana",    "",              403, "nota"),
    @("Sin token",                               "GET",  "/expedientes/101",       "",           "",              401, "nota"),
    @("Sesion expirada",                         "GET",  "/expedientes/101",       "lab-vencida","",              401, "nota"),
    @("Admin lee otra sede",                     "GET",  "/expedientes/202",       "lab-admin",  "",              200, ""),
    @("Expediente inexistente",                  "GET",  "/expedientes/999",       "lab-ana",    "",              404, "nota"),
    @("Maria cambia nota en su sede",            "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":85}',   200, ""),
    @("Maria NO cambia nota de Pacifico",        "POST", "/expedientes/202/nota",  "lab-maria",  '{"nota":10}',   403, "nota"),
    @("Admin NO cambia notas",                   "POST", "/expedientes/101/nota",  "lab-admin",  '{"nota":50}',   403, ""),
    @("Estudiante NO cambia notas",              "POST", "/expedientes/101/nota",  "lab-ana",    '{"nota":100}',  403, ""),
    @("Nota 101 rechazada",                      "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":101}',  400, ""),
    @("Nota -1 rechazada",                       "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":-1}',   400, ""),
    @("Nota texto rechazada",                    "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":"99"}', 400, ""),
    @("Nota true rechazada",                     "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":true}', 400, ""),
    @("JSON invalido",                           "POST", "/expedientes/101/nota",  "lab-maria",  '{nota:',        400, ""),
    @("Frontera 0 aceptada",                     "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":0}',    200, ""),
    @("Frontera 100 aceptada",                   "POST", "/expedientes/101/nota",  "lab-maria",  '{"nota":100}',  200, ""),
    @("Ana revoca su sesion",                    "POST", "/sesiones/revocar",      "lab-ana",    "",              200, ""),
    @("Ana ya no lee (sesion revocada)",         "GET",  "/expedientes/101",       "lab-ana",    "",              401, "nota")
)

$fallos = 0
try {
    foreach ($c in $casos) {
        $r = Llamar $c[1] $c[2] $c[3] $c[4]
        $ok = ($r.Codigo -eq $c[5]) -and ((-not $c[6]) -or ($r.Cuerpo -notmatch $c[6]))
        if (-not $ok) { $fallos++ }
        $color = if ($ok) { "Green" } else { "Red" }
        $estado = if ($ok) { "OK  " } else { "FALLO" }
        Escribir ("[{0}] {1,-38} esperado {2} obtenido {3}" -f $estado, $c[0], $c[5], $r.Codigo) $color
    }
} finally {
    if ($srv -and -not $srv.HasExited) { Stop-Process -Id $srv.Id -Force }
}

Escribir "`n=== RESUMEN ===" "Cyan"
Escribir ("Pruebas unitarias: {0}" -f $(if ($unitOk) { "OK" } else { "CON FALLOS" })) ""
Escribir ("Pruebas de API:    {0} de {1} correctas" -f ($casos.Count - $fallos), $casos.Count) ""

# Evidencia reproducible en UTF-8 (sin BOM).
[IO.File]::WriteAllLines((Join-Path $PSScriptRoot "evidencia.txt"), $log, (New-Object Text.UTF8Encoding $false))
if (-not $unitOk -or $fallos -gt 0) { exit 1 }

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/..").Path
$taskHome = Join-Path $root 'private/compiler-ghidra-home'
$out = Join-Path $root 'artifacts/experiments/COMPILER-20261101'
$ghidra = 'C:/Tools/ghidra_12.2_PUBLIC'
$java = 'C:/Program Files/Eclipse Adoptium/jdk-25.0.4.101-hotspot/bin/java.exe'
foreach ($entry in @(@('main','1000:409c','0x6000'),@('open','1000:1e48','0x800'))) {
    & $java '-Djava.system.class.loader=ghidra.GhidraClassLoader' "-Duser.home=$taskHome" "-Dapplication.settingsdir=$taskHome/settings" "-Dapplication.cachedir=$taskHome/cache" "-Dapplication.tempdir=$taskHome/tmp" -cp "$ghidra/Ghidra/Framework/Utility/lib/Utility.jar" ghidra.Ghidra ghidra.app.util.headless.AnalyzeHeadless "$root/private/ghidra-projects" OperationEurope -process "$($entry[0]).exe" -readOnly -noanalysis -scriptPath "$root/scripts/ghidra" -postScript InspectOeStartup.java "$out/$($entry[0])-startup.tsv" $entry[1] $entry[2] *> "$out/$($entry[0])-ghidra.log"
    if ($LASTEXITCODE -ne 0) { throw "Ghidra failed: $($entry[0])" }
}

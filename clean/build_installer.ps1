$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"

$dataArgs = @(
  "--add-data=$((Join-Path $root 'freecad_hid_udp_bridge.py'));.",
  "--add-data=$((Join-Path $root 'freecad_udp_orbit_autostart.py'));.",
  "--add-data=$((Join-Path $root 'freecad_udp_orbit_macro.py'));."
)

$calib = Join-Path $projectRoot "tools\freecad_hid_calibration.json"
if (Test-Path $calib) {
  $dataArgs += "--add-data=$calib;."
}

py -m pip install pyinstaller
py -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name joystick_mani_installer `
  --distpath $distDir `
  --workpath $buildDir `
  --hidden-import hid `
  --collect-all hid `
  @dataArgs `
  (Join-Path $root "installer.py")

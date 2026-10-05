<#
.SYNOPSIS
    Screenshot a single window by its Win32 HWND and write it to a PNG file.

.DESCRIPTION
    Called from a capture harness inside VFP, e.g.
        loShell = CREATEOBJECT("WScript.Shell")
        loShell.Run('powershell.exe -NoProfile -ExecutionPolicy Bypass -File Snap-Window.ps1 ' ;
            + '-Hwnd ' + TRANSFORM(oForm.HWnd) + ' -OutFile "x.png"', 0, .T.)

    PrintWindow with PW_RENDERFULLCONTENT (DWM-composed windows, including VFP
    forms and the frame of a top-level window); if that returns a single flat
    colour, falls back to copying the window's rectangle from the screen.

    -Root      capture the top-level window that owns the HWND. VFP's
               _SCREEN.HWnd is the MDI client, which leaves out the title bar,
               menu bar, and docked toolbars; -Root takes the whole frame.
    -Activate  restore and bring the window to the foreground first (the
               original behaviour). Off by default: a harness running inside the
               app already has the window on top, and activating a child form
               from outside runs the app's Activate code a second time.

.NOTES
    The calling thread is made DPI-unaware before any window call, so a
    DPI-unaware target (VFP 9) is measured and printed at its own pixel size
    rather than the DWM-scaled size (learned on a 200% desktop, Tastrade 2026-09).
    Requires Windows 10 1607+ for SetThreadDpiAwarenessContext and
    PW_RENDERFULLCONTENT; on older Windows drop the flag value from 2 to 0.
#>
param(
    [Parameter(Mandatory = $true)] [long]   $Hwnd,
    [Parameter(Mandatory = $true)] [string] $OutFile,
    [switch] $Root,
    [switch] $Activate
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$signature = @'
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
[DllImport("user32.dll", SetLastError = true)] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
[DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
[DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr dpiContext);
[DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr hWnd, uint gaFlags);
[DllImport("user32.dll", SetLastError = true)] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
'@
$u32 = Add-Type -MemberDefinition $signature -Name 'U32' -Namespace 'Snap' -PassThru

# DPI_AWARENESS_CONTEXT_UNAWARE = -1
try { [void][Snap.U32]::SetThreadDpiAwarenessContext([IntPtr](-1)) } catch { }

$h = [IntPtr]$Hwnd
if (-not [Snap.U32]::IsWindow($h)) { Write-Error "HWND $Hwnd is not a valid window." }
if ($Root) { $h = [Snap.U32]::GetAncestor($h, 2) }   # GA_ROOT

if ($Activate) {
    [void][Snap.U32]::ShowWindow($h, 9)         # SW_RESTORE
    [void][Snap.U32]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 250
}

$rect = New-Object Snap.U32+RECT
[void][Snap.U32]::GetWindowRect($h, [ref]$rect)
$w  = [int]($rect.Right  - $rect.Left)
$ht = [int]($rect.Bottom - $rect.Top)
if ($w -le 0 -or $ht -le 0) { Write-Error "Window $Hwnd has zero size; cannot capture." }

$bmp = New-Object System.Drawing.Bitmap $w, $ht, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.Clear([System.Drawing.Color]::White)
$hdc = $gfx.GetHdc()
$ok = $false
try {
    $ok = [Snap.U32]::PrintWindow($h, $hdc, 2)   # PW_RENDERFULLCONTENT
} finally {
    $gfx.ReleaseHdc($hdc)
}

# A blank PrintWindow result is one flat colour: test a coarse grid.
$flat = $true
if ($ok) {
    $first = $bmp.GetPixel(0, 0)
    for ($y = 0; $y -lt $ht -and $flat; $y += [Math]::Max(1, [int]($ht / 12))) {
        for ($x = 0; $x -lt $w; $x += [Math]::Max(1, [int]($w / 12))) {
            if ($bmp.GetPixel($x, $y) -ne $first) { $flat = $false; break }
        }
    }
}
$method = 'PrintWindow'
if (-not $ok -or $flat) {
    $gfx.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size($w, $ht)))
    $method = 'CopyFromScreen'
}

$dir = Split-Path -Path $OutFile -Parent
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose(); $bmp.Dispose()
Write-Output "$w $ht $method"

param(
    [Parameter(Mandatory=$true)][int]$Hwnd,
    [Parameter(Mandatory=$true)][string]$OutFile
)
# Captures the on-screen rectangle of a window (by HWND) to a PNG. Unlike PrintWindow,
# a screen-region BitBlt includes docked child windows (VFP toolbars) and the menu bar.
# Requires the window to be visible (NOT minimized).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinReg {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing

$h = [IntPtr]$Hwnd
[WinReg]::ShowWindow($h, 3) | Out-Null      # SW_MAXIMIZE
[WinReg]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 700

$r = New-Object WinReg+RECT
[WinReg]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$ht = $r.Bottom - $r.Top
if ($w -le 0 -or $ht -le 0) { throw "bad window rect" }

$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size($w, $ht)))
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()

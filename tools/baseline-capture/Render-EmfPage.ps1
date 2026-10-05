param(
    [Parameter(Mandatory = $true)] [string] $InFile,
    [Parameter(Mandatory = $true)] [string] $OutFile,
    [double] $Scale = 2.0
)
<#
.SYNOPSIS
    Rasterise an EMF report page to PNG.

.DESCRIPTION
    Pair with VFP 9's ReportListener:
        loListener.ListenerType = 3          && render every page, no output device
        REPORT FORM x.frx OBJECT loListener
        loListener.OutputPage(n, "page.emf", 100)   && LISTENER_DEVICE_TYPE_EMF
    then
        powershell -File Render-EmfPage.ps1 -InFile page.emf -OutFile page.png -Scale 2

    Why not OutputPage's own PNG (device type 104): on a 200% DPI desktop it
    returned a bitmap of half the page size with the page drawn at full size and
    clipped, whatever nWidth/nHeight were passed (Tastrade, VFP 9 SP2, Windows 11).
    The EMF is the whole page as vectors, so the raster is made here at any scale
    (2.0 = 1632 by 2112 pixels for Letter).
#>
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$emf = [System.Drawing.Imaging.Metafile]::new($InFile)
$w = [int][Math]::Round($emf.Width * $Scale)
$h = [int][Math]::Round($emf.Height * $Scale)
$bmp = New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::White)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.DrawImage($emf, (New-Object System.Drawing.Rectangle 0, 0, $w, $h))
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose(); $emf.Dispose()
Write-Output "$w $h"

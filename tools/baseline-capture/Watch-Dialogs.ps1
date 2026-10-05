param(
    [Parameter(Mandatory = $true)] [int] $ProcessId,
    [Parameter(Mandatory = $true)] [string] $OutDir,
    [string] $StopFile = '',
    [int] $TimeoutSec = 1200,
    [string[]] $EnterOnTitle = @(),
    [string[]] $Prefer = @('Ignore', 'OK', 'No', 'Cancel', 'Yes'),
    [string] $AnswerFile = ''
)
<#
.SYNOPSIS
    Watch a process for Win32 message boxes; screenshot, log, and dismiss each.

.DESCRIPTION
    Polls every 400 ms until the process exits, $StopFile appears, or $TimeoutSec
    elapses. Every visible top-level #32770 window belonging to the process is
    snapshotted to $OutDir\dialogs\NN.png, its title, static text, and button
    captions are appended to $OutDir\dialogs.csv, and the first button whose
    caption is in $Prefer (in that order) is clicked with WM_COMMAND/BN_CLICKED.

    -EnterOnTitle: titles of child windows (e.g. VFP modal forms opened while a
    report runs, which the app's own timers cannot reach) that are snapshotted
    to $OutDir\forms\<title>.png and answered with Enter (their default button).

    -AnswerFile: a file the harness writes before an action whose dialog needs
    a particular answer: a button caption ("Yes" on a delete confirmation) or
    "KEYS:<SendKeys string>" for a child window ("KEYS:{DOWN}{ENTER}"). Read
    once and deleted, so the default preference order resumes afterwards.

    Learned on Tastrade (Windows 11 26200): FindWindowEx(NULL, ..., "#32770")
    finds no MessageBox and FindWindowEx by child class stops after the first
    Static; EnumWindows/EnumChildWindows with callbacks work. Snapshots go
    through Snap-Window.ps1 beside this script. Only the given process is
    touched; nothing is killed here.
#>
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$signature = @'
public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
[DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr lParam);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder sb, int max);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder sb, int max);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr hWnd, uint gaFlags);
'@
$u32 = Add-Type -MemberDefinition $signature -Name 'U32' -Namespace 'Watch' -PassThru
Add-Type -AssemblyName System.Windows.Forms

function Get-Text([IntPtr] $h) { $sb = New-Object System.Text.StringBuilder 4096; [void][Watch.U32]::GetWindowText($h, $sb, $sb.Capacity); $sb.ToString() }
function Get-Class([IntPtr] $h) { $sb = New-Object System.Text.StringBuilder 256; [void][Watch.U32]::GetClassName($h, $sb, $sb.Capacity); $sb.ToString() }
function Get-TopWindows { $l = New-Object System.Collections.ArrayList; $cb = [Watch.U32+EnumProc]{ param($h, $x); [void]$l.Add($h); $true }; [void][Watch.U32]::EnumWindows($cb, [IntPtr]::Zero); @($l) }
function Get-Descendants([IntPtr] $p) { $l = New-Object System.Collections.ArrayList; $cb = [Watch.U32+EnumProc]{ param($h, $x); [void]$l.Add($h); $true }; [void][Watch.U32]::EnumChildWindows($p, $cb, [IntPtr]::Zero); @($l) }
function Owned([IntPtr] $h) { $q = [uint32]0; [void][Watch.U32]::GetWindowThreadProcessId($h, [ref]$q); $q -eq $ProcessId }
function Q($v) { '"' + ([string]$v).Replace('"', '""') + '"' }
function Snap([IntPtr] $h, [string] $file) {
    $ErrorActionPreference = 'Continue'   # a vanished window is a stderr line, not a reason to stop
    try { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$here\Snap-Window.ps1" -Hwnd ([long]$h) -OutFile $file 2>&1 | Out-Null } catch { }
}
function Read-Answer {
    if (-not $AnswerFile -or -not (Test-Path $AnswerFile)) { return '' }
    $a = (Get-Content $AnswerFile -Raw).Trim(); Remove-Item $AnswerFile -Force; return $a
}

foreach ($d in 'dialogs', 'forms') { $p = Join-Path $OutDir $d; if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }
$csv = Join-Path $OutDir 'dialogs.csv'
if (-not (Test-Path $csv)) { Set-Content -Path $csv -Value 'seq,time,title,text,buttons,pressed,file' -Encoding utf8 }

$started = Get-Date
$seen = @{}
$seq = 0
while ($true) {
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { Write-Host 'Process exited.'; break }
    if ($StopFile -and (Test-Path $StopFile)) { Write-Host 'Stop file seen.'; break }
    if (((Get-Date) - $started).TotalSeconds -gt $TimeoutSec) { Write-Host 'Timeout.'; break }
    foreach ($k in @($seen.Keys)) { if (-not [Watch.U32]::IsWindow([IntPtr][long]$k)) { $seen.Remove($k) } }

    foreach ($h in Get-TopWindows) {
        if (-not (Owned $h)) { continue }
        if ((Get-Class $h) -eq '#32770' -and [Watch.U32]::IsWindowVisible($h)) {
            $key = [string][long]$h
            if ($seen.ContainsKey($key)) { continue }
            $seen[$key] = $true
            Start-Sleep -Milliseconds 500
            $seq++
            $title = Get-Text $h
            $kids = Get-Descendants $h
            $texts = @($kids | Where-Object { (Get-Class $_) -eq 'Static' } | ForEach-Object { Get-Text $_ } | Where-Object { $_ -ne '' })
            $buttons = @($kids | Where-Object { (Get-Class $_) -eq 'Button' })
            $captions = @($buttons | ForEach-Object { (Get-Text $_).Replace('&', '') })
            $file = "dialogs\{0:d2}.png" -f $seq
            Snap $h (Join-Path $OutDir $file)
            $pick = -1
            $order = $Prefer
            $answer = Read-Answer
            if ($answer -and -not $answer.StartsWith('KEYS:')) { $order = @($answer) + $Prefer }
            foreach ($want in $order) { $i = [array]::IndexOf($captions, $want); if ($i -ge 0) { $pick = $i; break } }
            if ($pick -lt 0 -and $buttons.Count -gt 0) { $pick = 0 }
            $pressed = ''
            if ($pick -ge 0) {
                $hb = $buttons[$pick]
                [void][Watch.U32]::PostMessage($h, 0x0111, [IntPtr][Watch.U32]::GetDlgCtrlID($hb), $hb)   # WM_COMMAND, BN_CLICKED
                $pressed = $captions[$pick]
            }
            Add-Content -Path $csv -Encoding utf8 -Value (($seq, (Q (Get-Date).ToString('HH:mm:ss')), (Q $title), (Q ($texts -join ' | ')), (Q ($captions -join '/')), (Q $pressed), (Q $file)) -join ',')
            Write-Host "dialog $seq '$title': $($texts -join ' | ') [$($captions -join '/')] -> $pressed"
            continue
        }
        if ($EnterOnTitle.Count -eq 0) { continue }
        foreach ($c in Get-Descendants $h) {
            if (-not [Watch.U32]::IsWindowVisible($c)) { continue }
            $t = Get-Text $c
            if ($EnterOnTitle -notcontains $t) { continue }
            $key = [string][long]$c
            if ($seen.ContainsKey($key)) { continue }
            $seen[$key] = $true
            Start-Sleep -Milliseconds 800
            if (-not ([Watch.U32]::IsWindow($c) -and [Watch.U32]::IsWindowVisible($c))) { continue }
            $seq++
            $safe = ($t -replace '[^A-Za-z0-9_-]', '_')
            $file = "forms\$safe-$seq.png"
            Snap $c (Join-Path $OutDir $file)
            [void][Watch.U32]::SetForegroundWindow([Watch.U32]::GetAncestor($c, 2))
            Start-Sleep -Milliseconds 200
            $keys = '{ENTER}'
            $answer = Read-Answer
            if ($answer.StartsWith('KEYS:')) { $keys = $answer.Substring(5) }
            [System.Windows.Forms.SendKeys]::SendWait($keys)
            Add-Content -Path $csv -Encoding utf8 -Value (($seq, (Q (Get-Date).ToString('HH:mm:ss')), (Q $t), (Q 'child window answered with keys'), (Q '(default button)'), (Q $keys), (Q $file)) -join ',')
            Write-Host "form '$t' -> $keys"
        }
    }
    Start-Sleep -Milliseconds 400
}

param([string]$LogPath,[string]$Title='BAT68 QMK 按键测试')
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bat68Form=[System.Windows.Forms.Form]::new()
$bat68Form.Text=$Title
$bat68Form.Size=[System.Drawing.Size]::new(820,560)
$bat68Form.StartPosition='CenterScreen'
$bat68Form.KeyPreview=$true
$bat68Form.Font=[System.Drawing.Font]::new('Microsoft YaHei UI',12)
$bat68Instructions=[System.Windows.Forms.Label]::new()
$bat68Instructions.Text="请测试普通打字、Fn+1（应显示 F1）、Fn+W（应显示 Up）。`n按下和松开都会显示在下方；输入只在这个窗口内测试。"
$bat68Instructions.Dock='Top'
$bat68Instructions.Height=86
$bat68Last=[System.Windows.Forms.Label]::new()
$bat68Last.Text='等待按键…'
$bat68Last.Font=[System.Drawing.Font]::new('Consolas',22)
$bat68Last.Dock='Top'
$bat68Last.Height=64
$bat68List=[System.Windows.Forms.ListBox]::new()
$bat68List.Dock='Fill'
$bat68List.Font=[System.Drawing.Font]::new('Consolas',13)
$bat68Form.Controls.Add($bat68List)
$bat68Form.Controls.Add($bat68Last)
$bat68Form.Controls.Add($bat68Instructions)
$bat68Form.Add_KeyDown({
    param($sender,$event)
    $bat68Item=[pscustomobject]@{time=(Get-Date).ToString('o');event='down';key=$event.KeyCode.ToString();modifiers=$event.Modifiers.ToString()}
    $bat68Last.Text='DOWN  '+$event.KeyData.ToString()
    [void]$bat68List.Items.Add('DOWN  '+$event.KeyData.ToString())
    $bat68List.TopIndex=[Math]::Max(0,$bat68List.Items.Count-1)
    if($LogPath){$bat68Item|ConvertTo-Json -Compress|Add-Content -LiteralPath $LogPath -Encoding utf8}
    $event.SuppressKeyPress=$true
    $event.Handled=$true
})
$bat68Form.Add_KeyUp({
    param($sender,$event)
    $bat68Item=[pscustomobject]@{time=(Get-Date).ToString('o');event='up';key=$event.KeyCode.ToString();modifiers=$event.Modifiers.ToString()}
    [void]$bat68List.Items.Add('UP    '+$event.KeyData.ToString())
    $bat68List.TopIndex=[Math]::Max(0,$bat68List.Items.Count-1)
    if($LogPath){$bat68Item|ConvertTo-Json -Compress|Add-Content -LiteralPath $LogPath -Encoding utf8}
    $event.Handled=$true
})
$bat68Form.Add_Shown({$bat68Form.TopMost=$true;$bat68Form.Activate();$bat68Form.TopMost=$false})
[System.Windows.Forms.Application]::Run($bat68Form)

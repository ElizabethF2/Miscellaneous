@echo off

cd %~dp0
powershell -c "$c=[IO.File]::ReadAllText('%0');iex ($c.Substring($c.IndexOf('#' + '##')))"
set /p "unused=[Press enter to exit]"
goto :EOF
###

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName Microsoft.VisualBasic

Function Sync-Save
{
  Param ($name, $local_path, $cloud_path)

  Write-Host ('Syncing ' + $name);

  # NB: only checks mtimes for files at a depth of 1, no dir walking yet
  # NB: assumes clocks are synched accurately

  $local_parent_dir = Split-Path -parent $local_path;
  If (($local_parent_dir) -and (Test-Path $local_parent_dir))
  {
    $local_item = (Get-ChildItem -ErrorAction SilentlyContinue -Attributes !Directory $local_path | Sort-Object -Descending -Property LastWriteTimeUtc | select -First 1)
    $local_mtime = If ($local_item -eq $null) {0} Else {$local_item.LastWriteTimeUtc.Ticks}

    $cloud_mtime = 0;
    If (Test-Path $cloud_path)
    {
      $z = [IO.Compression.ZipFile]::OpenRead($cloud_path);
      $cloud_mtime = ($z.Entries | ? CompressedLength -gt 0 | Sort-Object -Descending -Property LastWriteTime | select -First 1).LastWriteTime.UtcTicks;
      $z.Dispose();
    }

    $local_mtime = [Math]::Round($local_mtime/100000000);
    $cloud_mtime = [Math]::Round($cloud_mtime/100000000);

    If (($local_mtime -eq 0) -and ($cloud_mtime -eq 0))
    {
      Write-Host '  No local or cloud copy. Nothing to do. Skipping...';
    }
    ElseIf ($local_mtime -gt $cloud_mtime)
    {
      Write-Host '  Sync Local -> Cloud';
      If (Test-Path $cloud_path)
      {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($cloud_path,'OnlyErrorDialogs','SendToRecycleBin');
      }
      Compress-Archive -Path $local_path -DestinationPath $cloud_path
    }
    ElseIf ($cloud_mtime -gt $local_mtime)
    {
      Write-Host '  Sync Cloud -> Local';
      If (Test-Path $local_path)
      {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($local_path,'OnlyErrorDialogs','SendToRecycleBin');
      }
      Expand-Archive -Path $cloud_path -DestinationPath $local_parent_dir
    }
    Else
    {
      Write-Host '  Local and Cloud have same mtime. Assuming already synced. Skipping...';
    }
  }
  Else
  {
    Write-Host '  Local parent dir missing. Assuming game not installed locally. Skipping...';
  }
}

$MC_MAPS = @{

  Example = 'W2tPmrKZ4ql=';
};

# $LOCAL_MC_SAVES = $env:LocalAppData + '\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\minecraftWorlds';
# $LOCAL_MC_SAVES = $env:AppData + '\Minecraft Bedrock\Users\123\games\com.mojang\minecraftWorlds';



foreach ($i in $MC_MAPS.GetEnumerator())
{
  $local_path = $LOCAL_MC_SAVES + '\' + $i.Value;
  $cloud_path = 'saves\' + $i.Name + '.zip'
  Sync-Save ('Minecraft - ' + $i.Name) $local_path $cloud_path
}

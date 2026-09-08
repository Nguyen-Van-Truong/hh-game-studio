param([Parameter(Mandatory=$true)][string]$Manifest)
$ErrorActionPreference='Stop'
$m=Get-Content -LiteralPath $Manifest -Raw|ConvertFrom-Json
$fail=[Collections.Generic.List[string]]::new()
$stats=[Collections.Generic.List[object]]::new()
$globalIds=[Collections.Generic.List[string]]::new()
$allDeps=@{}
$links=0
$edges=0
$decoder=[Text.UTF8Encoding]::new($false,$true)
foreach($f in $m.files){
 $actual=(Get-FileHash -LiteralPath $f.absolute_path).Hash.ToLowerInvariant()
 if($actual -ne $f.sha256){$fail.Add('Freeze mismatch: '+$f.path)}
 $txt=$decoder.GetString([IO.File]::ReadAllBytes($f.absolute_path)).Replace("`r`n","`n")
 if($txt.Contains([string][char]0xfffd)){$fail.Add('Replacement char: '+$f.path)}
 foreach($link in [regex]::Matches($txt,'\[[^\]\r\n]+\]\(([^)\r\n]+)\)')){
  $target=$link.Groups[1].Value
  if($target -match '^https?://|^#'){continue}
  $target=($target -split '#')[0].Trim('<','>')
  if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $f.absolute_path) $target))){$fail.Add('Missing routing link: '+$f.path+' -> '+$target)}
  $links++
 }
 $isTools=$f.absolute_path.EndsWith('/8-9-godot-blender-agent-studio-plan.txt')
 $isGame=$f.absolute_path.EndsWith('/8-9-hh-world-gameplay-viet-nam-plan.txt')
 if(-not($isTools -or $isGame)){continue}
 $expect=if($isTools){10}else{32}
 $prefix=if($isTools){'GT-\d{2}'}else{'H2-P\d-\d{2}'}
 $rows=[regex]::Matches($txt,'(?m)^\d{2} \| ('+$prefix+') \| [^\n|]+ \| ([^\n|]+) \| (\w+)$')
 $specs=[regex]::Matches($txt,'(?m)^### ('+$prefix+') — [^\n]+$')
 if($rows.Count -ne $expect -or $specs.Count -ne $expect){$fail.Add('WP/spec count: '+$f.path)}
 if($rows.Count -and $rows[0].Index -gt 1000){$fail.Add('Table not first')}
 foreach($row in $rows){
  $id=$row.Groups[1].Value
  if($globalIds.Contains($id)){$fail.Add('Duplicate ID '+$id)}else{$globalIds.Add($id)}
  $deps=@($row.Groups[2].Value.Split(',')|ForEach-Object{$_.Trim()})
  $allDeps[$id]=$deps
  if($row.Groups[3].Value -ne 'PLANNED'){$fail.Add('Unexpected implementation status '+$id)}
 }
 if([regex]::Matches($txt,'(?m)^CURRENT_VALID_WP=').Count -ne 1 -or -not $txt.Contains('CURRENT_VALID_WP='+$rows[0].Groups[1].Value)){$fail.Add('Current WP '+$f.path)}
 for($i=0;$i -lt $specs.Count;$i++){
  $end=if($i+1 -lt $specs.Count){$specs[$i+1].Index}else{$txt.IndexOf("`n"+$(if($isTools){'4. TQ'}else{'6. REGISTRY'}),$specs[$i].Index)}
  if($end -lt 0){$fail.Add('Missing specs end');continue}
  $block=$txt.Substring($specs[$i].Index,$end-$specs[$i].Index)
  foreach($label in @('ALLOWED:','BUILD:','VERIFY:','DoD:')){if(-not $block.Contains($label)){$fail.Add('Missing '+$label+' '+$specs[$i].Groups[1].Value)}}
  if(-not @($rows|ForEach-Object{$_.Groups[1].Value}).Contains($specs[$i].Groups[1].Value)){$fail.Add('Spec without table')}
 }
 $endMarker=if($isTools){'END_OF_TOOLS_PLAN'}else{'END_OF_GAME_PLAN'}
 if([regex]::Matches($txt,'(?m)^'+$endMarker+'$').Count -ne 1 -or $txt.IndexOf($endMarker) -lt $txt.Length-250){$fail.Add('End sentinel '+$f.path)}
 $exPrefix=if($isTools){'TX'}else{'EX'}
 $exExpected=if($isTools){14}else{36}
 $ex=[regex]::Matches($txt,'(?m)^'+$exPrefix+'(\d{2}) — ')
 if($ex.Count -ne $exExpected){$fail.Add('Exception count '+$f.path)}
 for($i=0;$i -lt $ex.Count;$i++){if([int]$ex[$i].Groups[1].Value -ne $i+1){$fail.Add('Exception sequence')}}
 foreach($link in [regex]::Matches($txt,'(?m)^(\.\.?/[^\r\n]+)$')){
  if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $f.absolute_path) $link.Value))){$fail.Add('Missing plan/evidence link '+$link.Value)}
  $links++
 }
 if($isGame -and ($txt -match '\bST-\d{2}\b|mục2\.2|mục2\.5|END_OF_UNIFIED|40WP|48cases')){$fail.Add('Stale unified contract in game')}
 foreach($marker in @('PLAN_REVISION=S1','IMPLEMENTATION=NOT_STARTED','RUNTIME_ACCEPTANCE=NONE','EXECUTION_AUTHORIZATION=PLAN_ONLY')){if(-not $txt.Contains($marker)){$fail.Add('Missing state '+$marker)}}
 $stats.Add([ordered]@{path=$f.path;wp_count=$rows.Count;spec_count=$specs.Count;exception_count=$ex.Count;bytes=(Get-Item -LiteralPath $f.absolute_path).Length;sha256=$actual})
}
$orderedIds=@($globalIds|Where-Object{$_ -match '^GT-'}|Sort-Object)+@($globalIds|Where-Object{$_ -match '^H2-'}|Sort-Object)
$cross=@()
foreach($id in $orderedIds){
 foreach($dep in $allDeps[$id]){
  if($dep -eq 'OWNER_START'){if($id -ne 'GT-01'){$fail.Add('Unexpected OWNER_START')};continue}
  $edges++
  if(-not $allDeps.ContainsKey($dep)){$fail.Add('Unknown dependency '+$id+' -> '+$dep);continue}
  if([array]::IndexOf($orderedIds,$dep) -ge [array]::IndexOf($orderedIds,$id)){$fail.Add('Non-topological/cycle '+$id+' -> '+$dep)}
  if(($id -match '^GT-' -and $dep -match '^H2-') -or ($id -match '^H2-' -and $dep -match '^GT-')){$cross+=($dep+' -> '+$id)}
 }
}
if($stats.Count -ne 2 -or $globalIds.Count -ne 42){$fail.Add('Two active plans / 42 WP invariant')}
if(($cross -join ',') -ne 'GT-10 -> H2-P0-01'){$fail.Add('Cross-plan dependency contract')}
$canonical=($m.files|Sort-Object path|ForEach-Object{$_.path+' '+$_.sha256}) -join [char]10
$mh=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($canonical))).ToLowerInvariant()
if($mh -ne $m.manifest_sha256){$fail.Add('Aggregate manifest mismatch')}
$math=@([math]::Floor(2400/180),[math]::Floor(10/.6),[math]::Floor(87500000/(32*30000)),[math]::Floor(87500000/(32*10000)),([math]::Ceiling([math]::Ceiling(1000/32)/8)+1),([math]::Ceiling([math]::Ceiling(1000/19.2)/8)+1),(1000*30000*86400*30/1e12),(200*30000*86400*30/1e12))
if(($math -join ',') -ne '13,16,91,273,5,8,77.76,15.552'){$fail.Add('Sizing arithmetic')}
[ordered]@{kind='STATIC_DOCUMENT_VALIDATION_NOT_RUNTIME';checked_at=(Get-Date -Format o);manifest_sha256=$mh;source_files=$m.files.Count;plans=@($stats);total_wp=$globalIds.Count;dependencies=$edges;cross_plan_dependency=$cross;checked_local_links=$links;arithmetic=$math;errors=@($fail);result=$(if($fail.Count){'FAIL'}else{'PASS_STATIC_ONLY'})}|ConvertTo-Json -Depth 7
if($fail.Count){exit 1}

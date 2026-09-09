param([Parameter(Mandatory=$true)][string]$Manifest)
$ErrorActionPreference='Stop'; $m=Get-Content -LiteralPath $Manifest -Raw|ConvertFrom-Json; $fail=[Collections.Generic.List[string]]::new(); $stats=@(); $all=@{}; $order=@(); $dec=[Text.UTF8Encoding]::new($false,$true); $base=Split-Path (Split-Path $Manifest)
foreach($f in $m.files){
  if(-not(Test-Path -LiteralPath $f.absolute_path)){$fail.Add('Missing plan '+$f.path);continue}
  $sha=(Get-FileHash -LiteralPath $f.absolute_path).Hash.ToLowerInvariant();if($sha -ne $f.sha256){$fail.Add('Hash mismatch '+$f.path)}
  $t=$dec.GetString([IO.File]::ReadAllBytes($f.absolute_path)).Replace("`r`n","`n")
  if($t.Contains([string][char]0xfffd)){$fail.Add('Invalid UTF8 '+$f.path)}
  $isTool=$f.path -eq '8-9-godot-blender-agent-studio-plan.txt';$isGame=$f.path -eq '8-9-hh-world-gameplay-viet-nam-plan.txt';if(-not($isTool -or $isGame)){$fail.Add('Unexpected manifest file '+$f.path);continue}
  $prefix=if($isTool){'GT-\d{2}'}else{'H2-P\d-\d{2}'};$expected=if($isTool){10}else{32};$exPrefix=if($isTool){'TX'}else{'EX'};$exExpected=if($isTool){14}else{36}
  $rows=[regex]::Matches($t,'(?m)^\d{2} \| ('+$prefix+') \| [^\n|]+ \| ([^\n|]+) \| PLANNED$');$spec=[regex]::Matches($t,'(?m)^### ('+$prefix+') — ');$ex=[regex]::Matches($t,'(?m)^'+$exPrefix+'(\d{2}) — ')
  if($rows.Count-ne$expected){$fail.Add("WP count $($f.path)=$($rows.Count), expected $expected")};if($spec.Count-ne$expected){$fail.Add("Spec count $($f.path)=$($spec.Count), expected $expected")};if($ex.Count-ne$exExpected){$fail.Add("Exception count $($f.path)=$($ex.Count), expected $exExpected")}
  if($t.IndexOf($rows[0].Value) -gt 1000){$fail.Add('Progress table not near beginning '+$f.path)}
  $cur=([regex]::Match($t,'(?m)^CURRENT_VALID_WP=.*$')).Value;if(-not $cur){$fail.Add('Missing CURRENT '+$f.path)}else{if($cur -notmatch [regex]::Escape($rows[0].Groups[1].Value)){$fail.Add('CURRENT mismatch '+$f.path)}}
  foreach($marker in @('PLAN_REVISION=S2','EXECUTION_AUTHORIZATION=PLAN_ONLY','IMPLEMENTATION=NOT_STARTED','RUNTIME_ACCEPTANCE=NONE','END_OF_'+$(if($isTool){'TOOLS'}else{'GAME'})+'_PLAN')){if(-not $t.Contains($marker)){$fail.Add("Missing $marker in $f.path")}}
  foreach($r0 in $rows){$id=$r0.Groups[1].Value;if($all.ContainsKey($id)){$fail.Add('Duplicate ID '+$id)}else{$all[$id]=$r0.Groups[2].Value;$order+=$id}}
  for($i=0;$i-lt$ex.Count;$i++){if([int]$ex[$i].Groups[1].Value-ne$i+1){$fail.Add('Exception sequence '+$f.path);break}}
  if($isGame){if($t -match '\bST-\d{2}\b|GT-TOOL-HISTORY|END_OF_UNIFIED|40WP|48cases|hh-3d/hh-3d-2'){ $fail.Add('Stale or wrong-scope reference in game') };if(-not($t -match '3\.2\.1 PHẠM VI QUY MÔ')){$fail.Add('Missing scale section')};if(-not($t -match '32 người/room')){$fail.Add('Missing room cap')};if(-not($t -match '100/300/1k/10k')){$fail.Add('Missing scale ladder')};if(-not($t -match '100 triệu')){$fail.Add('Missing hundred-million account distinction')};if(-not($t -match 'RSS/heap/GC')){$fail.Add('Missing memory metrics')};if(-not($t -match 'cache/CDN')){$fail.Add('Missing cache/CDN scale controls')}}
  if($isTool){if(-not($t -match 'fixture/sample-game')){$fail.Add('Missing independent fixture')};if(-not($t -match 'GT-10')){$fail.Add('Missing package handoff')};if($t -match 'PLAN_REVISION=S1'){$fail.Add('Stale S1 state in tools')}}
  foreach($l in [regex]::Matches($t,'(?m)^\./[^\r\n]+$')){if($l.Value -match '^\./(reviews/20260908/REVIEW-RESULT\.md|8-9-hh-studio-godot-blender-hh-world-plan\.txt|8-9-hh-world-gameplay-viet-nam-plan\.txt|8-9-godot-blender-agent-studio-plan\.txt)$'){continue}; if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $f.absolute_path) $l.Value))){$fail.Add('Missing relative link '+$l.Value+' in '+$f.path)}}
  $stats+=,[ordered]@{path=$f.path;sha256=$sha;bytes=(Get-Item $f.absolute_path).Length;wp_count=$rows.Count;spec_count=$spec.Count;exception_count=$ex.Count}
}
if($all.Count-ne42){$fail.Add('Expected 42 active WP IDs')};if(-not($all.ContainsKey('H2-P0-01')) -or $all['H2-P0-01'] -notmatch 'GT-10'){$fail.Add('Missing only cross-plan handoff GT-10 -> H2-P0-01')}
$canon=($m.files|Sort-Object path|ForEach-Object{$_.path+' '+$_.sha256})-join [char]10;$agg=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($canon))).ToLowerInvariant();if($agg-ne$m.manifest_sha256){$fail.Add('Manifest aggregate mismatch')}
[ordered]@{kind='STATIC_PLAN_CHECK_NOT_RUNTIME';checked_at=(Get-Date -Format o);manifest_sha256=$agg;plans=$stats;active_wp=$all.Count;errors=@($fail);result=$(if($fail.Count){'FAIL'}else{'PASS_STATIC_ONLY'})}|ConvertTo-Json -Depth 7
if($fail.Count){exit 1}

param([Parameter(Mandatory=$true)][string]$Plan,[Parameter(Mandatory=$true)][string]$Manifest)
$ErrorActionPreference='Stop'
$t=Get-Content -LiteralPath $Plan -Raw
$m=Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$fail=[Collections.Generic.List[string]]::new()
$rows=@([regex]::Matches($t,'(?m)^\d{2} \| (H2-P\d+-\d+|ST-\d+) \| ([^|\r\n]+) \| ([^|\r\n]+) \| ([^|\r\n]+)'))
$ids=@($rows|ForEach-Object {$_.Groups[1].Value})
$heads=@([regex]::Matches($t,'(?m)^### (H2-P\d+-\d+|ST-\d+) —'))
$hids=@($heads|ForEach-Object {$_.Groups[1].Value})
if($rows.Count -ne 40 -or ($ids|Sort-Object -Unique).Count -ne 40 -or $heads.Count -ne 40 -or (Compare-Object ($ids|Sort-Object) ($hids|Sort-Object))){$fail.Add('WP rows/specs missing/duplicate')}
$edges=0
foreach($r in $rows){
 $i=[array]::IndexOf($ids,$r.Groups[1].Value)
 if($r.Groups[4].Value.Trim() -ne 'PLANNED'){$fail.Add('Unexpected implementation state')}
 foreach($d in [regex]::Matches($r.Groups[3].Value,'H2-P\d+-\d+|ST-\d+')){
  $j=[array]::IndexOf($ids,$d.Value)
  if($j -lt 0 -or $j -ge $i){$fail.Add('Dependency: '+$r.Groups[1].Value+' -> '+$d.Value)}
  $edges++
 }
}
for($i=0;$i -lt $heads.Count;$i++){
 $end=if($i+1 -lt $heads.Count){$heads[$i+1].Index}else{$t.Length}
 $s=$t.Substring($heads[$i].Index,$end-$heads[$i].Index)
 foreach($marker in @('ALLOWED:','BUILD:','VERIFY:','DoD:')){if(-not $s.Contains($marker)){$fail.Add($hids[$i]+' missing '+$marker)}}
}
$ex=@([regex]::Matches($t,'(?m)^EX(\d{2}) —')|ForEach-Object {$_.Groups[1].Value})
if(($ex -join ',') -ne ((1..48|ForEach-Object {$_.ToString('00')}) -join ',')){$fail.Add('EX IDs')}
if([regex]::Matches($t,'(?m)^DB-D[1-4] —').Count -ne 4){$fail.Add('DB profiles')}
if([regex]::Matches($t,'(?m)^END_OF_UNIFIED_PLAN\r?$').Count -ne 1){$fail.Add('END marker')}
if([regex]::Matches($t,'(?m)^CURRENT_VALID_WP=H2-P0-01\r?$').Count -ne 1){$fail.Add('Current WP')}
if($t.IndexOf('01 | H2-P0-01') -gt 500){$fail.Add('Table position')}
if($t -match '(?im)\[[ x]\]|TODO|TBD|\[R\d+\]|text_not_a_command_placeholder'){$fail.Add('Placeholder')}
foreach($ref in @('D01','D02','D03','D04','D05','T01','T02','T03','T04','T05','T06')){
 if([regex]::IsMatch($t,'\b'+$ref+'\b')){$fail.Add('Legacy contract reference '+$ref)}
}
$linkCount=0
foreach($f in $m.files){
 if((Get-FileHash -LiteralPath $f.absolute_path).Hash.ToLowerInvariant() -ne $f.sha256){$fail.Add('Freeze mismatch: '+$f.path)}
 $u=[Text.UTF8Encoding]::new($false,$true)
 $txt=$u.GetString([IO.File]::ReadAllBytes($f.absolute_path))
 if($txt.Contains([string][char]0xfffd)){$fail.Add('UTF8 replacement: '+$f.path)}
 foreach($l in [regex]::Matches($txt,'\[[^\]\r\n]+\]\(([^)\r\n]+)\)')){
  $target=$l.Groups[1].Value
  if($target -match '^https?://|^#'){continue}
  $target=($target -split '#')[0].Trim('<','>')
  if(-not (Test-Path -LiteralPath (Join-Path (Split-Path $f.absolute_path) $target))){$fail.Add('Missing link '+$f.path+' -> '+$target)}
  $linkCount++
 }
}
foreach($l in [regex]::Matches($t,'(?m)^(\.\.?/[^\r\n]+)$')){
 if(-not (Test-Path -LiteralPath (Join-Path (Split-Path $Plan) $l.Groups[1].Value))){$fail.Add('History/evidence link '+$l.Value)}
 $linkCount++
}
$lines=($m.files|Sort-Object path|ForEach-Object {$_.path+' '+$_.sha256}) -join [char]10
$mh=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($lines))).ToLowerInvariant()
if($mh -ne $m.manifest_sha256){$fail.Add('Manifest aggregate')}
$math=@([math]::Floor(2400/180),[math]::Floor(10/.6),[math]::Floor(87500000/(32*30000)),[math]::Floor(87500000/(32*10000)),([math]::Ceiling([math]::Ceiling(1000/32)/8)+1),([math]::Ceiling([math]::Ceiling(1000/19.2)/8)+1),(1000*30000*86400*30/1e12),(200*30000*86400*30/1e12))
if(($math -join ',') -ne '13,16,91,273,5,8,77.76,15.552'){$fail.Add('Capacity arithmetic')}
[ordered]@{kind='STATIC_DOCUMENT_VALIDATION_NOT_RUNTIME';checked_at=(Get-Date -Format o);manifest_sha256=$mh;wp_count=$rows.Count;spec_count=$heads.Count;edges=$edges;ex_count=$ex.Count;links=$linkCount;source_files=$m.files.Count;arithmetic=$math;errors=@($fail);result=$(if($fail.Count){'FAIL'}else{'PASS_STATIC_ONLY'})}|ConvertTo-Json -Depth 5
if($fail.Count){exit 1}

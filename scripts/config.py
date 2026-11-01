#!/usr/bin/env python
"""Temporary Niri mapping/window rules, with backup before every edit."""
import pathlib,sys,datetime,subprocess,re
p=pathlib.Path.home()/'.config/niri/config.kdl'
start='// BEGIN TOUCHDECK EXPERIMENT\n';end='// END TOUCHDECK EXPERIMENT\n'
text=p.read_text();old=p.read_bytes()
if len(sys.argv)!=2 or sys.argv[1] not in ['apply','restore']:raise SystemExit('Usage: config.py apply|restore')
if sys.argv[1]=='apply':
 if start in text:raise SystemExit('Already applied')
 if re.search(r'^\s*touch\s*\{',text,re.M):raise SystemExit('Existing touch block: inspect and merge manually after backup')
 if text.count('input {')!=1:raise SystemExit('Expected one input block; inspect manually')
 text=text.replace('input {','input {\n    // TOUCHDECK MAP\n    touch { map-to-output "DP-1"; }',1)
 text+='\n'+start+'''window-rule {
 match title="^TouchDeck-panel$"
 open-on-output "DP-1"
 open-fullscreen true
}
window-rule {
 match title="^TouchDeck-primary$"
 open-on-output "DP-3"
 open-floating true
}
'''+end
else:
 if start not in text:raise SystemExit('No experiment block')
 a=text.index(start);b=text.index(end,a)+len(end)
 text=text[:a-1]+text[b:]
 # The first experiment version inserted an extra blank line after the mapping.
 text=text.replace('    // TOUCHDECK MAP\n    touch { map-to-output "DP-1"; }\n\n','',1)
 text=text.replace('    // TOUCHDECK MAP\n    touch { map-to-output "DP-1"; }\n','',1)
backup=p.with_name('config.kdl.touchdeck-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.bak')
backup.write_bytes(old);print('Backup:',backup)
p.write_text(text)
if subprocess.run(['niri','validate']).returncode:
 p.write_bytes(old);raise SystemExit('Validation failed; restored')

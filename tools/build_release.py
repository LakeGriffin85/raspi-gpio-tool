"""Build deterministic, self-contained base and Gertboard installers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
COMMON = ('gpio_core.py', 'gpio_gui.py', 'gpio_header.py', 'gpio_support.py',
          'gpio_availability.py', 'gpio_orientation.py', 'gpio_choices.py',
          'gpio_i18n.py', 'gpio_settings.py', 'gpio_locale_en.json',
          'gpio-terminal.sh', 'terminal-bashrc')
ADDON = ('gpio_gertboard.py',)
DOCUMENTS = ('README.md', 'README.de.md', 'LICENSE', 'VERSION', 'docs/GERTBOARD.md',
             'THIRD_PARTY.md', 'PRIVACY.md', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md',
             'SECURITY.md', 'ACCESSIBILITY.md', 'docs/IMAGES.md',
             'docs/assets/project-banner.svg', 'docs/assets/app-screenshot.png',
             'docs/assets/gertboard-on-pi.jpg', 'docs/assets/pin-orientation.svg',
             'docs/assets/gertboard-map.svg')

HEADER = r'''#!/bin/bash
# Raspberry Pi GPIO Tool. Run on the Pi as the normal desktop user.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
umask 077
[[ "$(uname -s)" == Linux && -f /etc/debian_version ]] || { printf 'Run this installer on Raspberry Pi OS.\n' >&2; exit 1; }
[[ "$(id -u)" != 0 ]] || { printf 'Run as your normal user, without sudo before the script.\n' >&2; exit 1; }
LOCK_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/raspi-gpio"
mkdir -p "$LOCK_DIR"
exec 9>"$LOCK_DIR/hardware.lock"
flock -n 9 || { printf 'Close GPIO Workshop before installing.\n' >&2; exit 1; }
sudo apt-get update
sudo apt-get install -y python3-guizero python3-gpiozero python3-lgpio lxterminal xdg-user-dirs
/usr/bin/python3 -c 'import guizero, gpiozero, gpiozero.pins.lgpio'
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/raspi-gpio-tool"
MENU_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP)"
[[ -n "$DESKTOP_DIR" && "$DESKTOP_DIR" != "$HOME" ]] || DESKTOP_DIR="$HOME/Desktop"
mkdir -p "$APP_DIR" "$MENU_DIR" "$DESKTOP_DIR"
STAGE_DIR="$(mktemp -d "$APP_DIR/.install.XXXXXX")"
trap 'rm -rf -- "$STAGE_DIR"' EXIT
'''

FOOTER = r'''
/usr/bin/python3 - "$STAGE_DIR" <<'VERIFY_RUNTIME'
import json, pathlib, py_compile, sys
root=pathlib.Path(sys.argv[1])
for path in root.glob('*.py'):
    py_compile.compile(str(path), doraise=True)
json.loads((root/'gpio_locale_en.json').read_text(encoding='utf-8'))
sys.path.insert(0,str(root))
from gpio_i18n import set_language
set_language('en')
from gpio_core import find_header_chip
from gpio_availability import line_snapshot
chip=find_header_chip()
lines,warning=line_snapshot(chip)
if len(lines)!=28:
    raise SystemExit(warning or 'Cannot read metadata for all 28 GPIOs.')
print('RP1 controller and pin ownership read; no GPIO has been activated.')
VERIFY_RUNTIME
STAMP="$(date +%Y%m%d-%H%M%S)-$$"
BACKUP="$APP_DIR/backups/$STAMP"
mkdir -p "$BACKUP"
for name in "${APP_FILES[@]}"; do
    if [[ -e "$APP_DIR/$name" ]]; then
        cp -p "$APP_DIR/$name" "$BACKUP/$name"
    fi
    mv -f "$STAGE_DIR/$name" "$APP_DIR/$name"
done
chmod 755 "$APP_DIR/gpio_gui.py" "$APP_DIR/gpio-terminal.sh"
/usr/bin/python3 - "$APP_DIR" "$MENU_DIR" "$DESKTOP_DIR" "$STAMP" <<'CREATE_LAUNCHERS'
from pathlib import Path
import shutil, sys
app,menu,desktop=map(Path,sys.argv[1:4])
stamp=sys.argv[4]
def quote(path):
    value=str(path).replace('%','%%')
    for char in ('\\','"','`','$'):
        value=value.replace(char,'\\'+char)
    return '"'+value+'"'
entries=(('raspi-gpio-tool.desktop','Raspberry Pi GPIO Tool',
          '/usr/bin/python3 '+quote(app/'gpio_gui.py'),'applications-engineering',False),
         ('raspi-gpio-tool-terminal.desktop','GPIO Terminal',
          '/bin/bash '+quote(app/'gpio-terminal.sh'),'utilities-terminal',True))
for name,title,command,icon,terminal in entries:
    text=('[Desktop Entry]\nVersion=1.0\nType=Application\n'
          f'Name={title}\nExec={command}\nIcon={icon}\nTerminal={str(terminal).lower()}\n'
          'Categories=Development;Education;\nStartupNotify=false\n')
    for folder in (menu,desktop):
        target=folder/name
        if target.exists():
            shutil.copy2(target,target.with_name(name+'.backup-'+stamp))
        target.write_text(text,encoding='utf-8')
        target.chmod(0o755)
print('Desktop launchers created in:',desktop)
CREATE_LAUNCHERS
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$MENU_DIR" || true
fi
printf '\nInstalled Raspberry Pi GPIO Tool. Open the desktop launcher.\n'
printf 'Choose language and optional Gertboard features in Language & modules.\n'
printf 'Previous files: %s\n' "$BACKUP"
'''


def runtime_names(gertboard=False):
    return COMMON + (ADDON if gertboard else ())


def installer(gertboard=False):
    names=runtime_names(gertboard)
    pieces=[HEADER, 'APP_FILES=('+' '.join(names)+')\n']
    for name in names:
        path=ROOT/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Expected regular runtime source: '+name)
        data=path.read_text(encoding='utf-8')
        if name.endswith('.py'):
            compile(data,name,'exec')
        elif name.endswith('.json'):
            json.loads(data)
        marker='PAYLOAD_'+name.upper().replace('.','_').replace('-','_')
        if marker in data.splitlines():
            raise ValueError('Payload delimiter appears in source: '+name)
        pieces += [f'cat > "$STAGE_DIR/{name}" <<\'{marker}\'\n', data.rstrip('\n')+'\n', marker+'\n']
    pieces.append(FOOTER)
    script=''.join(pieces)
    with tempfile.NamedTemporaryFile(mode='w',suffix='.sh',encoding='utf-8') as check:
        check.write(script);check.flush()
        subprocess.run(['bash','-n',check.name],check=True)
    return script


def build(output):
    version=(ROOT/'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('Invalid release version')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    archives=[]
    for gertboard in (False,True):
        name='raspi-gpio-tool'+('-gertboard' if gertboard else '')+'-'+version
        folder=output/name;folder.mkdir(exist_ok=True)
        files={'install.sh':installer(gertboard).encode('utf-8')}
        for doc in DOCUMENTS:
            files[doc]=(ROOT/doc).read_bytes()
        files['EDITION.txt']=('Gertboard module included\n' if gertboard else 'Base GPIO edition\n').encode()
        files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+path+'\n'
                                        for path,data in sorted(files.items())).encode()
        for path,data in files.items():
            dest=folder/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            if path=='install.sh':dest.chmod(0o755)
        archive=output/(name+'.zip')
        with ZipFile(archive,'w',compression=ZIP_DEFLATED) as package:
            for path,data in sorted(files.items()):
                info=ZipInfo(name+'/'+path,date_time=(1980,1,1,0,0,0))
                info.compress_type=ZIP_DEFLATED
                info.external_attr=(0o755 if path=='install.sh' else 0o644)<<16
                package.writestr(info,data)
        with ZipFile(archive) as package:
            if package.testzip() is not None:raise ValueError('Corrupt archive')
        archives.append(archive)
    (output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in archives))
    return archives


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    for archive in build(parser.parse_args().output):
        print(archive.name)

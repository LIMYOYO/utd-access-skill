"""Prepare a self-contained runtime; registration is a separate explicit operation."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import sqlite3
import time
from pathlib import Path
from .queue import BridgeQueue
from ..config import data_directory

OWNER='paper-access-native-bridge-v1'
HOST='com.paper_access.bridge'

def validate_extension_id(value):
    if not re.fullmatch('[a-p]{32}',value):raise ValueError('invalid_extension_id')
    return value

def registration_path():
    return Path.home()/'Library/Application Support/Google/Chrome/NativeMessagingHosts'/f'{HOST}.json'

def default_runtime():return data_directory()/'bridge-runtime'

def validate_download_root(value):
    root=Path(value).expanduser().absolute()
    if not root.is_dir():raise ValueError('download_root_missing')
    # Candidate staging uses O_NOFOLLOW throughout; reject unsupported aliases now.
    if root.resolve()!=root:raise ValueError('download_root_requires_canonical_path')
    return root

def prepare_install(destination,extension_id,download_root,source_root=None,data_dir=None):
    validate_extension_id(extension_id)
    destination=Path(destination).expanduser().absolute();download_root=validate_download_root(download_root)
    if destination.exists():raise ValueError('prepare_destination_already_exists')
    source_root=Path(source_root) if source_root else Path(__file__).resolve().parents[3]
    uv=shutil.which('uv')
    if not uv:raise ValueError('uv_required_for_preparation')
    destination.mkdir(parents=True,mode=0o700)
    # Install a built wheel, not an editable checkout. No Chrome registration here.
    subprocess.run([uv,'build','--wheel','--out-dir',str(destination/'wheels'),str(source_root)],check=True,capture_output=True)
    subprocess.run([sys._base_executable,'-m','venv','--copies','--without-pip',str(destination/'venv')],check=True,capture_output=True)
    wheel=next((destination/'wheels').glob('paper_access-*.whl'))
    python=destination/'venv/bin/python'
    subprocess.run([uv,'pip','install','--python',str(python),str(wheel)],check=True,capture_output=True)
    config={'extension_id':extension_id,'download_root':str(download_root),'data_dir':str(data_dir or data_directory())}
    config_path=destination/'bridge-config.json';config_path.write_text(json.dumps(config,indent=2));config_path.chmod(0o600)
    launcher=destination/'host'
    launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(python))+' -m paper_access.bridge.host '+shlex.quote(str(config_path))+' "$@"\n');launcher.chmod(0o700)
    extension=destination/'extension';extension.mkdir()
    shutil.copy2(source_root/'manifest.json',extension/'manifest.json');shutil.copytree(source_root/'src',extension/'src')
    marker={'owner':OWNER,'runtime':str(destination),'python':str(python),'extension':str(extension)}
    (destination/'prepared.json').write_text(json.dumps(marker,indent=2))
    return {**marker,'registered':False,'permission':'nativeMessaging','download_root':str(download_root)}

def _prepared(runtime):
    runtime=Path(runtime).expanduser().absolute()
    data=json.loads((runtime/'prepared.json').read_text())
    if data.get('owner')!=OWNER or data.get('runtime')!=str(runtime):raise ValueError('unowned_or_moved_runtime')
    config=json.loads((runtime/'bridge-config.json').read_text());validate_extension_id(config['extension_id'])
    if not (runtime/'host').is_file():raise ValueError('host_missing')
    return runtime,config

def install_prepared(prepared_dir,target=None):
    runtime,config=_prepared(prepared_dir);target=Path(target) if target else registration_path()
    validate_download_root(config['download_root'])
    manifest={'name':HOST,'description':'UTD Access Skill local PDF download and validation bridge','path':str(runtime/'host'),'type':'stdio','allowed_origins':['chrome-extension://'+config['extension_id']+'/']}
    if target.is_symlink():raise ValueError('unsafe_registration')
    if target.exists() and json.loads(target.read_text())!=manifest:raise ValueError('registration_conflict')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w') as stream:json.dump(manifest,stream,indent=2)
    target.chmod(0o600)
    return {'installed':True,'registration':str(target),'runtime':str(runtime),'requires_extension_reload':True}

def uninstall_owned(runtime,target=None):
    runtime,config=_prepared(runtime);target=Path(target) if target else registration_path()
    if target.exists():
        data=json.loads(target.read_text())
        if data.get('name')!=HOST or data.get('path')!=str(runtime/'host') or data.get('allowed_origins')!=['chrome-extension://'+config['extension_id']+'/']:raise ValueError('registration_conflict')
        target.unlink()
    # Preserve runtime as well as papers/data; no recursive deletion of user files.
    return {'installed':False,'runtime_preserved':str(runtime)}

def doctor(runtime=None,target=None):
    target=Path(target) if target else registration_path()
    if runtime is None and target.is_file():
        try:runtime=Path(json.loads(target.read_text())['path']).parent
        except (OSError,ValueError,KeyError):pass
    runtime=Path(runtime) if runtime else default_runtime()
    if not (runtime/'prepared.json').exists():return {'installed':False,'connected':False,'reason':'runtime_not_prepared'}
    try:
        runtime,config=_prepared(runtime)
        validate_download_root(config['download_root'])
        installed=target.is_file() and json.loads(target.read_text()).get('path')==str(runtime/'host')
        db=Path(config['data_dir'])/'bridge.sqlite3'
        connected=False
        if db.exists():
            connection=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
            try:
                row=connection.execute('SELECT heartbeat FROM connection WHERE singleton=1').fetchone()
                connected=bool(row and row[0]>time.time()-10)
            finally:connection.close()
        return {'installed':installed,'connected':bool(connected),'download_root_exists':Path(config['download_root']).is_dir(),'runtime':str(runtime),'extension_id':config['extension_id']}
    except (OSError,ValueError,KeyError,sqlite3.Error):return {'installed':False,'connected':False,'reason':'invalid_configuration'}

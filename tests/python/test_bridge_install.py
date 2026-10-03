import json
from pathlib import Path
import pytest
from paper_access.bridge.install import install_prepared, uninstall_owned, doctor, validate_extension_id, validate_download_root, prepare_install


def test_registration_refuses_foreign_and_uninstall_preserves_data(tmp_path):
    runtime=tmp_path/'runtime with space';runtime.mkdir()
    (runtime/'host').write_text('#!/bin/sh\n');(runtime/'host').chmod(0o700)
    (runtime/'bridge-config.json').write_text(json.dumps({'extension_id':'a'*32,'download_root':str(tmp_path),'data_dir':str(tmp_path/'data')}))
    (runtime/'prepared.json').write_text(json.dumps({'owner':'paper-access-native-bridge-v1','runtime':str(runtime)}))
    target=tmp_path/'registration.json';target.write_text('{"name":"other"}')
    with pytest.raises(ValueError):install_prepared(runtime,target)
    target.unlink();install_prepared(runtime,target)
    assert json.loads(target.read_text())['allowed_origins']==['chrome-extension://'+'a'*32+'/']
    pdf=runtime/'keep.pdf';pdf.write_text('keep')
    uninstall_owned(runtime,target);assert pdf.exists();assert not target.exists()


def test_bad_id_and_missing_doctor(tmp_path):
    with pytest.raises(ValueError):validate_extension_id('x'*32)
    assert doctor(tmp_path/'missing')['installed'] is False


def test_prepare_rejects_symlink_download_root_before_creating_runtime(tmp_path):
    actual=tmp_path/'actual';actual.mkdir()
    alias=tmp_path/'downloads';alias.symlink_to(actual,target_is_directory=True)
    assert validate_download_root(actual)==actual
    destination=tmp_path/'runtime'
    with pytest.raises(ValueError,match='download_root_requires_canonical_path'):
        prepare_install(destination,'a'*32,alias)
    assert not destination.exists()


def test_doctor_rejects_existing_symlink_download_configuration(tmp_path):
    actual=tmp_path/'actual';actual.mkdir()
    alias=tmp_path/'downloads';alias.symlink_to(actual,target_is_directory=True)
    runtime=tmp_path/'runtime';runtime.mkdir()
    (runtime/'host').write_text('#!/bin/sh\n')
    (runtime/'prepared.json').write_text(json.dumps({'owner':'paper-access-native-bridge-v1','runtime':str(runtime)}))
    (runtime/'bridge-config.json').write_text(json.dumps({'extension_id':'a'*32,'download_root':str(alias),'data_dir':str(tmp_path/'data')}))
    result=doctor(runtime,tmp_path/'registration.json')
    assert result['installed'] is False
    assert result['reason']=='invalid_configuration'


def test_uninstall_remains_available_when_download_root_is_missing(tmp_path):
    downloads=tmp_path/'downloads';downloads.mkdir()
    runtime=tmp_path/'runtime';runtime.mkdir()
    (runtime/'host').write_text('#!/bin/sh\n')
    (runtime/'prepared.json').write_text(json.dumps({'owner':'paper-access-native-bridge-v1','runtime':str(runtime)}))
    (runtime/'bridge-config.json').write_text(json.dumps({'extension_id':'a'*32,'download_root':str(downloads),'data_dir':str(tmp_path/'data')}))
    target=tmp_path/'registration.json';install_prepared(runtime,target)
    downloads.rmdir()
    uninstall_owned(runtime,target)
    assert not target.exists()
    assert runtime.exists()

"""Inspect built installers and archives; never run apt or touch GPIO devices."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_builder',ROOT/'tools/build_release.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class ReleaseTests(unittest.TestCase):
    def test_both_editions_embed_only_exact_runtime_sources(self):
        for addon in (False,True):
            script=builder.installer(addon)
            self.assertEqual('PAYLOAD_GPIO_GERTBOARD_PY' in script,addon)
            for name in builder.runtime_names(addon):
                marker='PAYLOAD_'+name.upper().replace('.','_').replace('-','_')
                embedded=script.split("<<'"+marker+"'\n",1)[1].split('\n'+marker+'\n',1)[0]
                self.assertEqual(embedded.rstrip('\n'),(ROOT/name).read_text().rstrip('\n'))
            self.assertIn('/raspi-gpio-tool',script)
            self.assertIn('flock -n 9',script)
            self.assertLess(script.index('line_snapshot(chip)'),script.index('mv -f'))
            self.assertNotIn('smbpasswd',script)
            self.assertNotIn('systemctl',script)

    def test_archives_are_reproducible_with_valid_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            first=builder.build(Path(temp)/'a');second=builder.build(Path(temp)/'b')
            for left,right in zip(first,second):
                self.assertEqual(left.read_bytes(),right.read_bytes())
                with ZipFile(left) as archive:
                    names=archive.namelist();prefix=names[0].split('/')[0]+'/'
                    self.assertTrue(all('/.git/' not in n and not n.endswith('.pyc') for n in names))
                    for line in archive.read(prefix+'SHA256SUMS.txt').decode().splitlines():
                        expected,name=line.split('  ',1)
                        self.assertEqual(hashlib.sha256(archive.read(prefix+name)).hexdigest(),expected)

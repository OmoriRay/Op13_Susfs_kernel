"""Execute the production shell against an isolated simulated sysfs/procfs.

No real ZRAM, swap syscall, device, root module or boot partition is touched.
Fault injection verifies that failures cannot be logged as successful setup.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'modules/op13_memory'
FP = 'OnePlus/PJZ110/OP5D0DL1:17/CP2A.260605.016/V.487427a-2227f32-224bc4c:user/release-keys'
ZRAM = '/sys/block/zram0/'
HELPER = r'''
import os,sys
from pathlib import Path
r=Path(os.environ['OP13MEM_TEST_ROOT'])
def put(path,value):
 p=r/path.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(value)+'\n')
def get(path):return (r/path.lstrip('/')).read_text().strip()
def swap(enabled):
 put('/proc/swaps','Filename Type Size Used Priority\n'+('/dev/block/zram0 partition 12000000 0 32767' if enabled else ''))
 text=get('/proc/meminfo')
 import re
 text=re.sub(r'SwapTotal:\s*\d+ kB','SwapTotal: '+('12000000' if enabled else '0')+' kB',text)
 put('/proc/meminfo',text)
cmd=sys.argv[1:]
with (r/'commands').open('a') as f:f.write(' '.join(cmd)+'\n')
if Path(sys.argv[0]).name=='write-node':
 path,val=cmd;node=Path(path).name
 if (r/('fail-write-'+node)).exists():sys.exit(1)
 if node=='reset':
  put('/sys/block/zram0/disksize',0);put('/sys/block/zram0/initstate',0)
  put('/sys/block/zram0/comp_algorithm','lzo lzo-rle [lz4] lz4hc zstd')
 elif node=='comp_algorithm':
  put('/sys/block/zram0/comp_algorithm',' '.join('['+x+']' if x==val else x for x in ('lzo','lzo-rle','lz4','lz4hc','zstd')))
 else:
  put(path[len(str(r)):],val)
  if node=='disksize':put('/sys/block/zram0/initstate',1)
 sys.exit(0)
if cmd==['swapon','--help']:
 print('usage: swapon [-d] [-p priority] filename');sys.exit(0)
tool=cmd[0]
failure=r/('fail-once-'+tool)
if failure.exists():failure.unlink();sys.exit(1)
if (r/('fail-'+tool)).exists():sys.exit(1)
if tool=='swapon':
 if not (r/'header').exists():sys.exit(1)
 swap(True)
elif tool=='swapoff':swap(False)
elif tool=='mkswap':(r/'header').write_text('SWAPSPACE2')
else:sys.exit(2)
'''


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='op13mem-test-', dir='/tmp')
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, OP13MEM_TEST='1', OP13MEM_TEST_ROOT=str(self.root))
        self.put('/props/ro.product.model', 'PJZ110')
        self.put('/props/ro.product.device', 'OP5D0DL1')
        self.put('/props/ro.build.fingerprint', FP)
        self.put('/kernelrelease', '6.6.118-android15-8-test-4k')
        self.put('/proc/meminfo', 'MemTotal: 12000000 kB\nMemAvailable: 8000000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB')
        self.put('/proc/swaps', 'Filename Type Size Used Priority')
        self.put('/proc/uptime', '30.0 20.0')
        self.put('/proc/sys/kernel/random/boot_id', 'test-boot-1')
        self.put('/proc/self/mountinfo', '')
        for node, value in {'disksize': '8000000000', 'initstate': '1', 'mm_stat': '4096 64 20480 0 20480 0 0 0 0',
                            'comp_algorithm': 'lzo lzo-rle [lz4] lz4hc zstd', 'mem_limit': '0', 'recomp_algorithm': '',
                            'backing_dev': 'none'}.items():
            self.put(ZRAM + node, value)
        self.put('/sys/kernel/mm/lru_gen/min_ttl_ms', 0)
        for node, value in {'swappiness': 60, 'page-cluster': 3, 'watermark_scale_factor': 10}.items():
            self.put('/proc/sys/vm/' + node, value)
        for path in ('/write-node', '/system/bin/toybox'):
            f = self.put(path, '#!' + sys.executable + '\n' + HELPER)
            f.chmod(0o755)
        wrong = self.put('/wrong-tools/swapon', '#!/bin/sh\necho WRONG_BUSYBOX_APPLET >&2\nexit 90')
        wrong.chmod(0o755)
        self.env['PATH'] = str(wrong.parent) + ':' + os.environ['PATH']

    def tearDown(self):
        self.temp.cleanup()

    def put(self, path, value):
        p = self.root / path.lstrip('/')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(value) + '\n', encoding='utf-8')
        return p

    def text(self, path):
        return (self.root / path.lstrip('/')).read_text(encoding='utf-8')

    def run_script(self, script, *args, ok=True):
        r = subprocess.run(['/bin/sh', str(MODULE / script), *args], env=self.env, text=True, capture_output=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def status(self):
        return self.text('/data/adb/op13_memory/status.txt')

    def enable_existing(self, used=0):
        self.put('/header', 'SWAPSPACE2')
        self.put('/proc/swaps', f'Filename Type Size Used Priority\n/dev/block/zram0 partition 8000000 {used} 32758')
        self.put('/proc/meminfo', 'MemTotal: 12000000 kB\nMemAvailable: 8000000 kB\nSwapTotal: 8000000 kB\nSwapFree: 8000000 kB')

    def test_default_activates_real_swap_and_uses_absolute_toybox(self):
        self.run_script('memory.sh', 'boot')
        self.assertIn('state=active\n', self.status())
        self.assertEqual(self.text(ZRAM + 'disksize').strip(), '24576000000')
        self.assertIn('swapon -p 32767', self.text('/commands'))
        self.assertIn('zram0 partition', self.text('/proc/swaps'))
        self.assertEqual(self.text('/proc/sys/vm/swappiness').strip(), '100')
        self.assertIn('algo=zstd priority=1', self.text(ZRAM + 'recomp_algorithm'))

    def test_a_successful_command_without_active_swap_is_not_success(self):
        tool = self.root / 'system/bin/toybox'
        tool.write_text(tool.read_text().replace('swap(True)', 'pass # fake false-success'), encoding='utf-8')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('state=error-no-swap', self.status())

    def test_failed_swapon_restores_previous_capacity(self):
        self.put('/fail-once-swapon', '')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('state=recovered\n', self.status())
        self.assertEqual(self.text(ZRAM + 'disksize').strip(), '8000000000')
        self.assertIn('zram0 partition', self.text('/proc/swaps'))

    def test_mkswap_failure_is_not_ignored(self):
        self.put('/fail-mkswap', '')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('state=error-no-swap', self.status())
        self.assertNotIn('swapon -p', self.text('/commands'))

    def test_reset_failure_preserves_existing_capacity(self):
        self.put('/fail-write-reset', '')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertEqual(self.text(ZRAM + 'disksize').strip(), '8000000000')
        self.assertNotIn('mkswap', self.text('/commands'))

    def test_reset_failure_after_swapoff_reactivates_intact_old_header(self):
        self.enable_existing()
        self.put('/fail-write-reset', '')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('state=recovered\n', self.status())
        self.assertIn('zram0 partition', self.text('/proc/swaps'))
        self.assertNotIn('mkswap', self.text('/commands'))

    def test_no_repeated_reset_in_same_boot(self):
        self.run_script('memory.sh', 'boot')
        before = self.text('/commands')
        self.run_script('memory.sh', 'boot')
        self.assertEqual(before, self.text('/commands'))

    def test_active_busy_swap_is_adopted_without_swapoff(self):
        self.enable_existing(used=200000)
        self.run_script('memory.sh', 'boot')
        self.assertIn('state=adopted-existing\n', self.status())
        self.assertNotIn('swapoff', self.text('/commands'))
        self.assertEqual(self.text(ZRAM + 'disksize').strip(), '8000000000')

    def test_late_boot_never_resets_active_swap(self):
        self.enable_existing()
        self.put('/proc/uptime', '500.0 200.0')
        self.run_script('memory.sh', 'boot')
        self.assertIn('state=adopted-existing\n', self.status())
        self.assertNotIn('swapoff', self.text('/commands'))

    def test_early_low_use_swap_can_be_transitioned_once(self):
        self.enable_existing()
        self.run_script('memory.sh', 'boot')
        self.assertIn('state=active\n', self.status())
        self.assertIn('swapoff', self.text('/commands'))

    def test_swapoff_failure_does_not_reset(self):
        self.enable_existing()
        self.put('/fail-swapoff', '')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('state=blocked-swapoff', self.status())
        self.assertNotIn('/reset', self.text('/commands'))

    def test_wrong_device_is_blocked_before_memory_writes(self):
        self.put('/props/ro.product.model', 'another device')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('blocked-target-or-owner', self.status())
        self.assertFalse((self.root / 'commands').exists())

    def test_existing_backing_device_is_preserved(self):
        self.put(ZRAM + 'backing_dev', '/dev/block/sda99')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('blocked-target-or-owner', self.status())
        self.assertNotIn('/reset', self.text('/commands'))

    def test_config_is_not_executed_as_shell(self):
        self.put('/data/adb/op13_memory/profile', '$(touch /tmp/op13mem-test-injection)')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertFalse(Path('/tmp/op13mem-test-injection').exists())
        self.assertFalse((self.root / 'commands').exists())

    def test_density_profile_and_unsupported_algorithm(self):
        self.run_script('memory.sh', 'profile', 'density')
        self.assertFalse((self.root / 'commands').exists())
        self.put(ZRAM + 'comp_algorithm', 'lzo [lz4]')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('blocked-algorithm', self.status())

    def test_masked_sysctl_is_not_unmounted_or_overwritten(self):
        self.put('/proc/self/mountinfo', '9 8 0:1 / /proc/sys/vm/swappiness rw - tmpfs tmpfs rw')
        self.run_script('memory.sh', 'boot', ok=False)
        self.assertIn('blocked-masked-vm', self.status())
        self.assertNotIn('/reset', self.text('/commands'))

    def test_x1_guard_install_is_idempotent_and_remove_preserves_other_code(self):
        original = 'zram_apply() {\n echo zram\n}\nram_expand_apply() {\n echo ram\n}\nprivacy_apply() {\n echo keep-this\n}\n'
        file = self.put('/data/adb/modules/ox_op13_kernel_manager/ox/common.sh', original.rstrip('\n'))
        self.put('/data/adb/modules/ox_op13_kernel_manager/module.prop', 'version=2.13.0')
        self.run_script('x1-handoff.sh', 'install')
        patched = file.read_text()
        self.assertEqual(patched.count('# OP13MEM_OWNER_BEGIN'), 2)
        self.run_script('x1-handoff.sh', 'install')
        self.assertEqual(file.read_text(), patched)
        # Removing our blocks must preserve unrelated later edits.
        file.write_text(patched + '# user-later-edit\n')
        self.run_script('x1-handoff.sh', 'remove')
        self.assertEqual(file.read_text(), original + '# user-later-edit\n')

    def test_unknown_x1_version_is_not_patched(self):
        file = self.put('/data/adb/modules/ox_op13_kernel_manager/ox/common.sh', 'zram_apply() {\n :\n}')
        self.put('/data/adb/modules/ox_op13_kernel_manager/module.prop', 'version=99.0')
        before = file.read_bytes()
        self.run_script('x1-handoff.sh', 'install', ok=False)
        self.assertEqual(file.read_bytes(), before)

    def test_all_production_shell_files_parse(self):
        for file in MODULE.glob('*.sh'):
            subprocess.run(['/bin/sh', '-n', str(file)], check=True)


if __name__ == '__main__':
    unittest.main()

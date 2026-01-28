# Functionally equivelant to running:
#   efibootmgr --label 'Windows Boot Manager' --delete-bootnum
# but with an added sanity check which ensures there are only 0 or 1
# Windows Boot Manager entries

import sys, subprocess

DRY_RUN = any((i in sys.argv for i in ('-d', '--dryrun', '--dry-run'))) # or True
HEXCHARS = '0123456789ABCDEFabcdef'
BOOTMGFW_UEFI_NAME = 'Windows Boot Manager'

bootnum_for_windows_boot_manager = None
stdout = subprocess.check_output(['efibootmgr'])

for line in stdout.decode().splitlines():
  sp = line.split('\t')[0]
  maybe_a_bootnum = sp[:sp.index(' ')]
  if not maybe_a_bootnum.startswith('Boot'):
    continue # This line doesn't start with a bootnum

  maybe_a_bootnum = maybe_a_bootnum[4:]
  if maybe_a_bootnum.endswith('*'):
    maybe_a_bootnum = maybe_a_bootnum[:-1]
  if any(map(lambda c: c not in HEXCHARS, maybe_a_bootnum)):
    continue # This line doesn't start with a bootnum

  bootnum = maybe_a_bootnum
  entry_name = sp[sp.index(' '):].strip()
  if DRY_RUN:
    print('Found UEFI entry with name: ' + repr(entry_name) +
          ', bootnum: ' + repr(bootnum))
  if entry_name == BOOTMGFW_UEFI_NAME:
    if bootnum_for_windows_boot_manager is not None:
      raise Exception('Multiple ' + BOOTMGFW_UEFI_NAME + 'entries')
    bootnum_for_windows_boot_manager = bootnum

if bootnum_for_windows_boot_manager is not None:
  if DRY_RUN:
    print('Will remove ' + BOOTMGFW_UEFI_NAME + ' entry with bootnum:',
          repr(bootnum_for_windows_boot_manager))
  else:
    subprocess.run(['efibootmgr',
                    '--bootnum', bootnum_for_windows_boot_manager,
                    '--delete-bootnum'])
elif DRY_RUN:
  print('No ' + BOOTMGFW_UEFI_NAME + ' entry to remove. Doing nothing.')

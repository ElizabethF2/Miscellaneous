import sys, os, subprocess, random, tempfile, string, json

ID_CHARS = string.digits + string.ascii_lowercase
ID_LENGTH = 12 # NB: FreeBSD has a max username length of 16
USER_PREFIX = 'ubes'
TMPROOT_PREFIX = 'ubes_temp_root_'
GLOBAL_LOCK_NAME = 'ubes_global_lock'
PROC_LOCK_PREFIX = 'ubes_proc_lock_'
INTERNAL_FLAG_PREFIX = 'UBES_INTERNAL_SPROC_'

NET_USER_EXISTS = 2
NET_USER_NOT_FOUND = 2
USERDEL_USER_NOT_FOUND = 6

ENVIORNMENT_VARIABLE_ALLOWLIST = {
  'ALLUSERSPROFILE', 'APPDATA', 'COMMONPROGRAMFILES', 'COMMONPROGRAMW6432',
  'COMPUTERNAME', 'COMSPEC', 'DRIVERDATA', 'HOME', 'HOMEDRIVE', 'HOMEPATH',
  'LOCALAPPDATA', 'NUMBER_OF_PROCESSORS', 'OS', 'PATH', 'PATHEXT',
  'PROCESSOR_ARCHITECTURE', 'PROCESSOR_IDENTIFIER', 'PROCESSOR_LEVEL',
  'PROCESSOR_REVISION', 'PROGRAMDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
  'PROGRAMW6432', 'PROMPT', 'PSMODULEPATH', 'PUBLIC', 'SHELL', 'SYSTEMDRIVE',
  'SYSTEMROOT', 'TEMP', 'TMP', 'USERDOMAIN', 'USERPROFILE', 'WINDIR'
}

def get_lock_name(_global, name=None):
  if name is not None:
    return name
  if _global:
    return GLOBAL_LOCK_NAME
  else:
    return PROC_LOCK_PREFIX + str(os.getpid())

_locks = {}

def acquire_lock(_global=True, name=None, blocking=True):
  name = get_lock_name(_global, name = name)
  try:
    import fcntl, tempfile, errno
    fh = open(os.path.join(tempfile.gettempdir(), name), 'w')
    try:
      fcntl.lockf(fh, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
    except OSError as ex:
      if ex.errno in (errno.EACCES, errno.EAGAIN):
        return None
      raise ex
    _locks['fh:'+name] = fh
  except ModuleNotFoundError:
    import ctypes
    handle = ctypes.windll.kernel32.CreateMutexW(0, False, name.encode())
    if not handle:
      raise ctypes.WinError()
    r = ctypes.windll.kernel32.WaitForSingleObject(handle, INFINITE if blocking else 0)
    if r == WAIT_FAILED:
      raise ctypes.WinError()
    if r == WAIT_TIMEOUT:
      return None
    _locks['handle:'+name] = handle
  return name

def release_lock(_global=True, name=None):
  name = get_lock_name(_global, name = name)
  try:
    fh = _locks.pop('fh:' + name)
    fh.close()
  except KeyError:
    try:
      handle = _locks.pop('handle:' + name)
      if not ctypes.windll.kernel32.ReleaseMutex(handle):
        raise ctypes.WinError()
      if not ctypes.windll.kernel32.CloseHandle(handle):
        raise ctypes.WinError()
    except KeyError:
      return False
  return True

def lock_held(name):
  r = acquire_lock(name, blocking = False)
  if r is not None:
    release_lock(name)
  return (r is None)

def get_manifest_path():
  xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
  if xdg_config_home:
    return os.path.join(xdg_config_home, 'ubes', 'manifest.json')
  appdata = os.environ.get('APPDATA')
  if appdata:
    return os.path.join(appdata, 'ubes', 'manifest.json')
  path = os.path.join('~', '.config', 'ubes', 'manifest.json')
  return os.path.expanduser(path)

def read_manifest():
  path = get_manifest_path()
  try:
    with open(path, 'r') as f:
      return json.load(f)
  except (FileNotFoundError, json.JSONDecodeError):
    pass
  try:
    with open(path+'.old', 'r') as f:
      return json.load(f)
  except (FileNotFoundError, json.JSONDecodeError):
    return {}

def write_manifest(manifest):
  path = get_manifest_path()
  os.makedirs(os.path.dirname(path), exist_ok = True)
  try:
    os.remove(path+'.old')
  except FileNotFoundError:
    pass
  try:
    os.rename(path, path+'.old')
  except FileNotFoundError:
    pass
  with open(path, 'w') as f:
    json.dump(manifest, f)

def generate_id():
  sr = random.SystemRandom()
  return (''.join((sr.choice(ID_CHARS) for _ in range(ID_LENGTH))))

def create_tmproot():
  while True:
    _id = generate_id()
    tr = os.path.join(tempfile.gettempdir(), TMPROOT_PREFIX + _id)
    try:
      os.mkdir(tr)
      return _id, tr
    except FileExistsError:
      pass

def try_useradd(_id, tmproot):
  import shutil
  useradd = shutil.which('useradd')
  if not useradd:
    return None
  user = USER_PREFIX + _id
  subprocess.check_call((useradd, user))
  return user, None

def try_net_user_add(_id, tmproot):
  import shutil
  net = shutil.which('net')
  if not net:
    return None
  user = USER_PREFIX + _id
  password = generate_id()
  subprocess.check_output((net, 'user', user, password, '/add'))
  return user, password

def try_dscl_create(_id, tmproot):
  import shutil
  dscl = shutil.which('dscl')
  if not dscl:
    return None
  user = USER_PREFIX + _id
  subprocess.check_call((dscl, '.', '-create', '/Users/'+user))
  subprocess.check_call((dscl, '.', '-create', '/Users/'+user, 'UserShell', '/bin/bash'))
  subprocess.check_call((dscl, '.', '-create', '/Users/'+user, 'RealName', user))
  import pwd
  sr = random.SystemRandom()
  existing_ids = set((p.pw_uid for p in pwd.getpwall()))
  while True:
    uid = sr.randInt(2000, (2**16)-1)
    if uid not in existing_ids:
      break
  subprocess.check_call((dscl, '.', '-create', '/Users/'+user, 'UniqueID', str(uid)))
  EVERYONE = '12'
  subprocess.check_call((dscl, '.', '-create', '/Users/'+user, 'PrimaryGroupID', EVERYONE))
  subprocess.check_call((dscl, '.', '-create', '/Users/'+user, 'NFSHomeDirectory', tmproot))
  return user, None

def try_adduser(_id, tmproot):
  import shutil
  adduser = shutil.which('adduser')
  if not adduser:
    return None
  user = USER_PREFIX + _id
  subprocess.check_call((adduser, user))
  return user, None

def create_user(_id, tmproot):
  queue = []
  if sys.platform.startswith('linux'):
    queue.append(try_useradd)
  elif any((sys.platform.startswith(i) for i in ('win32', 'cygwin'))):
    queue.append(try_net_user_add)
  elif sys.platform.startswith('darwin'):
    queue.append(try_dscl_create)
  elif sys.platform.startswith('freebsd'):
    queue.append(try_adduser)
  for f in (try_adduser, try_net_user_add, try_dscl_create, try_adduser):
    if f not in queue:
      queue.append(f)
  for function in queue:
    result = function(_id, tmproot)
    if result is not None:
      return result
  raise RuntimeError('Unable to add user', _id)

def try_userdel(user):
  import shutil
  userdel = shutil.which('userdel')
  if not userdel:
    return None
  proc = subprocess.check_call((userdel, '-r', user))
  if proc.returncode != USERDEL_USER_NOT_FOUND:
    proc.check_returncode()
  return True

def try_net_user_delete(user):
  import shutil
  net = shutil.which('net')
  if not net:
    return None
  proc = subprocess.run((net, 'user', user, '/delete'),
                        capture_output = True)
  if proc.returncode != NET_USER_NOT_FOUND:
    proc.check_returncode()
  return True

def try_dscl_delete(user):
  import shutil
  dscl = shutil.which('dscl')
  if not dscl:
    return None
  subprocess.check_call((dscl, '.', '-delete', '/Users/'+user))
  return True

def try_rmuser(user):
  import shutil
  rmuser = shutil.which('rmuser')
  if not rmuser:
    return None
  subprocess.check_call((rmuser, '-y', user))
  return True

def remove_user(name):
  queue = []
  if sys.platform.startswith('linux'):
    queue.append(try_userdel)
  elif any((sys.platform.startswith(i) for i in ('win32', 'cygwin'))):
    queue.append(try_net_user_delete)
  elif sys.platform.startswith('darwin'):
    queue.append(try_dscl_delete)
  elif sys.platform.startswith('freebsd'):
    queue.append(try_rmuser)
  for f in (try_userdel, try_net_user_delete, try_dscl_delete, try_rmuser):
    if f not in queue:
      queue.append(f)
  for function in queue:
    result = function(name)
    if result is not None:
      return result
  raise RuntimeError('Unable to remove user', _id)

def chown(path, user):
  import shutil
  try:
    shutil.chown(path, user)
  except (LookupError, AttributeError):
    if os.name == 'nt':
      icacls = shutil.which('icacls')
      if icacls:
        subprocess.check_output((icacls, path, '/setowner', user, '/t'))
        subprocess.check_output((icacls, path, '/grant', user+':F', '/t'))

def create_sandbox(shared=[], pending_deletion_lock = None):
  acquire_lock()
  manifest = read_manifest()
  _cleanup(manifest, write_pending = True)
  _id, tmproot = create_tmproot()
  if _id in manifest:
    raise RuntimeError('duplicate sandbox', _id)
  manifest[_id] = {'tmproot': tmproot}
  if pending_deletion_lock is not None:
    manifest[_id]['pending_deletion_lock'] = pending_deletion_lock
  write_manifest(manifest)
  user, password = create_user(_id, tmproot)
  manifest[_id]['user'] = user
  manifest[_id]['password'] = password
  write_manifest(manifest)
  chown(tmproot, user)
  for s in sorted(
            map(lambda i: i.split(':'), shared),
            key = lambda i: i[0]):
    sp = s.split(':')
    ro = (len(sp) == 3 and sp[-1] == 'ro')
    share(manifest, manifest[_id], sp[0], sp[1], read_only = ro)
  release_lock()
  return manifest[_id]

def get_sandbox_path(sandbox, path):
  p = os.path.abspath(path)
  _, p = os.path.splitdrive(p)
  if p.startswith(os.path.sep):
    p = p[len(os.path.sep):]
  return os.path.join(sandbox['tmproot'], p)

def try_setfacl_add(user, path, read_only):
  import shutil, stat
  setfacl = shutil.which('setfacl')
  if not setfacl:
    return None
  st = os.stat(path)
  mask = 'u:'+user+':r'
  if not read_only:
    mask += 'w'
  if stat.S_IXUSR(st.st_mode):
    mask += 'x'
  subprocess.check_call((setfacl, '-R', '-m', mask, path))
  return True

def try_icacls_grant(user, path, read_only):
  import shutil
  icacls = shutil.which('icacls')
  if not icacls:
    return None
  perm = 'RX' if read_only else 'F'
  subprocess.check_output((icacls, path, '/grant', user+':'+perm, '/t'))
  return True

def try_chmod_add(user, path, read_only):
  import shutil, stat
  chmod = shutil.which('chmod')
  if not chmod:
    return None
  st = os.stat(path)
  perms = user+' allow read,readattr,readextattr,readsecurity,'
  if stat.S_ISDIR(st.st_mode):
    perms += 'list,search,'
  else:
    perms += 'read,'
  if not read_only:
    perms += 'delete,writeattr,writeextattr,writesecurity,chown,'
    if stat.S_ISDIR(st.st_mode):
      perms += 'add_file,add_subdirectory,delete_child,'
    else:
      perms += 'write,append,'
  if stat.S_IXUSR(st.st_mode):
    perms += 'execute,'
  perms += 'file_inherit,directory_inherit'
  subprocess.check_call((cmod, '+a', perms, path))

def try_setfacl_remove(user, path):
  import shutil
  setfacl = shutil.which('setfacl')
  if not setfacl:
    return None
  subprocess.run((setfacl, '-R', '-x', 'u:'+user, path))
  return True

def try_icacls_remove(user, path):
  import shutil
  icacls = shutil.which('icacls')
  if not icacls:
    return None
  subprocess.run((icacls, path, '/remove', user, '/t'))
  return True

def try_chmod_remove(user, path, read_only):
  import shutil, stat
  chmod = shutil.which('chmod')
  if not chmod:
    return None
  perms = (
    'read,readattr,readextattr,readsecurity,file_inherit,directory_inherit',
    'list,search',
    'read',
    'delete,writeattr,writeextattr,writesecurity,chown',
    'add_file,add_subdirectory,delete_child',
    'write,append',
    'execute',
  )
  for perm in perms:
    subprocess.run((cmod, '-a', user+' allow '+perm, path))

def share(manifest, sandbox, src, dst, read_only = True):
  src = os.path.abspath(src)
  modes = (os.R_OK, os.X_OK) if read_only else (os.R_OK, os.X_OK, os.W_OK)
  if any((not os.access(src, mode) for mode in modes)):
    return
  sandbox.setdefault('shared', []).append(src)
  write_manifest(manifest)
  queue = []
  if sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
    queue.append(try_setfacl_add)
  elif any((sys.platform.startswith(i) for i in ('win32', 'cygwin'))):
    queue.append(try_icacls_grant)
  elif sys.platform.startswith('darwin'):
    queue.append(try_chmod_add)
  for f in (try_setfacl_add, try_icacls_grant, try_chmod_add):
    if f not in queue:
      queue.append(f)
  user = sandbox['user']
  for function in queue:
    result = function(user, src, read_only)
    if result is not None:
      return result
  raise RuntimeError('Unable to add ACL', user, src)
  os.symlink(src, get_sandbox_path(dst))

def unshare(sandbox, path):
  queue = []
  if sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
    queue.append(try_setfacl_remove)
  elif any((sys.platform.startswith(i) for i in ('win32', 'cygwin'))):
    queue.append(try_icacls_remove)
  elif sys.platform.startswith('darwin'):
    queue.append(try_chmod_remove)
  for f in (try_setfacl_add, try_icacls_grant, try_chmod_remove):
    if f not in queue:
      queue.append(f)
  user = sandbox['user']
  for function in queue:
    result = function(user, path)
    if result is not None:
      return result
  raise RuntimeError('Unable to remove ACL', user, path)

def tmproot_to_id(tmproot):
  return os.path.basename(tmproot)[len(TMPROOT_PREFIX):]

def get_sandbox(_id, pending_deletion_lock = None):
  acquire_lock()
  manifest = read_manifest()
  _cleanup(manifest)
  breakpoint()
  sandbox = manifest[_id]
  if 'pending_deletion_lock' in sandbox:
    internal_flag = INTERNAL_FLAG_PREFIX + _id
    if internal_flag not in os.environ:
      raise ValueError('Cannot get sandbox pending deletion', _id)
  if pending_deletion_lock is not None:
    sandbox['pending_deletion_lock'] = pending_deletion_lock
    write_manifest(manifest)
  release_lock()
  return sandbox

def _remove_sandbox(sandbox):
  import shutil
  try:
    shutil.rmtree(sandbox['tmproot'])
  except FileNotFoundError:
    pass
  for s in sandbox.setdefault('shared', []):
    unshare(sandbox, s)
  user = sandbox.get('user')
  if user:
    remove_user(sandbox['user'])

def remove_sandbox(sandbox):
  _remove_sandbox(sandbox)
  _id = tmproot_to_id(sandbox['tmproot'])
  acquire_lock()
  manifest = read_manifest()
  manifest.pop(_id)
  write_manifest(manifest)
  release_lock()

def _cleanup(manifest, write_pending=False):
  ids_to_remove = []
  for _id, sandbox in manifest.items():
    pending_deletion_lock = sandbox.get('pending_deletion_lock')
    if ((pending_deletion_lock and not lock_held(pending_deletion_lock)) or
        not os.path.exists(sandbox['tmproot'])):
      ids_to_remove.append(_id)
  for _id in ids_to_remove:
    _remove_sandbox(manifest.pop(_id))
  if not write_pending and len(ids_to_remove) > 0:
    write_manifest(manifest)

def cleanup():
  acquire_lock()
  manifest = read_manifest()
  _cleanup(manifest)
  release_lock()

def make_env(sandbox, custom_env=None):
  new_env = {}
  for key, value in os.environ.items():
    if key.upper() in ENVIORNMENT_VARIABLE_ALLOWLIST:
      new_env[key] = value
  if custom_env is not None:
    new_env.update(custom_env)
  return new_env

def try_sudo(sandbox, proc_args, cwd=None, env=None):
  import shutil
  sudo = shutil.which('sudo')
  if not sudo:
    return None
  return subprocess.run((sudo, '-u', sandbox['user']) + proc_args,
                        cwd = cwd,
                        env = env)

def try_doas(sandbox, proc_args, cwd=None, env=None):
  import shutil
  doas = shutil.which('doas')
  if not doas:
    return None
  return subprocess.run((doas, '-u', sandbox['user']) + proc_args,
                        cwd = cwd,
                        env = env)

def try_runuser(sandbox, proc_args, cwd=None, env=None):
  import shutil
  runuser = shutil.which('runuser')
  if not runuser:
    return None
  return subprocess.run((runuser, '-u', sandbox['user'], '-l', '--') +
                        proc_args,
                        cwd = cwd,
                        env = env)

def make_completed_process(proc):
  ret = proc.wait()
  return subprocess.CompletedProcess(args = proc.args,
                                     returncode = ret)

def try_powershell(sandbox, proc_args, cwd=None, env=None):
  import shutil, shlex
  powershell = shutil.which('powershell')
  if not powershell:
    return None
  n = 'Z'+generate_id()
  p  = '$s=ConvertTo-SecureString -String $env:'+n+' -AsPlainText -Force;'
  p += '$env:'+n+'=0;'
  p += '$c=New-Object -Type PSCredential("{}",$s);'.format(sandbox['user'])
  p += 'exit (Start-Process -Credential $c'
  p += ' -FilePath {}'.format(repr(proc_args[0]))
  if len(proc_args) > 1:
    p += ' -ArgumentList {}'.format(repr(shlex.join(proc_args[1:])))
  p += ' -NoNewWindow -PassThru -Wait).ExitCode'
  penv = {k:v for k,v in (env or {}).items()}
  penv[n] = sandbox['password']
  pcwd = sandbox['tmproot'] if cwd is None else cwd
  return subprocess.run((powershell, '-c', p), cwd = pcwd, env = penv)

def run_with_existing_sandbox(sandbox, proc_args, cwd=None, env=None):
  _id = tmproot_to_id(sandbox['tmproot'])
  internal_flag = INTERNAL_FLAG_PREFIX + _id
  if internal_flag in os.environ:
    env = make_env(sandbox, env)
    queue = (try_sudo, try_doas, try_runuser, try_powershell)
    args = tuple(proc_args)
    for function in queue:
      result = function(sandbox, args, cwd = cwd, env = env)
      if result is not None:
        sys.exit(result.returncode)
  else:
    a = [sys.executable, __file__, '-r', sandbox['tmproot']]
    eargs = ['-e '+k+'='+'v' for k, v in (env or {}).items()]
    env = make_env(sandbox, env)
    env[internal_flag] = json.dumps({'user': sandbox['user'],
                                     'password': sandbox['password']})
    return subprocess.run(a + eargs + proc_args, cwd = cwd, env = env)

def run(proc_args, cwd=None, env=None, shared=None, root=None, keep=False):
  if keep:
    _pending_deletion_lock = None
  else:
    _pending_deletion_lock = acquire_lock(False)

  if root is None:
    sandbox = create_sandbox(shared=shared,
                             pending_deletion_lock=_pending_deletion_lock)
    root = sandbox['tmproot']
  else:
    _id = tmproot_to_id(root)
    internal_flag = os.environ.get(INTERNAL_FLAG_PREFIX + _id)
    if internal_flag:
      sandbox = json.loads(internal_flag)
      sandbox['tmproot'] = root
    else:
      sandbox = get_sandbox(_id,
                            pending_deletion_lock=_pending_deletion_lock)

  if proc_args:
    proc = run_with_existing_sandbox(sandbox,
                                     proc_args,
                                     cwd = cwd,
                                     env = env)
    if not keep:
      remove_sandbox(sandbox)
  else:
    proc = None

  if _pending_deletion_lock is not None:
    release_lock(False)

  return proc, sandbox


def main():
  import argparse
  parser = argparse.ArgumentParser(prog='PROG')
  parser.add_argument('command',
                      nargs='+',
                      help='the command to be run and its arguments')
  parser.add_argument('-k',
                      '--keep',
                      action=argparse.BooleanOptionalAction,
                      help='keep the sandbox after exiting')
  parser.add_argument('-r',
                      '--root',
                      help='use the sandbox with the given root instead of making a new sandbox')
  parser.add_argument('-v',
                      '--volume',
                      action='append',
                      default=[],
                      help='(repeatable) map a local path into the sandbox')
  parser.add_argument('-e',
                      '--env',
                      action='append',
                      default=[],
                      help='(repeatable) set an environment variable')
  parser.add_argument('-w',
                      '--cwd',
                      help='set the working directory')
  args = parser.parse_args()

  env = {k:'='.join(v) for k, *v in map(lambda e: e.split('='), args.env)}
  proc, sandbox = run(args.command,
                      cwd = args.cwd,
                      env = env,
                      shared = args.volume,
                      root = args.root,
                      keep = args.keep)

  if proc is None:
    print(sandbox['tmproot'])
  else:
    sys.exit(proc.returncode)

if __name__ == '__main__':
  main()

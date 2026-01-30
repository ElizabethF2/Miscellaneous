#!/usr/bin/env python3

import sys, os, subprocess, shlex, shutil, fnmatch, time, tomllib, json

HELP_TEXT = '''
Usage:
  --sync-all or -a                    Sync all repos
  --sync REPONAME or -s REPONAME      Sync just REPONAME
  --no-pull-sync REPONAME             Sync just REPONAME without pulling remote
    or -n REPONAME                    changes
  --procfile or -p                    Run the 'release' process type for a
                                      Procfile called Procfile
  --procfile PATH or -p PATH          Run the 'release' process type for a
                                      Procfile at PATH
  --procfile PATH PROCESS_TYPE        Run the given PROCESS_TYPE for a Procfile
    or -p PATH PROCESS_TYPE           at PATH
  --help or -h                        Show this help text
'''.lstrip()

DEFAULTS = {
  'branch': None,
  'procfile': None,
  'procfile_process_type': 'release',
  'sync_trigger_interval': 0,
  'sandbox': True,
  'sandbox_networking': False,
  'no_pull': False,
}

class Context(object): ...

def die(error):
  sys.stderr.write(f'{error}'.strip() + '\n')
  sys.stderr.flush()
  sys.exit(1)

def get_state_dir():
  state_home = os.environ.get('XDG_STATE_HOME')
  if not state_home:
    state_home = os.environ.get('LOCALAPPDATA')
  if not state_home:
    state_home = os.path.expanduser(os.path.join('~', '.local', 'state'))
  return os.path.join(state_home, 'git_mirror_sync')

def log(ctx, *args):
  lines = ' '.join(map(str, args)).splitlines()
  prefix = time.strftime('%c {}').format(repr(getattr(ctx, 'repo', None)))
  pid = os.getpid()
  if not (fh := getattr(ctx, 'log_fh', None)):
    log_path = ctx.config.get('log_path')
    if not log_path:
      log_path = os.path.join(get_state_dir(), 'log.txt')
      os.makedirs(os.path.dirname(log_path), exist_ok = True)
    ctx.log_fh = fh = open(log_path, 'a')
  for line in lines:
    fh.write('[{} {}] {}\n'.format(prefix, pid, line))
  for line in lines:
    print('[{}] {}'.format(prefix, line))

def get_config_path():
  if path := os.environ.get('GIT_MIRROR_SYNC_CONFIG'):
    return path
  config_home = os.environ.get('XDG_CONFIG_HOME')
  if not config_home:
    config_home = os.environ.get('APPDATA')
  if not config_home:
    config_home = os.path.expanduser(os.path.join('~', '.config'))
  return os.path.join(config_home, 'git_mirror_sync.toml')

def load_config(ctx):
  with open(get_config_path(), 'rb') as f:
    ctx.config = tomllib.load(f)

def get_state_path(ctx):
  if not (path := ctx.config.get('state_path')):
    path = os.path.join(get_state_dir(), 'state.json')
  return path

def load_state(ctx):
  if (state := getattr(ctx, 'state_on_disk', None)) is not None:
    return state
  try:
    with open(get_state_path(ctx), 'r') as f:
      ctx.state_on_disk = state = json.load(f)
  except FileNotFoundError:
    ctx.state_on_disk = state = {}
  return state

def get_last_sync(ctx, repo_name):
  return load_state(ctx).get('last_syncs', {}).get(repo_name, 0)

def update_state(ctx, new_sync_times):
  if set(ctx.config.get('repos', {}).keys()) == set(new_sync_times.keys()):
    old_state = {'last_syncs': {}}
  else:
    old_state = load_state(ctx)
  new_state = {'last_syncs': old_state.get('last_syncs', {}) | new_sync_times}
  if new_state != old_state:
    with open(get_state_path(ctx), 'w') as f:
      json.dump(new_state, f)

def get_cache_dir(ctx):
  if path := ctx.config.get('cache_dir'):
    return path
  cache_home = os.environ.get('XDG_CACHE_HOME')
  if not cache_home:
    cache_home = os.path.expanduser(os.path.join('~', '.cache'))
  return os.path.join(cache_home, 'git_mirror_sync')

def take_snapshot(root, excluded_paths, renames = None):
  snapshot = {}
  queue = ['']
  while len(queue) > 0:
    current = queue.pop()
    full_current = os.path.join(root, current)
    try:
      with os.scandir(full_current) as it:
        for entry in it:
          relpath = os.path.join(current, entry.name)
          if any((fnmatch.fnmatch(relpath, i) for i in excluded_paths)):
            continue
          if entry.is_dir():
            queue.append(relpath)
          metadata = {'mtime': entry.stat().st_mtime}
          if renames is not None:
            relpath = renames.get(relpath, relpath)
            if entry.is_file():
              metadata['source'] = entry.path
          snapshot[relpath] = metadata
    except NotADirectoryError:
      fp = os.path.dirname(full_current)
      relpath = os.path.join(current, '')
      if not any((fnmatch.fnmatch(relpath, i) for i in excluded_paths)):
        metadata = {'mtime': os.path.getmtime(fp)}
        if renames is not None:
          relpath = renames.get(relpath, relpath)
          metadata['source'] = fp
        snapshot[relpath] = metadata
    except FileNotFoundError:
      pass
  return snapshot

def parse_procfile(path):
  with open(path, 'r') as f:
    return dict(
      __import__('re').findall(r'(?m)^([A-Za-z0-9_]+):\s*(.+)$', f.read())
    )

def get_procfile_command(path, process_type = None):
  if process_type is None:
    process_type = DEFAULTS['procfile_process_type']
  if (cmd := parse_procfile(path).get(process_type)) is None:
    die(f'No process type {repr(process_type)} in procfile {repr(path)}')
  return shlex.split(cmd)

def sync_changes_from_source(ctx, r):
  destination_snapshot = take_snapshot(r.destination,
                                       {'.git'} | r.kept_paths)
  if not hasattr(r, 'source'):
    return False, destination_snapshot
  source_snapshot = take_snapshot(r.source, r.excluded_paths, r.renames)
  if '' not in source_snapshot and not r.urls:
    os.makedirs(r.destination, exist_ok = True)
  repo_modified = False
  for relpath in sorted(source_snapshot.keys(), key = len):
    source_metadata = source_snapshot[relpath]
    destination_metadata = destination_snapshot.get(relpath, {})
    destination_path = (os.path.join(r.destination, relpath)
                        if relpath else r.destination)
    entity_modified = False
    if (source_path := source_metadata.get('source')) is not None:
      with open(source_path, 'rb') as f:
        source_data = f.read()
      for pattern, repl in r.substitutions.items():
        source_data = __import__('re').sub(pattern, repl, source_data)
      if 'mtime' in destination_metadata:
        with open(destination_path, 'rb') as f:
          destination_data = f.read()
      else:
        destination_data = None
      if source_data != destination_data:
        with open(destination_path, 'wb') as f:
          f.write(source_data)
        entity_modified = True
      destination_metadata['data'] = source_data
    elif destination_metadata.get('mtime') is None:
      os.mkdir(destination_path)
      entity_modified = True
    source_mtime = source_metadata['mtime']
    if source_mtime != destination_metadata.get('mtime'):
      os.utime(destination_path, (source_mtime, source_mtime))
      entity_modified = True
    destination_metadata['mtime'] = source_mtime
    if entity_modified:
      git_add(ctx, r.destination, relpath)
      repo_modified = True
    destination_snapshot[relpath] = destination_metadata
  for relpath in sorted(destination_snapshot.keys(), key = len, reverse = True):
    if relpath not in source_snapshot:
      git(ctx, r.destination, 'rm', relpath)
      repo_modified = True
      destination_snapshot.pop(relpath, 0)
  return repo_modified, destination_snapshot

def log_process_output(ctx, proc):
  while True:
    if not (line := proc.stdout.readline()):
      break
    try:
      line = line.decode().strip()
    except UnicodeDecodeError:
      line = repr(line)
    log(ctx, '  ' + line)
  return proc.wait()

def git(ctx, cwd, *args, capture = True, check = True):
  cfg = []
  for k,v in ctx.config.get('git_config', {}).items():
    cfg += ['-c', k+'='+v]
  kwargs = ({'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT}
            if capture else {})
  proc = subprocess.Popen(['git', *cfg, *args], cwd = cwd, **kwargs)
  rc = log_process_output(ctx, proc) if capture else proc.wait()
  if check and rc != 0:
    log(ctx, err := f'Unexpected return code: {proc}')
    log(ctx, f'Full Command: {repr(proc.args)}')
    raise Exception(err)
  return rc

def git_add(ctx, cwd, relpath):
  if relpath == '':
    relpath = os.path.basename(cwd)
    cwd = os.path.dirname(cwd)
  return git(ctx, cwd, 'add', relpath)

def sync_internal(ctx, repo_name, repo_cfg):
  ctx.repo = repo_name
  log(ctx, 'loading config for repo')
  r = Context()
  for k,v in DEFAULTS.items():
    setattr(r, k, repo_cfg.get(k, ctx.config.get(k, v)))
  for i in ('excluded_paths', 'kept_paths', 'commands', 'scripts',
            'sandbox_read_only_paths', 'sandbox_read_write_paths'):
    setattr(r, i, set(repo_cfg.get(i, []) + ctx.config.get(i, [])))
  for i in ('substitutions', 'renames'):
    setattr(r, i, ctx.config.get(i, {}) | repo_cfg.get(i, {}))
  for i in ('source', 'git_dir'):
    if (v := repo_cfg.get(i)) is not None:
      setattr(r, i, os.path.expanduser(v))
  r.urls = repo_cfg.get('urls', [])
  if (v := repo_cfg.get('url')) is not None:
    r.urls.insert(0, v)
  for i in ('destination',):
    if (v := repo_cfg.get(i)) is None:
      die('Missing or empty value for {} in {}'.format(i, repo_name))
    setattr(r, i, os.path.expanduser(v))
  r.substitutions = {k.encode(): v.encode() for k,v in r.substitutions.items()}
  if r.urls:
    if os.path.exists(r.destination):
      if not r.no_pull:
        log(ctx, 'pulling changes')
        git(ctx, r.destination, 'pull')
    else:
      log(ctx, 'cloning repo')
      dest_parent = os.path.dirname(r.destination)
      os.makedirs(dest_parent, exist_ok = True)
      git(ctx, dest_parent, 'clone', r.urls[0], r.destination)
      log(ctx, 'set origin')
      git(ctx, r.destination, 'add', 'origin', r.urls[0], check = False)
  if r.branch is not None:
    log(ctx, f'switching to branch {repr(r.branch)}')
    git(ctx, r.destination, 'checkout', '-b', r.branch)
  log(ctx, 'checking for local changes')
  repo_modified, _ = sync_changes_from_source(ctx, r)
  timestamp = time.time()
  if not repo_modified:
    if (timestamp - get_last_sync(ctx, repo_name)) < r.sync_trigger_interval:
      return None
  dirs_to_try_deleting_before_moving_back_paths = []
  paths_to_move_back = {}
  dirs_to_try_deleting_after_moving_back_paths = []
  try:
    if r.sandbox and (r.commands or r.scripts or r.procfile):
      cache_dir = get_cache_dir(ctx)
      if not os.path.isdir(cache_dir):
        os.makedirs(cache_dir, exist_ok = True)
        dirs_to_try_deleting_after_moving_back_paths.append(cache_dir)
      git_dirs = os.path.join(cache_dir, 'git_dirs')
      try:
        os.mkdir(git_dirs)
        dirs_to_try_deleting_after_moving_back_paths.append(git_dirs)
      except FileExistsError:
        pass
      os.mkdir(repo_cache_dir := os.path.join(git_dirs, repo_name))
      dirs_to_try_deleting_after_moving_back_paths.append(repo_cache_dir)
      src = os.path.join(destination, '.git')
      dst = os.path.join(repo_cache_dir, '.git')
      path_to_move_back[dst] = src
      shutil.move(src, dst)
      dirs_to_try_deleting_before_moving_back_paths.append(src)

      import sandboxpy
      r.sandbox_read_write_paths.add(destination)
      if len(r.scripts) > 0:
        python_ro_paths = (set(sandboxpy.get_python_paths()) +
                           r.sandbox_read_only_paths)
    elif len(r.scripts) > 0:
      python_ro_paths = r.sandbox_read_only_paths
    commands = [(shlex.split(i),
                 r.sandbox_read_only_paths, r.sandbox_read_write_paths)
                for i in r.commands]
    for script in r.scripts:
      commands.append(((sys.executable, script),
                       python_ro_paths, r.sandbox_read_write_paths))
    if r.procfile:
      commands.append((get_procfile_command(procfile, r.procfile_process_type),
                       r.sandbox_read_only_paths, r.sandbox_read_write_paths))

    if len(commands) > 0:
      ci_env = {
        'CI': 'true',
        'GIT_MIRROR_SYNC_DST_DIR': os.path.abspath(r.destination),
        'GIT_MIRROR_SYNC_NAME': repo_name,
        'GIT_MIRROR_SYNC_CFG': get_config_path(),
      }
      if hasattr(r, 'source'):
        ci_env['GIT_MIRROR_SYNC_SRC_DIR'] = os.path.abspath(r.source)
      kwargs = {
        'cwd': r.destination,
        'env': os.environ | ci_env,
      }
      old_snapshot = take_snapshot(r.destination, ())
      for command, ro_paths, rw_paths in commands:
        log(f'Running: {repr(command)}')
        if sandbox:
          proc = sandboxpy.run(command,
                               readable_paths = ro_paths,
                               writable_paths = rw_paths,
                               allow_networking = sandbox_networking,
                               **kwargs)
        else:
          proc = subprocess.Popen(command,
                                  stdout = subprocess.PIPE,
                                  stderr = subprocess.STDOUT,
                                  **kwargs)
        rc = log_process_output(proc)
        log(ctx, f'Finished running with a return code of {rc}')
      new_snapshot = take_snapshot(r.destination, ())
  finally:
    for i in reversed(dirs_to_try_deleting_before_moving_back_paths):
      try:
        shutil.rmtree(i)
      except FileNotFoundError:
        pass
    for src, dst in paths_to_move_back.items():
      shutil.move(src, dst)
    try:
      for i in reversed(dirs_to_try_deleting_after_moving_back_paths):
        os.rmdir(i)
    except OSError:
      pass

  if len(commands) > 0:
    for relpath in sorted(new_snapshot.keys(), reverse = True):
      if new_snapshot[relpath] != old_snapshot.get(relpath, {}):
        git_add(ctx, r.destination, relpath)
    for relpath in sorted(old_snapshot.keys(), reverse = True):
      if relpath not in new_snapshot:
        git(ctx, r.destination, 'rm', relpath)

  if r.urls:
    rc = git(ctx, r.destination, 'diff', '--staged', '--quiet', check = False)
    if rc == 0:
      return None

    git(ctx, r.destination, 'status')

    while True:
      print('')
      print('Mirror:', r.destination)
      print('Proceed with commit? (Y)es / (N)o / (V)iew diff')
      inp = input('> ').lower()
      if (inp == 'v'):
        git(ctx, r.destination, 'diff', '--cached', capture = False)
      elif (inp != 'y'):
        die('Aborted!')
      else:
        break

    log(ctx, f'Committing changes')
    git(ctx, r.destination, 'commit', capture = False)

    print('')
    print('Proceed with push? (y/n)')
    if (input('> ').lower() != 'y'):
      die('Aborted!')
    log(ctx, f'Pushing changes')
    for url in r.urls:
      branch = () if r.branch is None else (r.branch,)
      git(ctx, r.destination, 'push', url, *branch)

  return timestamp

def sync_one_repo(repo_name, pull_changes = True):
  ctx = Context()
  load_config(ctx)
  if not (repo_cfg := ctx.config.get('repos', {}).get(repo_name)):
    die(f'Invalid repo: {repr(repo_name)}')
  if not pull_changes:
    repo_cfg['no_pull'] = True
  sync_time = sync_internal(ctx, repo_name, repo_cfg)
  if sync_time is not None:
    update_state(ctx, {repo_name: sync_time})

def sync_all_repos():
  ctx = Context()
  load_config(ctx)
  new_sync_times = {}
  repos = ctx.config.get('repos', {})
  log(ctx, 'Found {} repo(s) in config'.format(len(repos)))
  for repo_name, repo_cfg in repos.items():
    sync_time = sync_internal(ctx, repo_name, repo_cfg)
    if sync_time is not None:
      new_sync_times[repo_name] = sync_time
  update_state(ctx, new_sync_times)

def main():
  try:
    with open('/proc/self/comm', 'r+') as f:
      f.write('git_mirror_sync')
  except (FileNotFoundError, PermissionError):
    pass
  args = dict(enumerate(sys.argv[1:]))
  if args.get(0) in ('-a', '--sync-all'):
    if len(args) > 1:
      die('Too many arguments')
    return sync_all_repos()
  if args.get(0) in ('-s', '--sync'):
    if (repo_name := args.get(1)) is None:
      die('No repo name given\n\n' + HELP_TEXT)
    if len(args) > 2:
      die('Too many arguments')
    return sync_one_repo(repo_name)
  if args.get(0) in ('-n', '--no-pull-sync'):
    if (repo_name := args.get(1)) is None:
      die('No repo name given\n\n' + HELP_TEXT)
    if len(args) > 2:
      die('Too many arguments')
    return sync_one_repo(repo_name, pull_changes = False)
  if args.get(0) in (None, '-h', '--help'):
    return print(HELP_TEXT)
  if args.get(0) in ('-p', '--procfile'):
    if len(ags) > 3:
      die('Too many arguments')
    path = args.get(1, 'Procfile')
    process_type = args.get(2, DEFAULTS['procfile_process_type'])
    rc = subprocess.run(get_procfile_command(path, process_type)).returncode
    sys.exit(rc)
  die('Invalid argument(s)')

if __name__ == '__main__':
  main()

#!/usr/bin/env python3

import sys, os, io, time, subprocess, shlex, shutil, json, functools

# TODO CharonRMM status, parse ReflectiveNAS log for messages
# TODO btrfs scrub and balance

STATE_PATH = '~/.local/state/do_all_the_things.json'
SESSION_NAME = 'datt'

ONE_HOUR = 60*60
ONE_DAY = 24*ONE_HOUR

PERIODS = {
  'lincfg_online': 26 * ONE_HOUR,
  'game_release_checker': 16 * ONE_HOUR,
  'price_checker_full': 5 * ONE_DAY,
  'price_checker_fast_insane': 16 * ONE_HOUR,
  'healthcheck': 7 * ONE_DAY,
  'git_mirror_sync': 3 * ONE_DAY,
}

COMM_NAMES = {
  'game_release_checker': 'release_checker',
}

SAME_TAB_ACTIONS = {'lincfg_offline', 'lincfg_online', 'prbsync_sync'}

is_remote = '--remote' in sys.argv
show_next = '-n' in sys.argv or '--next' in sys.argv

def apply_enqueue_rules(ctx):
  if is_remote:
    enqueue(ctx, 'lincfg_offline', 'lincfg -o')
  else:
    enqueue_if_due(ctx, 'lincfg_online', 'lincfg') or \
    enqueue(ctx, 'lincfg_offline', 'lincfg -o')

  enqueue_if_due(ctx, 'game_release_checker', 'game_release_checker')

  enqueue_if_due(ctx, 'price_checker_full', 'price_checker pcx') or \
  enqueue_if_due(ctx, 'price_checker_fast_insane', 'price_checker fnx')

  enqueue_if_due(ctx, 'healthcheck', 'healthcheck')

  if not is_remote:
    enqueue_if_due(ctx, 'git_mirror_sync', 'git_mirror_sync --sync-all')

  if is_remote:
    ctx['pending_actions'].append(('prbsync_sync', 'prbsync auto'))
  if not is_remote or show_next:
    try_set_comm('datt_check_sync')
    print('Checking PRBSync...')
    proc = subprocess.Popen(('prbsync', 'tail_log_and_json_query'),
                            stdout = subprocess.PIPE)
    while line := proc.stdout.readline().decode().strip():
      print(line)
    state = json.loads(proc.stdout.read())
    if validate_prbsync_state(ctx, state).get('sync_due') and not is_remote:
      ctx['pending_actions'].append(('prbsync_sync', 'prbsync sync'))

VALID_PRBSYNC_PATHS_THAT_SHOULD_BE_HYDRATED = (
  {'GDrive', 'OneDrive'},
)

def validate_prbsync_state(ctx, state):
  hydrated_paths = set(filter(state['is_hydrated'].get,
                              state['is_hydrated'].keys()))
  if hydrated_paths not in VALID_PRBSYNC_PATHS_THAT_SHOULD_BE_HYDRATED:
    raise Exception(f'Some paths need hydration! {hydrated_paths}')
  print('PRBSync Due:', state.get('sync_due', 'Unknown'))
  print('')
  return ctx.setdefault('prbsync_state', state)

@functools.cache
def which(cmd):
  if path := os.environ.get('PATH'):
    path = path.split(os.pathsep)
  if (xdg_bin := os.path.expanduser('~/.local/bin')) not in path:
    path.append(xdg_bin)
  return shutil.which(cmd, path = os.pathsep.join(path))

def enqueue(ctx, name, cmd):
  csp = shlex.split(cmd)
  if not which(csp[0]):
    print('NOTICE: Skipping {}'.format(name))
    return False
  ctx['pending_actions'].append((name, cmd))
  return True

def enqueue_if_due(ctx, name, cmd):
  next = ctx['state'].get('last_' + name, 0) + PERIODS[name]
  ctx.setdefault('next', {})[name] = next
  if ctx['now'] >= next:
    return enqueue(ctx, name, cmd)
  return False

# NB: no thread safety when handling state file and tmux session
#     assumes that each command can safely handle concurrency and that
#     running a command too soon won't cause catastrophic issues

def load_state():
  state_path = os.path.expanduser(STATE_PATH)
  try:
    with open(state_path, 'r') as f:
      state = json.load(f)
  except (FileNotFoundError, json.decoder.JSONDecodeError):
    state = {}
  return state, state_path

def try_set_comm(name):
  try:
    with open('/proc/self/comm', 'r+') as f:
      f.write(COMM_NAMES.get(name, name))
  except (FileNotFoundError, PermissionError):
    pass

def should_use_same_tab(pending_actions):
  return (
    len(pending_actions) < 2 or
    all((i[0] in SAME_TAB_ACTIONS for i in pending_actions))
  )

def run_cmd(name, cmd, background = False):
  try_set_comm(name)
  print('Running:', name)
  cmd = shlex.split(cmd)
  cmd[0] = which(cmd[0]) or cmd[0]
  if background:
    kwargs = {
      'stdout': subprocess.PIPE,
      'stderr': subprocess.STDOUT,
    }
    if detached_process := getattr(subprocess, 'DETACHED_PROCESS', None):
      kwargs['creationflags'] = detached_process
    else:
      kwargs['start_new_session'] = True
    proc = subprocess.Popen(cmd, **kwargs)
    proc.output_buffer = io.BytesIO()
    return proc
  proc = subprocess.run(cmd)
  finish_cmd(name, proc)
  return proc

def finish_cmd(name, proc, timeout = None):
  if (output_buffer := getattr(proc, 'output_buffer', None)) is not None:
    try:
      proc.wait(timeout = timeout)
      timed_out = False
    except subprocess.TimeoutExpired:
      timed_out = True
    os.set_blocking(proc.stdout.fileno(), not timed_out)
    if buf := proc.stdout.read():
      output_buffer.write(buf)
    if timed_out:
      return False
    print(f'STDOUT for {repr(name)}:')
    print(output_buffer.getvalue().decode())
  print('Completed:', name)
  print('Command:', shlex.join(proc.args))
  print('Return Code:', proc.returncode)
  print('')
  if proc.returncode == 0:
    state, state_path = load_state()
    os.makedirs(os.path.dirname(state_path), exist_ok = True)
    state['last_' + name] = time.time()
    with open(state_path, 'w') as f:
      json.dump(state, f)
  return True

def list_next(ctx):
  for name, t in sorted(ctx.get('next', {}).items(), key = lambda i: i[1]):
    hours = (t - ctx['now'])/(60*60)
    print(name,
          '- %.2f hour(s) -' % hours,
          time.strftime('%c', time.localtime(t)))
  return print('')

def main():
  pending_actions = []
  argv = list(filter(lambda i: i not in ('--remote', '--next', '-n'),
                     sys.argv))
  if len(argv) >= 3:
    name, cmd = sys.argv[1:3]
    pending_actions.append((name, cmd))
    try_set_comm(name)

  if pending_actions:
    ctx = {}
  else:
    apply_enqueue_rules(ctx := {
      'state': load_state()[0],
      'pending_actions': pending_actions,
      'now': time.time(),
    })

  if show_next:
    return list_next(ctx)

  if is_remote:
    remaining_procs = {}
    for name, cmd in pending_actions:
      remaining_procs[name] = run_cmd(name, cmd, background = True)
    while len(remaining_procs) > 0:
      for name, proc in list(remaining_procs.items()):
        if finished := finish_cmd(name, proc, timeout = 1):
          remaining_procs.pop(name)
          sys.stdout.flush()
    return
  using_konsole = os.environ.get('KONSOLE_VERSION')
  if using_konsole and not should_use_same_tab(pending_actions):
    for name, cmd in pending_actions[1:]:
      c = ['konsole', '--new-tab', '-e',
          sys.executable, __file__, name, cmd, '--child']
      subprocess.check_call(c)
    pending_actions = pending_actions[:1]
  if should_use_same_tab(pending_actions):
    for name, cmd in pending_actions:
      proc = run_cmd(name, cmd)
    list_next(ctx)
    if not os.environ.get('TMUX') and '--child' not in sys.argv:
      return
    shell = os.environ.get('SHELL', 'sh')
    if not os.path.isabs(shell):
      shell = which(shell)
    execve = getattr(os, 'execve')
    env = (dict(os.environ) |
           {
             'PS1': r'[{} \W]\$ '.format(name),
             'DATT_NAME': name,
             'DATT_CMD': cmd,
             'DATT_RETURN_CODE': str(proc.returncode),
           })
    if shell and execve:
      execve(shell, (shell,), env)
    else:
      subprocess.run((sys.executable,), env = env)
  else:
    proc = subprocess.run(('tmux', 'has-session', '-t', SESSION_NAME))
    needs_new_session = (proc.returncode != 0)
    for name, cmd in pending_actions:
      c = [sys.executable, __file__, name, cmd]
      if needs_new_session:
        subprocess.check_call(('tmux', 'new-session', '-d', '-s', SESSION_NAME,
                               shlex.join(c)))
        needs_new_session = False
      else:
        subprocess.check_call(['tmux', 'split-window', '-t', SESSION_NAME] + c)
    subprocess.check_call(('tmux', 'attach-session', '-t', SESSION_NAME))

if __name__ == '__main__':
  main()

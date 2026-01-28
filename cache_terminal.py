#!/usr/bin/env python3

import os, sys, subprocess, shlex, time, threading

STDIN_READ_TIMEOUT = 1

def stdin_thread(proc, log_lock, log_fh):
  while proc.poll() is None:
    if not (c := sys.stdin.buffer.raw.read(1)):
      proc.stdin.close()
      break
    if proc.poll() is not None:
      break
    with log_lock:
      log_fh.write(c)
    proc.stdin.write(c)

def main():
  args = sys.argv[1:]
  if not args or args[0] == '--help':
    cmd = sys.argv[0]
    if __import__('shutil').which(os.path.basename(cmd)) == cmd:
      cmd = os.path.basename(cmd)
    print(f'Usage: {cmd} [COMMAND] [ARG0 ARGS]')
    print('  --help Displays this help message')
    print('')
    print('cache_terminal is a utility which will run a command while logging')
    print('it\'s input and output to a file. By default, logs are saved to')
    print('$XDG_CACHE_HOME/cached_terminal_sessions.')
    print('')
    print('Set the environment variable CACHED_TERMINAL_SESSIONS_DIR to use')
    print('another directory; the directory must already exist.')
    return

  if not (cache_dir := os.environ.get('CACHED_TERMINAL_SESSIONS_DIR')):
    if not (cache_home := os.environ.get('XDG_CACHE_HOME')):
      cache_home = os.path.join(os.path.expanduser('~'), '.cache')
    cache_dir = os.path.join(cache_home, 'cached_terminal_sessions')
    os.makedirs(cache_dir, exist_ok = True)

  log_lock = threading.Lock()
  log_fname = f'session-{round(time.time())}-{os.urandom(5).hex().upper()}.log'
  log_fpath = os.path.join(cache_dir, log_fname)
  print(f'Logging to {log_fpath}\n')
  log_fh = open(log_fpath, 'xb')
  log_fh.write((shlex.join(args) + '\n\n').encode())

  proc = subprocess.Popen(
    args,
    bufsize = 0,
    stdin = subprocess.PIPE,
    stdout = subprocess.PIPE,
    stderr = subprocess.STDOUT,
  )

  input_thread = threading.Thread(
    target = stdin_thread,
    args = (proc, log_lock, log_fh),
    daemon = True,
  )
  input_thread.start()

  last_comm = None
  check_comm = True
  while True:
    try:
      c = proc.stdout.read(1)
    except KeyboardInterrupt:
      continue
    if c in (b'\n', None) and check_comm:
      try:
        with open(f'/proc/{proc.pid}/comm', 'rb') as f:
          new_comm = b'ct-' + f.read()
        if new_comm != last_comm:
          with open('/proc/self/comm', 'rb+') as f:
            f.write(new_comm)
          last_comm = new_comm
      except (FileNotFoundError, PermissionError):
        check_comm = False
    if not c:
      break
    with log_lock:
      log_fh.write(c)
    sys.stdout.buffer.raw.write(c)

  rc = proc.wait()
  input_thread.join(timeout = STDIN_READ_TIMEOUT)

  # NB: manually close stdin if stdin_thread might still have its lock as this
  #     can cause a fatal error if the interpreter tries to acquire the lock
  #     for stdin when stdin_thread already holds it
  if input_thread.is_alive():
    sys.stdin.close()

  with log_lock:
    log_fh.write(f'\nReturn Code: {rc}\n'.encode())
    log_fh.flush()
    log_fh.close()
    sys.exit(rc)

if __name__ == '__main__':
  main()

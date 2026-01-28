#!/usr/bin/env python3

SESSION_NAME = 'persist'

def session_exists(user):
  proc = __import__('subprocess').run((
    'sudo', '-u', user, 'tmux', 'has-session', '-t', SESSION_NAME
  ), capture_output = True)
  return proc.returncode == 0

def main():
  user = __import__('sys').argv[1]
  if not session_exists(user):
    pw = __import__('pwd').getpwnam(user)
    uid = pw.pw_uid
    tmux_sock_dir = __import__('os').path.join(
      __import__('os').environ.get('TMUX_TMPDIR', '/tmp'), f'tmux-{uid}',
    )
    script =  ';'.join((
      f'tmux new-session -d -s {SESSION_NAME}',
      f'while tmux has-session -t {SESSION_NAME}',
        f'do inotifywait -q {tmux_sock_dir}',
      'done',
      'exit 0',
    ))
    __import__('subprocess').check_call((
      'systemd-run', '-u', 'persistent-tmux-'+user, '-pUser='+user,
      'sh', '-c', script,
    ))
    while not session_exists(user):
      __import__('time').sleep(0.1)

if __name__ == '__main__':
  main()

#!/usr/bin/env python3

ONE_DAY = 24 * 60 * 60

MIN_CONSOLE_WIDTH = 80

SSH_HOSTNAME_ERROR_STR = 'Could not resolve hostname'
SSH_HOSTNAME_ERROR_CODE = 255
DEFAULT_SSH_RETRY_COUNT = 5

class Context(object): ...

def call_ssh(ctx, destination, inp):
  if enc := getattr(inp, 'encode', None):
    inp = enc()
  import subprocess
  for _ in range(ctx.options.get('retry_count', DEFAULT_SSH_RETRY_COUNT)):
    proc = subprocess.run(('ssh', destination),
                           capture_output = True,
                           input = inp)
    try:
      stderr = proc.stderr.decode()
    except UnicodeDecodeError:
      stderr = repr(stderr)
    if (proc.returncode != SSH_HOSTNAME_ERROR_CODE or
        SSH_HOSTNAME_ERROR_STR not in stderr):
      return proc
    ctx.logger.debug('Encountered retriable SSH error: {}'.format(proc))
  raise RuntimeError('SSH retry count exceeded')

def apt_healthcheck_class_handler(ctx):
  import os, time, datetime
  max_mtime = 0
  cmds = [
    'zcat /var/log/apt/history.log.1.gz',
    'cat /var/log/apt/history.log',
  ]
  while len(cmds) > 0:
    cmd = cmds.pop()
    ctx.logger.debug('Querying server via ' + cmd)
    destination = ctx.options.get('destination', ctx.name)
    barrier = os.urandom(50).hex()
    icmd = 'echo {} ; {}\n'.format(barrier, cmd)
    proc = call_ssh(ctx, destination, icmd)
    ctx.logger.debug('Query completed: {}'.format(proc))
    proc.check_returncode()
    stdout = proc.stdout.decode().strip()
    stdout = stdout[stdout.index(barrier)+22:].strip()
    if cmd[0] == 'p':
      st = json.loads(stdout)
      mtime = st['st_mtime']
    else:
      try:
        mtime = stdout[stdout.rindex('End-Date:') + 9:].strip()
        mtime = time.mktime(time.strptime(mtime, '%Y-%m-%d  %H:%M:%S'))
      except ValueError:
        if not ctx.options.get('fallback_to_mtime'):
          continue
        path = cmd.split()[-1]
        code = ('''
          import os, json;
          st = os.stat(_PATH);
          print(json.dumps({k: k[0] not in 'sn' or getattr(st,k)
                               for k in dir(st)}))
        '''
          .strip()
          .replace('\n','')
          .replace('  ', '')
          .replace('_PATH', repr(path))
        )
        import json
        cmds.append('python -c {}'.format(json.dumps(code)))
        continue
    ctx.logger.debug('MTIME: {}'.format(mtime))
    max_mtime = max(max_mtime, mtime)
  delta = time.time() - max_mtime
  ctx.logger.debug('Delta from {}: {}'.format(repr(cmd), delta))
  max_age = ctx.options.get('max_age', 30 * ONE_DAY)
  if delta > max_age:
    raise Exception('{} is due for updates'.format(ctx.name))
  else:
    return True

def pacman_healthcheck_class_handler(ctx):
  import time, datetime
  cmd = 'tail /var/log/pacman.log'
  ctx.logger.debug('Querying server')
  destination = ctx.options.get('destination', ctx.name)
  proc = call_ssh(ctx, destination, cmd)
  ctx.logger.debug('Query completed: {}'.format(proc))
  line = proc.stdout.splitlines()[-1].decode().split()[0][1:-1]
  mtime = time.mktime(datetime.datetime.fromisoformat(line).timetuple())
  delta = time.time() - mtime
  max_age = ctx.options.get('max_age', 30 * ONE_DAY)
  ctx.logger.debug('Delta: {}'.format(delta))
  if delta > max_age:
    raise Exception('{} is due for updates'.format(ctx.name))
  else:
    return True

def external_healthcheck_class_handler(ctx):
  import os, subprocess, json
  env = dict(os.environ) | ctx.options.get('env', {})
  kwargs = {'stdin': subprocess.PIPE, 'env': env}
  if cwd := ctx.options.get('cwd'):
    kwargs['cwd'] = os.path.expanduser(cwd)
  js_ctx = json.dumps({
    'name': ctx.name,
    'options': ctx.options,
  })
  if ctx.options.get('pass_context_via_env'):
    env['HEALTHCHECK_CONTEXT'] = js_ctx
  stdin = ctx.options.get('stdin')
  if ctx.options.get('pass_context_via_stdin'):
    stdin = js_ctx
  if stdin:
    stdin = stdin.encode()
  passing_return_codes = set(ctx.options.get('passing_return_codes', (0,)))
  ctx.logger.debug('Starting process')
  cmd = ctx.options['cmd']
  if type(cmd) is str:
    import shlex
    cmd = shlex.split(cmd)
  if not (no_capture := ctx.options.get('no_capture')):
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.STDOUT
  proc = subprocess.Popen(cmd, **kwargs)
  ctx.logger.debug('Running process: {}'.format(proc))
  if stdin:
    proc.stdin.write(stdin)
    proc.stdin.flush()
  if not no_capture:
    ctx.logger.debug('  ---------- Begin Process Output ----------  ')
    last_line = b''
    while True:
      line = proc.stdout.readline()
      if not line:
        if last_line.endswith(b'\n'):
          ctx.logger.debug('')
        break
      last_line = line if ctx.options.get('keepends') else line.rstrip()
      ctx.logger.debug(repr(last_line)[2:-1])
    ctx.logger.debug('  ----------  End Process Output  ----------  ')
  ret = proc.wait()
  ctx.logger.debug('Completed process: {}'.format(proc))
  ctx.logger.debug('Return Code: {}'.format(ret))
  if ret not in passing_return_codes:
    raise Exception('Return code was {}, expected {}'
                     .format(ret, ' or '.join(map(str, passing_return_codes))))
  else:
    return True

class ExclusiveLogger(object):
  def __init__(self, name):
    import logging, threading
    self.lock = (globals()
                  .setdefault('_logger_locks', {})
                  .setdefault(name, threading.Lock()))
    self.logger = logging.getLogger(name)
    self.level = logging.NOTSET
    self.handlers = []
    self.filters = []
  def setLevel(self, level):
    self.level = level
  def addHandler(self, handler):
    with self.lock:
      self.handlers.append(handler)
  def removeHandler(self, handler):
    with self.lock:
      self.handlers.remove(handler)
  def addFilter(self, filter):
    with self.lock:
      self.filters.append(filter)
  def removeFilter(self, filter):
    with self.lock:
      self.filters.remove(filter)
  def __getattr__(self, name):
    v = getattr(self.logger, name)
    v_is_method = type(v) is type(self.setLevel)
    def _wrapped(*args, **kwargs):
      with self.lock:
        self.logger.setLevel(self.level)
        for lh in self.handlers:
          self.logger.addHandler(lh)
        for lf in self.filters:
          self.logger.addFilter(lf)
        try:
          return v(*args, **kwargs) if v_is_method else v
        finally:
          for lf in self.filters:
            self.logger.removeFilter(lf)
          for lh in self.handlers:
            self.logger.removeHandler(lh)
    return _wrapped if v_is_method else _wrapped()

def _add_log_file_if_set(config, logger, name = None):
  if log_path := config.get('log_path'):
    import os, logging
    lh = logging.FileHandler(os.path.expanduser(log_path), delay = True)
    pid = os.getpid()
    n = '' if name is None else ' [{}]'.format(name)
    fmt = '[%(asctime)s] [{}]{} %(message)s'.format(pid, n)
    lh.setFormatter(logging.Formatter(fmt = fmt))
    logger.addHandler(lh)

def setup_logging(config = None, ectx = None):
  import os, logging, threading
  if config is None:
    config = ectx.config
  ectx.log_level = config.get('log_level', 'DEBUG')
  logger = ExclusiveLogger(__name__ + '.main')
  logger.setLevel(ectx.log_level)
  if not config.get('quiet'):
    logger.addHandler(logging.StreamHandler(ectx.console_output_stream))
  _add_log_file_if_set(config, logger)
  ectx.__dict__.setdefault('console_output_lock', threading.Lock())
  ectx.logger = logger
  return logger

def print_status_line(ectx, *args, permanent = False, entity = None):
  with ectx.console_output_lock:
    last_lines = getattr(ectx, 'last_lines', [])
    last_line = last_lines[-1][1] if last_lines else ''
    last_lines = list(filter(lambda i: i[0] != entity, last_lines))
    for i in (
      (len(last_line) * '\b'),
      (len(last_line) * ' '),
      (len(last_line) * '\b'),
    ):
      ectx.console_output_stream.write(i)
      ectx.console_output_stream.flush()
    if permanent:
      ectx.logger.info(*args)
      line = last_lines[-1][1] if last_lines else ''
    else:
      line = (
        ' '.join(map(str, args))
          .split('\n')[-1]
          .split('\r')[-1]
          [:MIN_CONSOLE_WIDTH]
      )
      last_lines.append((entity, line))
    ectx.console_output_stream.write(line)
    ectx.console_output_stream.flush()
    ectx.last_lines = last_lines

def lprint(ectx, *args, entity = None):
  if not (logger := getattr(ectx, 'logger', None)):
    logger = setup_logging(ectx = ectx)
  print_status_line(ectx, *args, permanent = True, entity = entity)

def check(ectx, name, options):
  import io, logging

  class StatusLineHandler(logging.Handler):
    def __init__(self, ectx, name):
      self.ectx = ectx
      self._entity_name = name
      super().__init__()
      self.setLevel(ectx.log_level)
    def emit(self, record):
      try:
        print_status_line(self.ectx,
                          self.format(record),
                          entity = self._entity_name)
      except RecursionError:
        raise
      except Exception:
        self.handleError(record)

  log_stream = io.StringIO()
  status = {
    'name': name,
    'log_stream': log_stream,
  }
  cls = repr(options.get('class'))[1:-1].lower()
  handler = globals().get('{}_healthcheck_class_handler'.format(cls))
  if not handler:
    status['passed'] = False
    status['reason'] = 'invalid handler class {}'.format(repr(cls))
    return status
  logger = ExclusiveLogger(__name__ + '.entity')
  logger.setLevel(options.get('log_level', ectx.log_level))
  logger.addHandler(logging.StreamHandler(log_stream))
  logger.addHandler(StatusLineHandler(ectx, name))
  for lh in logger.handlers:
    lh.setFormatter(logging.Formatter(fmt = '[{}] %(message)s'.format(name)))
  _add_log_file_if_set(ectx.config, logger, name = name)
  ctx = Context()
  ctx.name = name
  ctx.options = options
  ctx.logger = logger
  ctx.status = status
  try:
    status['passed'] = handler(ctx)
  except Exception as exc:
    status['exception'] = exc
    status['passed'] = False
  return status

def load_config(path = None):
  import os
  config_path = path or os.environ.get('HEALTHCHECK_CONFIG')
  if not config_path:
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
    if xdg_config_home:
      config_path = os.path.join(xdg_config_home, 'healthcheck.toml')
  if not config_path:
    appdata = os.environ.get('APPDATA')
    if appdata:
      config_path = os.path.join(appdata, 'healthcheck.toml')
  if not config_path:
    config_path = os.path.expanduser(
      os.path.join('~', '.config', 'healthcheck.toml')
    )
  with open(config_path, 'rb') as f:
    import tomllib
    return tomllib.load(f)

def verify_status(ectx, status):
  name = status.get('name')
  missing = object()
  passed = status.get('passed', missing)
  if passed is True:
    lprint(ectx, '[PASSED] {}'.format(name), entity = name)
    return 0
  lprint(ectx, '[FAILED!] {}  <<<----------'.format(name), entity = name)
  lprint(ectx, status['log_stream'].getvalue(), entity = name)
  exception = status.get('exception')
  if exception:
    import traceback
    fmt = ''.join(traceback.format_exception(exception))
    lprint(ectx, '{} failed with exception: {}'.format(name, fmt),
            entity = name)
  reason = status.get('reason')
  if reason:
    lprint(ectx, '{} failed with reason: {}'.format(name, reason),
            entity = name)
  if passed is missing:
    lprint(ectx, '{} failed without a return value'.format(name),
            entity = name)
  else:
    lprint(ectx,
            '{} failed with return value: {}'.format(name, repr(passed)),
            entity = name)
  return 1

def verify_entity(ectx, name, options):
  return verify_status(ectx, check(ectx, name, options))

def check_entities(config = None, ectx = None, console_output_stream = None):
  if ectx is None:
    ectx = Context()
  if config:
    ectx.config = config
  if ectx.__dict__.setdefault('console_output_stream',
                              console_output_stream) is None:
    import sys
    ectx.console_output_stream = sys.stdout

  try:
    lprint(ectx, 'Starting health checks...')
    import concurrent.futures
    ex = concurrent.futures.ThreadPoolExecutor()
    futures = [
      ex.submit(check, ectx, name, options)
      for name, options in ectx.config['entities'].items()
    ]
    overall_return_code = 0
    for future in concurrent.futures.as_completed(futures):
      if verify_status(ectx, future.result()):
        overall_return_code = 1
    print_status_line(ectx, '')
  finally:
    if logger := ectx.__dict__.pop('logger', None):
      for lh in ectx.__dict__.pop('log_handlers', []):
        logger.removeHandler(lh)
  if overall_return_code == 0:
    lprint(ectx, 'OK! All health checks passed! B-P')
  else:
    lprint(ectx, 'ERROR! Some health checks failed! See the log for details.')
  return overall_return_code

def main():
  try:
    with open('/proc/self/comm', 'r+') as f:
      f.write('healthcheck')
  except (FileNotFoundError, PermissionError):
    pass
  import sys, argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('-c', '--config', help = 'config file path')
  args = parser.parse_args()
  sys.exit(check_entities(config = load_config(path = args.config)))

if __name__ == '__main__':
  main()

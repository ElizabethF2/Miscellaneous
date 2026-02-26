#!/usr/bin/env python3

import sys, os, time, threading
import hashlib, subprocess, shutil

EPSILON = 0.001

PAGE_EXECUTE_READWRITE = 0x40

DEFAULT_BUFLEN = 32
DEFAULT_BUFWIDTH = 1

# TODO args: os-rng, timing (pool and loop), other entropy sources

def worker_wrapper(pools, algs, cb, ctx):
  ident = threading.get_ident()
  while not pools['done']:
    for i in range(8):
      time.sleep(EPSILON)
      h = 0
      ent = cb(ctx) if cb else b''
      for alg in algs:
        if alg:
          t = hashlib.new(alg, str(time.time_ns()).encode())
          t.update(ent)
          t = t.digest(256) if 'shake' in alg else t.digest()
          h += sum((bin(i).count('1') for i in t)) % 2
        else:
          h += bin(time.time_ns()).count('1') % 2
      pools[ident] = (pools.get(ident, 0) + (h << i)) % 256

def make_executable(buf):
  import mmap
  try:
    mem = mmap.mmap(-1,
                    len(buf),
                    flags = mmap.MAP_ANON | mmap.MAP_PRIVATE,
                    prot = mmap.PROT_WRITE | mmap.PROT_EXEC)
    mem.write(buf.value)
    return type(buf).from_buffer(mem)
  except (TypeError, AttributeError):
    import ctypes.wintypes
    old_value = ctypes.wintypes.DWORD();
    ret = ctypes.windll.kernel32.VirtualProtect(
      ctypes.addressof(buf),
      len(buf),
      PAGE_EXECUTE_READWRITE,
      ctypes.byref(old_value)
    )
    if not ret:
      raise ctypes.WinError()
    return buf

possible_entropy_sources = []
all_hash_algs = hashlib.algorithms_available | set([None])

@possible_entropy_sources.append
def has_rdrand():
  import platform
  if platform.machine().lower() not in ('x86_64', 'amd64'):
    return
  import ctypes
  asm = (
    '480FC7F0' + # RDRAND RAX
    'C3'         # RET
  )
  code = ctypes.create_string_buffer(bytes.fromhex(asm))
  ftype = ctypes.CFUNCTYPE(ctypes.c_uint64)
  exe = make_executable(code)
  rdrand = ftype(ctypes.addressof(exe))
  rdrand._backing_buf = exe
  return get_ent_from_rdrand, rdrand

def get_ent_from_rdrand(rdrand):
  return rdrand().to_bytes(8)

@possible_entropy_sources.append
def has_alsa():
  try:
    with open('/proc/asound/pcm', 'r') as f:
      pcm = f.read()
  except FileNotFoundError:
    pcm = ''
  if pcm.lower().count('capture') < 1:
    return
  if not (ffmpeg := shutil.which('ffmpeg')):
    return
  proc = subprocess.Popen(
    (ffmpeg, '-f', 'alsa', '-i', 'default', '-f', 'wav', '-'),
    stdout = subprocess.PIPE,
    stderr = subprocess.STDOUT,
    stdin = subprocess.DEVNULL,
  )
  ctx = { 'proc': proc }
  return get_ent_from_proc_stream, ctx

def get_ent_from_proc_stream(ctx):
  bufsize = ctx.get('bufsize', 128)
  stdout = ctx['proc'].stdout
  start = time.time()
  try:
    buf = stdout.read(bufsize)
  except (BrokenPipeError, MemoryError):
    ctx.pop('bufsize', None)
    time.sleep(EPSILON)
    return b''
  if (time.time() - start) < EPSILON:
    ctx['bufsize'] = round(1.1 * bufsize)
  return buf if buf else b''

@possible_entropy_sources.append
def has_v4l():
  if not (v4l2_ctl := shutil.which('v4l2-ctl')):
    return
  if not (ffmpeg := shutil.which('ffmpeg')):
    return
  out = subprocess.check_output((v4l2_ctl, '--list-devices'))
  devices = list(filter(os.path.exists,
                        map(str.strip, out.decode().splitlines())))
  if not devices:
    return
  proc = subprocess.Popen(
    (ffmpeg, '-f', 'v4l2', '-i', devices[0], '-f', 'avi', '-'),
    stdout = subprocess.PIPE,
    stderr = subprocess.STDOUT,
    stdin = subprocess.DEVNULL,
  )
  ctx = { 'proc': proc }
  return get_ent_from_proc_stream, ctx

@possible_entropy_sources.append
def has_ps():
  ps = shutil.which('ps')
  if not ps:
    tasklist = shutil.which('tasklist')
    if not tasklist:
      return
  ctx = {
    'cmd': [ps, 'aux'] if ps else [tasklist]
  }
  return get_ent_from_cmd, ctx

def get_ent_from_cmd(ctx):
  if not (proc := ctx.get('proc')):
    time.sleep(ctx.get('delay', EPSILON))
    ctx['start'] = time.time()
    proc = subprocess.Popen(
      ctx['cmd'],
      stdout = subprocess.PIPE,
      stderr = subprocess.STDOUT,
      stdin = subprocess.DEVNULL,
    )
    ctx['proc'] = proc
  buf = proc.stdout.read(128)
  if not buf:
    buf = repr(ctx.pop('proc').poll()).encode()
    ctx['delay'] = time.time() - ctx['start']
  return buf

@possible_entropy_sources.append
def has_netstat():
  netstat = shutil.which('netstat')
  if not netstat:
    busybox = shutil.which('busybox')
    if not busybox:
      return
  ctx = {
    'cmd': ([netstat] if netstat else [busybox, 'netstat']) + ['-a', '-e']
  }
  return get_ent_from_cmd, ctx

@possible_entropy_sources.append
def has_nmcli():
  if not (nmcli := shutil.which('nmcli')):
    return
  ctx = { 'cmd': [nmcli, 'device', 'wifi', 'list', '--rescan', 'yes'] }
  return get_ent_from_cmd, ctx

@possible_entropy_sources.append
def has_bluetoothctl():
  if not (bluetoothctl := shutil.which('bluetoothctl')):
    return
  proc = subprocess.Popen(
    bluetoothctl,
    bufsize = 0,
    stdout = subprocess.PIPE,
    stderr = subprocess.STDOUT,
    stdin = subprocess.PIPE,
  )
  set_blocking = getattr(os, 'set_blocking', None)
  if set_blocking:
    set_blocking(proc.stdout.fileno(), False)
  ctx = { 'proc': proc, 'delay': 1 }
  return get_ent_from_bluetoothctl, ctx

def get_ent_from_bluetoothctl(ctx):
  proc = ctx.get('proc')
  buf = proc.stdout.read(128)
  if buf:
    if 'error.inprogress' in buf.decode().lower():
      ctx['delay'] += 1
    return buf
  now = time.time()
  delta = now - ctx.get('last', 0)
  if delta < ctx['delay']:
    time.sleep(ctx['delay'] - delta)
  try:
    proc.stdin.write('scan on\n'.encode())
    proc.stdin.flush()
  except BrokenPipeError:
    pass
  ctx['last'] = time.time()
  return b''

@possible_entropy_sources.append
def has_tpm2():
  if getattr(os, 'getuid', str)() not in ('', 0):
    return
  if not (tpm2_getrandom := shutil.which('tpm2_getrandom')):
    return
  ctx = { 'cmd': [tpm2_getrandom, '16'] }
  return get_ent_from_cmd, ctx

@possible_entropy_sources.append
def has_hwmon():
  root = '/sys/class/hwmon'
  found = []
  try:
    hwmons = os.listdir(root)
  except FileNotFoundError:
    hwmons = []
  for hwmon in hwmons:
    try:
      files = filter(lambda i: not os.path.isdir(i),
                     os.listdir(os.path.join(root, hwmon)))
    except FileNotFoundError:
      files = []
    for f in files:
      if f.endswith('_input') or f.endswith('_target'):
        found.append(os.path.join(root, hwmon, f))
  if not found:
    return
  return get_ent_from_hwmon, found

def get_ent_from_hwmon(paths):
  vals = []
  for path in paths:
    vals.append(path)
    time.sleep(EPSILON)
    try:
      with open(path, 'r') as f:
        vals.append(f.read())
    except OSError:
      vals.append(None)
  return '\n'.join(map(repr, vals)).encode()

@possible_entropy_sources.append
def has_get_cpu():
  import ctypes, ctypes.util
  libc = ctypes.CDLL(ctypes.util.find_library('c'))
  if not (get_cpu := getattr(libc, 'getcpu', None)):
    return
  return get_ent_from_get_cpu, get_cpu

def get_ent_from_get_cpu(get_cpu):
  import ctypes
  cpu = ctypes.c_uint()
  node = ctypes.c_uint()
  ret = get_cpu(ctypes.byref(cpu), ctypes.byref(node))
  errno = ctypes.get_errno()
  return repr((cpu.value, node.value, ret, errno)).encode()

@possible_entropy_sources.append
def has_pymem():
  return get_ent_from_pymem, None

def get_ent_from_pymem(_unused_ctx):
  return repr((
    tuple(map(id, {}, [], set(), range(1))),
    sys.getallocatedblocks(),
    sys._current_frames(),
  )).encode()

def get_ent_from_path(ctx):
  fh = ctx['fh']
  try:
    buf = fh.read(1)
  except KeyboardInterrupt:
    return b''
  if not buf:
    return b''
  if set_blocking := getattr(os, 'set_blocking', None):
    set_blocking(fh.fileno(), False)
    try:
      buf += fh.read(16 * 1024)
    except KeyboardInterrupt:
      pass
    set_blocking(fh.fileno(), True)
  return buf

def safe_fmt(obj, indent = ''):
  keys = getattr(obj, 'keys', None)
  if not keys:
    lines = repr(obj).splitlines()
  else:
    lines = ['{']
    keys = list(keys())
    for key in keys:
      val = obj.get(key, ...)
      lines.append(
        '  ' + safe_fmt(key) + ': ' +
        safe_fmt(val, indent = indent + '  ') +
        ('' if key == keys[-1] else ',')
      )
    lines.append('}')
  return '\n'.join((((indent + line) if idx > 0 else line)
                    for idx, line in enumerate(lines)))

def getrandom(length = 1):
  return b'\x00' * length
  buf = b''
  while len(buf) < length:
    buf += getrandom(1, getattr(os, 'GRND_RANDOM', 0)) \
           if (getrandom := getattr(os, 'getrandom', None)) else \
           os.urandom(1)
  return buf

def count_entropy(counts, buffer):
  for c in buffer:
    counts[c] = counts.get(c, 0) + 1

def sum_entropy(counts, total = None):
  if total is None:
    total = sum(counts.values())
  entropy = 0
  import math
  for c, v in counts.items():
    p = v / total
    entropy -= p * math.log2(p)
  return (entropy / 8)

def calculate_entropy(buffer):
  count_entropy(counts := {}, buffer)
  return sum_entropy(counts, total = len(buffer))

def generate(buflen = DEFAULT_BUFLEN,
             bufwidth = DEFAULT_BUFWIDTH,
             output_fh = None,
             hex = False,
             debug = False,
             realtime = False,
             calculate_entropy = False,
             autofire_delay = None,
             entropy_fhs = [],
             entropy_cmds = [],
             stop_predicate = None):
  result_ctx = type('Context', (), {})()
  pools = {'done': False}
  threads = [([i], None, None, 'timing_{}'.format(i)) for i in all_hash_algs]
  threads = []
  for has_entropy_source in possible_entropy_sources:
    has_it = has_entropy_source()
    name = has_entropy_source.__name__[4:]
    if debug:
      print(name + ' = ' + str(bool(has_it)))
    if not has_it:
      continue
    cb, ctx = has_it
    threads.append((all_hash_algs, cb, ctx, name))
  for fh in entropy_fhs:
    ctx = { 'fh': fh }
    name = 'PATH:' + getattr(path, 'name', repr(fh))
    threads.append((all_hash_algs, get_ent_from_path, ctx, name))
  for cmd in (entropy_cmds or []):
    ctx = { 'cmd': __import__('shlex').split(cmd) }
    name = 'CMD:' + cmd
    threads.append((all_hash_algs, get_ent_from_cmd, ctx, name))
  ctxs = {i[3]: i[2] for i in threads}
  threads = [(j, j.start())[0]
             for j in (threading.Thread(target = worker_wrapper,
                                        args = (pools, i[0], i[1], i[2]),
                                        name = i[3])
                       for i in threads)]
  if debug:
    ident_to_name = {i.ident: i.name for i in threads}
  while len(pools) < len(threads):
    time.sleep(EPSILON)
  buf = b''
  count = 0
  if getattr(buflen, 'lower', str)() == 'inf':
    buflen = float('inf')
  elif buflen != float('inf'):
    buflen = int(buflen)
    if bufwidth > 1 and not realtime:
      buflen *= bufwidth
  counts = {}
  try:
    while len(buf) < buflen and count < buflen:
      if stop_predicate and stop_predicate():
        break
      b = 0
      if autofire_delay is None:
        inp = b''.join(sys.stdin.buffer.readline() for _ in range(8))
      else:
        snapshot = tuple(pools.values())
        time.sleep(autofire_delay)
        for _ in range(2):
          while snapshot:
            new_snap = tuple(pools.values())
            if new_snap != snapshot:
              snapshot = new_snap
              break
            time.sleep(EPSILON)
        inp = getrandom(16)
      for idx, c in enumerate(inp):
        b += ((bin(c).count('1') % 2) << (idx % 8))
        b += ((bin(time.time_ns()).count('1') % 2) << (idx % 8))
        b += ord(getrandom(1))
        for v in pools.values():
          b += v
        if debug:
          print('Threads:')
          t = {ident_to_name.get(k, k): {'pool': v, 'ident': k}
               for k,v in pools.items()}
          t = {k: (v | {'ctx': ctxs.get(k)}) for k,v in t.items()}
          print(safe_fmt(t))
          if realtime:
            print('\nCount: {} out of {}\n'.format(count+1, buflen))
          else:
            print('\nLength: {} out of {}\n'.format(len(buf)+1, buflen))
        time.sleep(EPSILON)
      for v in pools.values():
        b += v
      b = (b % 256).to_bytes()
      if realtime:
        if output_fh:
          output_fh.write(b.hex().encode() if hex else b)
          getattr(output_fh, 'flush', int)()
        count += 1
      else:
        buf += b
      if calculate_entropy:
        count_entropy(counts, b)
  except KeyboardInterrupt:
    pass
  pools['done'] = True
  if not realtime:
    if bufwidth > 1:
      _buf = []
      for x in range(len(buf)//bufwidth):
        b = 0
        for y in range(bufwidth):
          try:
            b ^= buf[(y*bufwidth)+x]
          except IndexError:
            break
        _buf.append(b.to_bytes())
      buf = b''.join(_buf)
    result_ctx.buffer = buf
    if output_fh:
      output_fh.write(buf.hex().encode() if hex else buf)
      getattr(output_fh, 'flush', int)()
  if calculate_entropy:
    entropy = sum_entropy(counts, total = buflen)
    if debug:
      print('\nEntropy: {}\n'.format(entropy))
    result_ctx.entropy = entropy
  for thread in threads:
    ctx = ctxs.get(thread.name)
    if type(ctx) is dict:
      proc = ctx.get('proc')
      if proc and proc.poll() is None:
        proc.terminate()
    thread.join()
  return result_ctx

def main():
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('--buflen', type = str, default = str(DEFAULT_BUFLEN))
  parser.add_argument('--bufwidth', type = int, default = DEFAULT_BUFWIDTH)
  parser.add_argument('--out', type = str)
  parser.add_argument('--hex', action = argparse.BooleanOptionalAction)
  parser.add_argument('--debug', action = argparse.BooleanOptionalAction)
  parser.add_argument('--realtime', action = argparse.BooleanOptionalAction)
  parser.add_argument('--autofire-delay', type = float, default = None)
  parser.add_argument('--entropy-paths', type = str, nargs = '*')
  parser.add_argument('--entropy-cmds', type = str, nargs = '*')
  parser.add_argument('--calculate-entropy',
                      action = argparse.BooleanOptionalAction)
  parser.add_argument('--calculate-entropy-for-path', type = str)
  parser.add_argument('--calculate-entropy-for-stdin',
                      action = argparse.BooleanOptionalAction)
  args = parser.parse_args()

  calculate_entropy_for_fh = None
  if args.calculate_entropy_for_path:
    calculate_entropy_for_fh = open(args.calculate_entropy_for_path, 'rb')
  elif args.calculate_entropy_for_stdin:
    calculate_entropy_for_fh = sys.stdin.buffer
  if calculate_entropy_for_fh:
    counts = {}
    total = 0
    while True:
      if not (buf := calculate_entropy_for_fh.read(16 * 1024)):
        break
      count_entropy(counts, buf)
      total += len(buf)
    return print(sum_entropy(counts, total = total))

  entropy_fhs = [open(path, 'rb') for path in (args.entropy_paths or [])]
  if args.out:
    output_fh = open(args.out, 'ab' if args.realtime else 'xb')
  else:
    output_fh = sys.stdout.buffer
  result_ctx = generate(
    buflen = args.buflen,
    bufwidth = args.bufwidth,
    output_fh = output_fh,
    hex = args.hex,
    debug = args.debug,
    realtime = args.realtime,
    calculate_entropy = args.calculate_entropy,
    autofire_delay = args.autofire_delay,
    entropy_fhs = entropy_fhs,
    entropy_cmds = args.entropy_cmds or [],
  )
  if args.calculate_entropy and not args.debug:
    print('\nEntropy: {}\n'.format(result_ctx.entropy))

if __name__ == '__main__':
  main()

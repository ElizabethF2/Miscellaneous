#!/usr/bin/env python3

import sys, os, termios, tty

ESC = chr(27)
ENABLE_MOUSE_TRACKING = ESC + '[?1000h'
DISABLE_MOUSE_TRACKING = ESC + '[?1000l'

LEFT_MOUSE_BUTTON = 0

HORIZONTAL_BAR = chr(9472)
VERTICAL_BAR = chr(9474)
TOP_LEFT_CORNER = chr(9581)
BOTTOM_LEFT_CORNER = chr(9584)
TOP_RIGHT_CORNER = chr(9582)
BOTTOM_RIGHT_CORNER = chr(9583)

DEFAULT_RETURN_CODE = 127

def menu(items, input_stream = None, ui_stream = None, result_stream = None):
  if input_stream is None:
    input_stream = sys.stdin
  if ui_stream is None:
    ui_stream = sys.stderr
  width, height = os.get_terminal_size()
  lines = []
  bounds = {}
  for index, item in enumerate(items):
    eitem = item
    if len(eitem) > (width - 6):
      eitem = eitem[:width-9] + '...'
    ilen = len(eitem) + 2
    lines.append('')
    lines.append(' ' +
                 TOP_LEFT_CORNER +
                 (ilen * HORIZONTAL_BAR) +
                 TOP_RIGHT_CORNER)
    lines.append(' ' + VERTICAL_BAR + ' ' + eitem + ' ' + VERTICAL_BAR)
    lines.append(' ' +
                 BOTTOM_LEFT_CORNER +
                 (ilen * HORIZONTAL_BAR) +
                 BOTTOM_RIGHT_CORNER)
    bounds[item] = {
      'top': len(lines) - 3,
      'bottom': len(lines),
      'left': 1,
      'right': 3 + ilen,
      'index': index,
    }
  lines = lines[:height] + ((height - len(lines)) * [''])

  ui_stream.write('\n'.join(lines))
  inp = input_stream.fileno()
  old_attr = termios.tcgetattr(inp)
  new_attr = old_attr[:]
  new_attr[3] &= ~(termios.ICANON | termios.ECHO)
  match = None
  try:
    ui_stream.write(ENABLE_MOUSE_TRACKING)
    ui_stream.flush()
    termios.tcsetattr(inp, termios.TCSANOW, new_attr)
    buf = ''
    while match is None:
      buf += input_stream.read(1)
      if buf[-6:-3] == (ESC + '[M'):
        button = ord(buf[-3]) - 32
        if button == LEFT_MOUSE_BUTTON:
          x = ord(buf[-2]) - 32
          y = ord(buf[-1]) - 32
          buf = ''
          for name, bound in bounds.items():
            if x >= bound['left'] and x <= bound['right'] and \
              y <= bound['bottom'] and y >= bound['top']:
              match = name
              match_index = bound['index']
              break
  finally:
    termios.tcsetattr(inp, termios.TCSANOW, old_attr)
  ui_stream.write(DISABLE_MOUSE_TRACKING)
  ui_stream.flush()
  if result_stream is not None:
    result_stream.write(match)
    result_stream.flush()
  return match_index

def main():
  res = DEFAULT_RETURN_CODE
  try:
    res = menu(sys.argv[1:])
  except:
    import traceback
    traceback.print_last()
  sys.exit(res)

if __name__ == '__main__':
  main()

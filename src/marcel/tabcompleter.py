import os
import pathlib
import readline

import marcel.core
import marcel.op
from marcel.util import *


DEBUG = True


def debug(message):
    if DEBUG:
        print(message)


class TabCompleter:

    OPS = marcel.op.public
    FILENAME_OPS = ['cd',
                    'ls',
                    'mv',
                    'out',
                    'rm']

    def __init__(self, global_state):
        self.global_state = global_state
        self.op_name = None
        self.executables = None
        self.homedirs = None
        readline.set_completer(self.complete)
        # Removed '-', '/', '~' from readline.get_completer_delims()
        readline.set_completer_delims(' \t\n`!@#$%^&*()=+[{]}\\|;:\'",<>?')

    def complete(self, text, state):
        line = readline.get_line_buffer()
        debug(f'complete: line={line}, text={text}')
        if len(line.strip()) == 0:
            candidates = TabCompleter.OPS
        else:
            # Parse the text so far, to get information needed for tab completion. It is expected that
            # the text will end early, since we are doing tab completion here. This results in a PrematureEndError
            # which can be ignored. The important point is that the parse will set Parser.op.
            parser = marcel.parse.Parser(line, self.global_state)
            try:
                parser.parse(partial_text=True)
                debug('parse succeeded')
            except marcel.parse.PrematureEndError:
                debug('premature end')
                pass
            except Exception as e:
                debug(f'caught ({type(e)}) {e}')
                # Don't do tab completion
                return None
            debug(f'parser.op: {parser.op}')
            if parser.op is None:
                candidates = self.complete_op(text)
            else:
                self.op_name = parser.op.op_name()
                if text.startswith('-'):
                    candidates = TabCompleter.complete_flag(text, self.op_name)
                elif self.op_name in TabCompleter.FILENAME_OPS:
                    candidates = self.complete_filename(text)
                else:
                    return None
        return candidates[state]

    def complete_op(self, text):
        debug(f'complete_op, text = <{text}>')
        candidates = []
        if len(text) > 0:
            # Display marcel ops.
            # Display executables only if there are no qualifying ops.
            for op in TabCompleter.OPS:
                op_with_space = op + ' '
                if op_with_space.startswith(text):
                    candidates.append(op_with_space)
            if len(candidates) == 0:
                self.ensure_executables()
                for ex in self.executables:
                    ex_with_space = ex + ' '
                    if ex_with_space.startswith(text):
                        candidates.append(ex_with_space)
            debug(f'complete_op candidates for {text}: {candidates}')
        else:
            candidates = TabCompleter.OPS
        return candidates

    @staticmethod
    def complete_flag(text, op_name):
        flags = marcel.core.ArgParser.op_flags[op_name]
        candidates = []
        for f in flags:
            if f.startswith(text):
                candidates.append(f)
        debug('complete_flag candidates for <{}>: {}'.format(text, candidates))
        return candidates

    def complete_filename(self, text):
        debug('complete_filenames, text = <{}>'.format(text))
        current_dir = self.global_state.env.pwd()
        if text:
            if text == '~/':
                home = pathlib.Path(text).expanduser()
                filenames = os.listdir(home.as_posix())
            elif text.startswith('~/'):
                base = pathlib.Path('~/').expanduser()
                base_length = len(base.as_posix())
                pattern = text[2:] + '*'
                filenames = ['~' + f[base_length:] + ' '
                             for f in [p.as_posix() for p in base.glob(pattern)]]
            elif text.startswith('~'):
                find_user = text[1:]
                self.ensure_homedirs()
                filenames = []
                for username in self.homedirs.keys():
                    if username.startswith(find_user):
                        filenames.append('~' + username + ' ')
            else:
                base, pattern_prefix = (('/', text[1:])
                                        if text.startswith('/') else
                                        ('.', text))
                filenames = [p.as_posix() + ' ' for p in pathlib.Path(base).glob(pattern_prefix + '*')]
        else:
            filenames = ['/'] + [p.relative_to(current_dir).as_posix() for p in current_dir.iterdir()]
        debug('complete_filename candidates for {}: {}'.format(text, filenames))
        return filenames

    @staticmethod
    def op_name(line):
        first = line.split()[0]
        return first if first in TabCompleter.OPS else None

    def ensure_executables(self):
        if self.executables is None:
            self.executables = []
            path = os.environ['PATH'].split(':')
            for p in path:
                for f in os.listdir(p):
                    if is_executable(f):
                        self.executables.append(f)

    def ensure_homedirs(self):
        if self.homedirs is None:
            self.homedirs = {}
            # TODO: This is a hack. Is there a better way?
            with open('/etc/passwd', 'r') as passwds:
                users = passwds.readlines()
            for line in users:
                fields = line.split(':')
                username = fields[0]
                homedir = fields[5]
                self.homedirs[username] = homedir


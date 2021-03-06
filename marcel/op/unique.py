# This file is part of Marcel.
# 
# Marcel is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or at your
# option) any later version.
# 
# Marcel is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Marcel.  If not, see <https://www.gnu.org/licenses/>.

import marcel.argsparser
import marcel.core
import marcel.util


HELP = '''
{L,wrap=F}unique [-c|--consecutive]

{L,indent=4:28}{r:-c}, {r:--consecutive}       Only look for consecutive duplicates.

Write to the output stream all input tuples, but without duplicates.

Input tuples are passed to output, removing duplicates. No output is
generated until the end of the input stream occurs. However, if the
duplicates are known to be consecutive, then {r:--consecutive} allows
output to be generated sooner. Input order is preserved only if {r:--consecutive}
is specified.
'''


def unique(env, consecutive=False):
    return Unique(env), ['--consecutive'] if consecutive else []


class UniqueArgsParser(marcel.argsparser.ArgsParser):

    def __init__(self, env):
        super().__init__('unique', env)
        self.add_flag_no_value('consecutive', '-c', '--consecutive')
        self.validate()


class Unique(marcel.core.Op):

    def __init__(self, env):
        super().__init__(env)
        self.consecutive = None
        self.uniquer = None

    def __repr__(self):
        return 'unique()'

    # AbstractOp

    def setup(self):
        self.uniquer = ConsecutiveUniquer(self) if self.consecutive else GeneralUniquer(self)

    def receive(self, x):
        self.uniquer.receive(x)


class Uniquer:

    def receive(self, x):
        assert False


class GeneralUniquer(Uniquer):

    def __init__(self, op):
        self.op = op
        self.unique = set()

    def receive(self, x):
        x = marcel.util.wrap_op_input(x)  # convert list to tuple
        if x not in self.unique:
            self.unique.add(x)
            self.op.send(x)


class ConsecutiveUniquer(Uniquer):

    def __init__(self, op):
        self.op = op
        self.current = None

    def receive(self, x):
        if self.current != x:
            self.op.send(x)
            self.current = x

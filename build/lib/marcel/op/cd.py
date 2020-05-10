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

import pathlib

import marcel.core


SUMMARY = '''
Change the current directory to the given directory.
'''


DETAILS = '''
If {r:directory} is omitted, then change the current directory to the home directory.
'''


def cd(directory=None):
    op = Cd()
    op.directory = directory
    return op


class CdArgParser(marcel.core.ArgParser):

    def __init__(self, env):
        super().__init__('cd', env, None, SUMMARY, DETAILS)
        self.add_argument('directory',
                          nargs='?',
                          default='~',
                          help='New current directory')


class Cd(marcel.core.Op):

    def __init__(self):
        super().__init__()
        self.directory = None

    def __repr__(self):
        return f'cd({self.directory})'

    # BaseOp

    def setup_1(self):
        self.directory = pathlib.Path(self.directory)

    def receive(self, _):
        self.env().dir_state().cd(self.directory)

    # Op

    def must_be_first_in_pipeline(self):
        return True

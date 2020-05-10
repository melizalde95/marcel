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
Pop the directory stack, and cd to the new top directory.
'''


DETAILS = None


def popd():
    return Popd()


class PopdArgParser(marcel.core.ArgParser):

    def __init__(self, env):
        super().__init__('popd', env, None, SUMMARY, DETAILS)


class Popd(marcel.core.Op):

    def __init__(self):
        super().__init__()

    def __repr__(self):
        return 'popd()'

    # BaseOp

    def setup_1(self):
        pass

    def receive(self, _):
        self.env().dir_state().popd()
        for dir in self.env().dir_state().dirs():
            self.send(dir)

    # Op

    def must_be_first_in_pipeline(self):
        return True

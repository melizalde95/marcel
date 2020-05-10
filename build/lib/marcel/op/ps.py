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

import marcel.core
import marcel.object.process


SUMMARY = '''
Generate a stream of Process objects, representing running processes.
'''


DETAILS = None


def ps():
    return Ps()


class PsArgParser(marcel.core.ArgParser):

    def __init__(self, env):
        super().__init__('ps', env, None, SUMMARY, DETAILS)


class Ps(marcel.core.Op):

    def __init__(self):
        super().__init__()

    # BaseOp
    
    def setup_1(self):
        pass

    def receive(self, _):
        for process in marcel.object.process.processes():
            self.send(process)

    # Op

    def must_be_first_in_pipeline(self):
        return True

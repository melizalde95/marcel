"""C{ps [-o|--omit-self]}

Generates a stream of objects of type C{osh.process.Process}.

C{-o} omits the osh process itself from the process list.
"""

import os

import marcel.core
import marcel.object.process


def ps():
    return Ps()


class PsArgParser(marcel.core.OshArgParser):

    def __init__(self):
        super().__init__('ps')
        self.add_argument('-o', '--omit-self',
                          action='store_true')


class Ps(marcel.core.Op):

    argparser = PsArgParser()

    def __init__(self):
        super().__init__()
        self.omit_self = False

    # BaseOp interface
    
    def doc(self):
        return __doc__

    def setup_1(self):
        pass

    def receive(self, x):
        assert x is None, x
        this_pid = os.getpid()
        for process in marcel.object.process.processes():
            if process.pid != this_pid or not self.omit_self:
                self.send(process)

    # Op

    def arg_parser(self):
        return Ps.argparser
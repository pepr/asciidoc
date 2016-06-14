import os

import core.g

class Message:
    """Message functions."""

    def __init__(self):
        # Set to True or False to globally override line numbers method
        # argument. Has no effect when set to None.
        self.linenos = None
        self.messages = []
        self.prev_msg = ''

    def stdout(self,msg):
        print(msg)

    def stderr(self,msg=''):
        if msg == self.prev_msg:  # Suppress repeated messages.
            return
        self.messages.append(msg)
        if __name__ == '__main__':
            sys.stderr.write('%s: %s%s' % (core.g.progname, msg, os.linesep))
        self.prev_msg = msg

    def verbose(self, msg,linenos=True):
        if core.g.config.verbose:
            msg = self.format(msg,linenos=linenos)
            self.stderr(msg)

    def warning(self, msg,linenos=True,offset=0):
        msg = self.format(msg,'WARNING: ',linenos,offset=offset)
        core.g.document.has_warnings = True
        self.stderr(msg)

    def deprecated(self, msg, linenos=True):
        msg = self.format(msg, 'DEPRECATED: ', linenos)
        self.stderr(msg)

    def format(self, msg, prefix='', linenos=True, cursor=None, offset=0):
        """Return formatted message string."""
        if self.linenos is not False and ((linenos or self.linenos) and core.g.reader.cursor):
            if cursor is None:
                cursor = core.g.reader.cursor
            prefix += '%s: line %d: ' % (os.path.basename(cursor[0]),cursor[1]+offset)
        return prefix + msg

    def error(self, msg, cursor=None, halt=False):
        """
        Report fatal error.
        If halt=True raise EAsciiDoc exception.
        If halt=False don't exit application, continue in the hope of reporting
        all fatal errors finishing with a non-zero exit code.
        """
        if halt:
            raise EAsciiDoc(self.format(msg,linenos=False,cursor=cursor))
        else:
            msg = self.format(msg,'ERROR: ',cursor=cursor)
            self.stderr(msg)
            core.g.document.has_errors = True

    def unsafe(self, msg):
        self.error('unsafe: '+msg)


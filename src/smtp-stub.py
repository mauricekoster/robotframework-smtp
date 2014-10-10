import smtpd
import asyncore
import asynchat
import logging
import sys
import os
import socket
import time
from email.parser import Parser
import json

program = sys.argv[0]
__version__ = 'SMTP Stub version 0.1'

SMTP_PORT = 2525
SMTP_MGMT_PORT = 5252

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.abspath(__file__))
logger.info("basedir: %s" % base_dir)

NEWLINE = '\n'
EMPTYSTRING = ''
COMMASPACE = ', '

# Internal mail store
__mailstore = {}

class SMTPMgmtChannel(asynchat.async_chat):
    COMMAND = 0
    DATA = 1


    def __init__(self, server, conn, addr, mailstore):
        asynchat.async_chat.__init__(self, conn)
        self.__server = server
        self.__conn = conn
        self.__addr = addr
        self.__line = []
        self.__state = self.COMMAND
        self.__greeting = 0
        self.__data = ''
        self.__fqdn = socket.getfqdn()
        self.__mailstore = mailstore

        try:
            self.__peer = conn.getpeername()

        except socket.error, err:
            # a race condition  may occur if the other end is closing
            # before we can get the peername
            self.close()
            if err[0] != errno.ENOTCONN:
                raise
            return

        logger.debug('Peer: %s' % repr(self.__peer) )
        self.push('220 %s %s' % (self.__fqdn, __version__))
        self.set_terminator('\r\n')

    # Overrides base class for convenience
    def push(self, msg):
        asynchat.async_chat.push(self, msg + '\r\n')

    # Implementation of base class abstract method
    def collect_incoming_data(self, data):
        self.__line.append(data)

    # Implementation of base class abstract method
    def found_terminator(self):
        line = EMPTYSTRING.join(self.__line)
        logger.debug( 'Data: %s' % repr(line) )

        self.__line = []
        if self.__state == self.COMMAND:
            if not line:
                self.push('500 Error: bad syntax')
                return
            method = None
            i = line.find(' ')
            if i < 0:
                command = line.upper()
                arg = None
            else:
                command = line[:i].upper()
                arg = line[i+1:].strip()
            method = getattr(self, 'smtpmgmt_' + command, None)
            if not method:
                self.push('502 Error: command "%s" not implemented' % command)
                return
            method(arg)
            return
        else:
            if self.__state != self.DATA:
                self.push('451 Internal confusion')
                return
            # Remove extraneous carriage returns and de-transparency according
            # to RFC 821, Section 4.5.2.
            data = []
            for text in line.split('\r\n'):
                if text and text[0] == '.':
                    data.append(text[1:])
                else:
                    data.append(text)
            self.__data = NEWLINE.join(data)
            status = self.__server.process_data(self.__peer, self.__data)
            self.__state = self.COMMAND
            self.set_terminator('\r\n')
            if not status:
                self.push('250 Ok')
            else:
                self.push(status)

    # SMTP and ESMTP commands
    def smtpmgmt_HELO(self, arg):
        if not arg:
            self.push('501 Syntax: HELO hostname')
            return
        if self.__greeting:
            self.push('503 Duplicate HELO/EHLO')
        else:
            self.__greeting = arg
            self.push('250 %s' % self.__fqdn)

    def smtpmgmt_NOOP(self, arg):
        if arg:
            self.push('501 Syntax: NOOP')
        else:
            self.push('250 Ok')

    def smtpmgmt_RESET(self, arg):
      if arg:
        self.push('501 Syntax: RESET')
      else:
        logger.info('Cleared internal mailstore')
        self.__mailstore.clear()
        self.push('250 Mailstore cleared')

    def smtpmgmt_MSGCNT(self, arg):
      if arg:
        logger.info('Count messages for recipient: %s' % arg)

        if arg in self.__mailstore:
          cnt = len(self.__mailstore[arg])
        else:
          cnt = 0

        logger.debug('# messages: %d' % cnt)
        self.push('250 CNT = %d' % cnt)

      else:
        self.push('501 Syntax: MSGCNT <recipient>')

    def smtpmgmt_MSGLST(self, arg):
      if arg:
        if arg in self.__mailstore:
          cnt = len(self.__mailstore[arg])
        else:
          cnt = 0

        logger.debug('# messages: %d' % cnt)
        self.push('250 CNT %d' % cnt)
        idx = 1
        if cnt > 0:
          for msg in self.__mailstore[arg]:
            self.push("%03d : %s" % (idx, msg['subject']))
            idx += 1
          self.push('')

      else:
        self.push('501 Syntax: MSGLST <recipient>')

    def smtpmgmt_MSGGET(self, arg):
      if arg:
        self.push('250 "%s"' % arg)
        rcpt, idx = arg.split()
        msgs = self.__mailstore[rcpt]
        msg = msgs[int(idx)-1]
        self.push(msg['payload'])
        self.push('')

      else:
        self.push('501 Syntax: MSGGET <recipient> <msgnr>')

    def smtpmgmt_DUMP(self, arg):

      if len(self.__mailstore):
        self.push('250 List')
        if arg == 'json':
          txt = json.dumps(self.__mailstore, sort_keys=True,
                  indent=1, separators=(',', ': '))
          self.push(txt)

        else:
          for rcpt in self.__mailstore:
            self.push('%s:' % rcpt)
            msgs = self.__mailstore[rcpt]
            idx = 1
            for msg in msgs:
              self.push("\t%03d:%s" % (idx, msg['subject']) )
              idx += 1

        self.push('')

      else:
        self.push('250 No entries')

    def smtpmgmt_HELP(self, arg):
      self.push('250 Avaiable commands:')
      self.push('HELO    : Handshake')
      self.push('NOOP    : Does nothing')
      self.push('RESET   : Clears the mail store')
      self.push('MSGCNT  : Message count for a recipient')
      self.push('MSGLST  : List all id,subjects of a recipient')
      self.push('MSGGET  : Get payload of a numbered message from recipient')
      self.push('DUMP    : Dumps the current mail store')
      self.push('QUIT    : Quits the session')
      self.push('')         # blank line indicated end

    def smtpmgmt_QUIT(self, arg):
      # args is ignored
      self.push('221 Bye')
      self.close_when_done()

class SMTPMgmtServer(asyncore.dispatcher):
    def __init__(self, localaddr, mailstore):
        self._localaddr = localaddr
        self.__mailstore = mailstore
        asyncore.dispatcher.__init__(self)
        try:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            # try to re-use a server port if possible
            self.set_reuse_addr()
            self.bind(localaddr)
            self.listen(5)
        except:
            # cleanup asyncore.socket_map before raising
            self.close()
            raise
        else:
            logger.debug('%s started at %s\n\tLocal addr: %s\n'
                        % (self.__class__.__name__, time.ctime(time.time()),  localaddr)
                        )

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            conn, addr = pair
            logger.debug( 'Incoming connection from %s' % repr(addr) )
            channel = SMTPMgmtChannel(self, conn, addr, self.__mailstore)


class SMTPStubServer(smtpd.SMTPServer):
    def __init__(self, localaddr, remoteaddr, mailstore):
      smtpd.SMTPServer.__init__(self, localaddr, remoteaddr)
      self.__mailstore = mailstore

    def process_message(self, peer, mailfrom, rcpttos, data):

      msg = Parser().parsestr( data )
      print repr(msg)

      for rcpt in rcpttos:
        d = dict(peer=mailfrom,
          mailfrom=msg['From'],
          subject=msg['Subject'],
          payload=msg.get_payload(),
          data=data)

        if not rcpt in self.__mailstore:
          self.__mailstore[rcpt] = []

        self.__mailstore[rcpt].append(d)

      print 'Receiving message from:', peer
      print 'Message addressed from:', mailfrom
      print 'Message addressed to  :', rcpttos
      print 'Message length        :', len(data)

      print self.__mailstore

server = SMTPStubServer(('127.0.0.1', SMTP_PORT), None, __mailstore)
server_mgmt = SMTPMgmtServer(('127.0.0.1', SMTP_MGMT_PORT), __mailstore)


try:
  asyncore.loop()

except KeyboardInterrupt:
  print '^C received, shutting down the web server'
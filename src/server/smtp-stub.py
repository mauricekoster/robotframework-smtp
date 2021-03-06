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
import smtplib
import argparse

# === Configuration ========================================================================
argparser = argparse.ArgumentParser()
argparser.add_argument("--host", help="Hostname of listening address. (Default: localhost)", default='localhost')
argparser.add_argument("--port", type=int,  help="Portnumber of listening address. (Default: 25)", default=25)
argparser.add_argument("--mgmthost", help="Hostname of management interface. (Default: localhost)", default='localhost')
argparser.add_argument("--mgmtport", type=int,  help="Portnumber of management interface. (Default: 5252)", default=5252)

argparser.add_argument("--proxyhost", help="Hostname of smtp host address for relaying messages. (Default: localhost)", default='localhost')
argparser.add_argument("--proxyport", type=int,  help="Portnumber of smtp host address for relaying messages. (Default: 2525)", default=2525)
argparser.add_argument("-p", "--proxy", action="store_true", help="Enable proxy mode. This will relay messages to smtp server defined by proxyhost and proxyport.")
argparser.add_argument("-c", "--check", action="store_true", help="Check the arguments used")
args = argparser.parse_args()

print args

use_proxy=False
if args.proxy:
    use_proxy=True

# === Program info =============================================================
program = sys.argv[0]
__version__ = 'SMTP Stub version 0.2'

# === Log settings =============================================================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.abspath(__file__))

# === Configuration summary ====================================================
logger.info("version: %s" % __version__)
logger.info("basedir: %s" % base_dir)
logger.info("host: %s" % args.host)
logger.info("port: %s" % args.port)
logger.info("mgmt host: %s" % args.mgmthost)
logger.info("mgmt port: %s" % args.mgmtport)

if use_proxy:
    logger.info('proxy mode on.')
    logger.info("proxy host: %s" % args.proxyhost)
    logger.info("proxy port: %s" % args.proxyport)
else:
    logger.info('proxy mode off.')

if args.check:
    # Just a config check. Exiting here...
    sys.exit()

# === Private constants=========================================================
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
        self.push('100 %s %s' % (self.__fqdn, __version__))
        self.set_terminator('\r\n')

    # Overrides base class for convenience
    def push(self, msg):
        asynchat.async_chat.push(self, msg + '\r\n')

    def pushdata(self, data):
        asynchat.async_chat.push(self, data)

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
                self.push('500 Error: command "%s" not implemented' % command)
                return
            method(arg)
            return
        else:
            if self.__state != self.DATA:
                self.push('500 Internal confusion')
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
            self.push('500 Syntax: HELO hostname')
            return
        if self.__greeting:
            self.push('500 Duplicate HELO/EHLO')
        else:
            self.__greeting = arg
            self.push('250 %s' % self.__fqdn)

    def smtpmgmt_NOOP(self, arg):
        if arg:
            self.push('500 Syntax: NOOP')
        else:
            self.push('250 Ok')

    def smtpmgmt_ECHO(self, arg):
        if arg:
            self.push('250 %s' % arg)
        else:
            self.push('500 Syntax: ECHO <message>')

    def smtpmgmt_RESET(self, arg):
      if arg:
        self.push('500 Syntax: RESET')
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
        self.push('250 %d' % cnt)

      else:
        self.push('500 Syntax: MSGCNT <recipient>')

    def smtpmgmt_MSGLST(self, arg):
      if arg:
        args = arg.split()
        rcpt = args[0]
        mode = 'plain'
        if len(args)>1:
          mode = args[1]

        if rcpt in self.__mailstore:
          cnt = len(self.__mailstore[rcpt])
        else:
          cnt = 0

        logger.debug('# messages: %d' % cnt)

        if mode == 'json':
          if cnt == 0:
            self.push('210 %d' % cnt)

          else:
            txt = json.dumps(self.__mailstore[rcpt], sort_keys=True,
                    indent=1, separators=(',', ': '))

            self.push('200 %d' % len(txt))
            self.pushdata(txt)

        else:
          self.push('210 %d' % cnt)
          idx = 1
          if cnt > 0:
            for msg in self.__mailstore[rcpt]:
              self.push("%03d:%s" % (idx, msg['subject']))
              idx += 1

      else:
        self.push('500 Syntax: MSGLST <recipient> [<mode>]')

    def smtpmgmt_MSGGET(self, arg):
      if arg:

        args = arg.split()
        rcpt, idx = args[0:2]
        if len(args)==3:
          mode = args[2]
        else:
          mode = 'plain'

        if rcpt in self.__mailstore:
        msgs = self.__mailstore[rcpt]
            if len(msgs)==0:
                self.push('500 No messages')
            elif int(idx) > len(msgs):
                self.push('500 Index: maximum exceeded')
            else:
                if idx>0:
        msg = msgs[int(idx)-1]
                elif idx<0:
                    msg = msgs[idx]
                else:
                    msg = msgs[0]

        if mode == 'json':
          txt = json.dumps(msg, sort_keys=True,
                  indent=1, separators=(',', ': '))
          self.push('200 %d' % len(txt))
          self.pushdata(txt)

        elif mode == 'mime':
          msglen = len(msg['data'])
          self.push('200 %d' % msglen)
          self.pushdata(msg['data'])

        else:
          msglen = len(msg['payload'])
          self.push('200 %d' % msglen)
          self.pushdata(msg['payload'])
        else:
            self.push('500 Unknown recipient')

      else:
        self.push('500 Syntax: MSGGET <recipient> <msgnr>')

    def smtpmgmt_DUMP(self, arg):

      if len(self.__mailstore):

        if arg == 'json':
          txt = json.dumps(self.__mailstore, sort_keys=True,
                  indent=1, separators=(',', ': '))

          self.push('200 %d' % len(txt))
          self.pushdata(txt)

        else:
          lines = 0
          for rcpt in self.__mailstore:
            lines += 1
            msgs = self.__mailstore[rcpt]
            lines += len(msgs)

          self.push('210 %d' % lines)

          for rcpt in self.__mailstore:
            self.push('%s:' % rcpt)
            msgs = self.__mailstore[rcpt]
            idx = 1

            for msg in msgs:
              self.push("\t%03d:%s" % (idx, msg['subject']) )
              idx += 1



      else:
        self.push('250 No entries')

    def smtpmgmt_HELP(self, arg):

      cmds = [ 'Avaiable commands:'
        , 'HELO    : Handshake'
        , 'NOOP    : Does nothing'
        , 'RESET   : Clears the mail store'
        , 'MSGCNT  : Message count for a recipient'
        , 'MSGLST  : List all id,subjects of a recipient'
        , 'MSGGET  : Get payload of a numbered message from recipient'
        , 'DUMP    : Dumps the current mail store'
        , 'HELP    : Help'
        , 'ECHO    : Echos message'
        , 'QUIT    : Quits the session'
      ]
      self.push('210 %d' % len(cmds))
      for c in cmds:
        self.push(c)


    def smtpmgmt_QUIT(self, arg):
      # args is ignored
      self.push('100 Bye')
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
    proxyenabled = False
    proxyhost = None
    proxyport = None

    def __init__(self, localaddr, remoteaddr, mailstore):
      smtpd.SMTPServer.__init__(self, localaddr, remoteaddr)
      self.__mailstore = mailstore

    def process_message(self, peer, mailfrom, rcpttos, data):

      if self.proxyenabled:
          refused = self._deliver(mailfrom, rcpttos, data)
          if refused:
              logger.error(refused)

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

      # print 'Receiving message from:', peer
      # print 'Message addressed from:', mailfrom
      # print 'Message addressed to  :', rcpttos
      # print 'Message length        :', len(data)

    def _deliver(self, mailfrom, rcpttos, data):
        if not self.proxyenabled:
            return {}

        refused = {}
        try:
            s = smtplib.SMTP()
            s.connect(self.proxyhost, self.proxyport)
            try:
                refused = s.sendmail(mailfrom, rcpttos, data)
            finally:
                s.quit()
        except smtplib.SMTPRecipientsRefused, e:
            logger.debug('got SMTPRecipientsRefused')
            refused = e.recipients
        except (socket.error, smtplib.SMTPException), e:
            logger.debug('got', e.__class__)
            # All recipients were refused.  If the exception had an associated
            # error code, use it.  Otherwise,fake it with a non-triggering
            # exception code.
            errcode = getattr(e, 'smtp_code', -1)
            errmsg = getattr(e, 'smtp_error', 'ignore')
            for r in rcpttos:
                refused[r] = (errcode, errmsg)
        return refused

    def enable_proxy(self, proxyhost='localhost', proxyport=25):
        self.proxyhost = proxyhost
        self.proxyport = proxyport
        self.proxyenabled=True




# === Main======================================================================
server = SMTPStubServer((args.host, args.port), None, __mailstore)
if use_proxy:
    server.enable_proxy(args.proxyhost, args.proxyport)

server_mgmt = SMTPMgmtServer((args.mgmthost, args.mgmtport), __mailstore)


try:
  asyncore.loop()

except KeyboardInterrupt:
  print '^C received, shutting down the web server'

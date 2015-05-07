import logging
import socket
import platform
if platform.system()=='Java':
	import com.xhaus.jyson.JysonCodec as json
else:
	import json
import email.parser

class SmtpMsgmtException(Exception):  pass

class SmtpMgmtClient():
    __socket = None
    __socket_file = None

    def __init__(self, host, port):
        self.received_data = []
        self.logger = logging.getLogger('SmtpMgmtClient')
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.debug('connecting to %s', (host, port))
        self.__socket.connect((host, port))

        self.__socket_file = self.__socket.makefile('rw',0)
        result = self.read_response()

        self.__helo()


    def send_command(self, command, args=None):
      self.logger.debug('sending "%s"' % command)
      self.received_data = []
      if args:
        self.__socket.sendall('%s %s\r\n' % (command, args) )
      else:
        self.__socket.sendall('%s\r\n' % command)

    def read_response(self):
      line = self.__socket_file.readline()
      line = line.strip()
      self.logger.debug('recieved: "%s"' % line)
      ll = line.split()
      code = int(ll[0])
      rest = ' '.join(ll[1:])

      #self.logger.debug('code: %d' % int(code) )
      #self.logger.debug('rest: %s' % rest )

      if code == 100:
        # connect / handshake
        self.logger.info('Host >> %s <<' % rest )
        return rest

      if code == 200:
        # Command ok. Data in number of bytes given
        bytecnt = int(rest)
        self.logger.debug('Byte count: %d' % bytecnt )
        result = self.__socket_file.read(bytecnt)
        return result

      if code == 210:
        # Command ok. Data in number of lines given
        linecnt = int(rest)
        self.logger.debug('Line count: %d' % linecnt )

        lines = []
        for i in range(linecnt):
          line = self.__socket_file.readline()
          line = line.rstrip()
          self.logger.debug('line: %s' % line)
          lines.append(line)

        return lines

      if code == 250:
        # Command ok. No data returned
        self.logger.info('Result: %s' % rest )
        return rest

      if code == 500:
        # error
        raise SmtpMsgmtException(rest)
        return None

    def __helo(self, msg='SmtpMgmtClient'):
      self.send_command('HELO', msg )
      return self.read_response()

    def noop(self):
      self.send_command('NOOP')
      return self.read_response()

    def echo(self, msg='Echo'):
      self.send_command('ECHO', msg)
      return self.read_response()


    def reset(self):
      self.send_command('RESET')
      result = self.read_response()
      return

    def msgcnt(self, recipient):
      self.send_command('MSGCNT', recipient)
      result = self.read_response()
      return int(result)

    def msglst(self, recipient, mode=None):
      if mode:
        self.send_command('MSGLST', '%s %s' % (recipient, mode) )
      else:
        self.send_command('MSGLST', recipient)
      result = self.read_response()

      if mode == 'json':
        if result:
          d = json.loads(result)
        else:
          d = []

      else:
        d = []

        for line in result:
          d.append(line.strip()[4:])

      return d

    def msgget(self, recipient, msgid, mode=None):
      if mode:
        self.send_command('MSGGET', '%s %d %s' % (recipient, msgid, mode) )
      else:
        self.send_command('MSGGET', '%s %d' % (recipient, msgid))
      result = self.read_response()

      if mode == 'json':
        if result:
          d = json.loads(result)
        else:
          d = {}

      if mode == 'mime':
        fp = email.parser.Parser()
        print result
        msg = fp.parsestr(result)
        d = msg

      else:
        d = result

      return d

    def dump(self, mode=None):

      self.send_command('DUMP', mode)
      result = self.read_response()

      if result == 'No entries':
        return None

      if mode == 'json':
        d = json.loads(result)

      else:
        d = {}

        for line in result:
          if line[0] == '\t':
            d[rcpt].append(line.strip()[4:])
          else:
            rcpt = line[:-1]
            d[rcpt] = []

      return d

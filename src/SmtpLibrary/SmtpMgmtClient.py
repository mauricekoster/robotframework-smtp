import logging
import socket
import time

class SmtpMgmtClient(asynchat.async_chat):
    self.__socket = None

    def __init__(self, host, port):
        self.received_data = []
        self.logger = logging.getLogger('SmtpMgmtClient')
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.debug('connecting to %s', (host, port))
        self.connect((host, port))

        self.send_command('HELO %s' % 'SmtpMgmtClient' )

    def send_command(self, command, terminator=None):
      self.logger.debug('sending "%s"' % command)
      self.received_data = []
      self.sendall('%s\r\n' % command)

      while self.received_data[-1] != terminator:
        time.sleep(0.1)

      return self.received_message

    def dump(self):
      return self.send_command('DUMP', '\r\n\r\n')

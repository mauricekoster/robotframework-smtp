from robot.api import logger
from robot.libraries.Process import Process
import sys
import os
import subprocess

base_dir = os.path.dirname(os.path.abspath(__file__))

class SmtpKeywords():
  __stub_started = False
  __smtphost = None
  __smtpport = None
  __stub_handle = None

  def __init__(self, smtphost='localhost', smtpport=25):
    self.__smtphost = smtphost
    self.__smtpport = smtpport

  # Stub handling

  def start_smtp_stub(self):
    if not self.__stub_started:
      logger.info('Starting STUB on host: %s port: %d' % (self.__smtphost, self.__smtpport))
      stubscript = os.path.join(base_dir,'..','server','smtp-stub.py')
      self.__stub_handle = Process().start_process(sys.executable, stubscript, cwd=base_dir, alias='stub')
      print 'Handle: %d' % self.__stub_handle
    else:
      logger.warn('Stub already started')

    self.__stub_started = True

  def stop_smtp_stub(self):
    print 'Handle: %d' % self.__stub_handle
    if self.__stub_started:
      logger.info('Stopping STUB')
      Process().terminate_process(self.__stub_handle, kill=True)
    else:
      logger.warn('Stub already stopped')

    self.__stub_started = False

  def reset_smtp_stub(self):
    """ Reset Smtp Stub

    Reset (clears) the mail store
    """
    pass

  # Smtp Manager

  def get_message_count(self, recipient):
    pass

  def get_message_list(self, recipient):
    pass

  def get_message_content(self, recipient, messageid):
    pass


  # Smtp Client
  def get_mail_address(self, sendername, senderemail):
    pass

  def send_message(self, senderaddr, recipients, subject, body):
    # Create the message
    msg = MIMEText(body)
    msg['To'] = email.utils.formataddr(('Recipient', 'recipient@example.com'))
    msg['From'] = email.utils.formataddr(('Author', sender))
    msg['Subject'] = 'Simple test message'

    server = smtplib.SMTP('127.0.0.1', 2525)
    server.set_debuglevel(True) # show communication with the server
    try:
        server.sendmail('author@example.com', ['recipient1@example.com', 'recipient2@example.com'], msg.as_string())
    finally:
        server.quit()
    pass

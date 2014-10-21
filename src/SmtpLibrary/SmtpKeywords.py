from robot.api import logger
from robot.libraries.Process import Process
import sys
import os
import subprocess
from SmtpLibrary import SmtpMgmtClient
import smtplib
import email.utils
from email.mime.text import MIMEText

base_dir = os.path.dirname(os.path.abspath(__file__))

class SmtpKeywords():
  __stub_started = False
  __smtphost = None
  __smtpport = None
  __mgmtclient = None

  def __init__(self, smtphost='localhost', smtpport=25, smtpmgmtport=5252):
    self.__smtphost = smtphost
    self.__smtpport = smtpport
    self.__smtpmgmtport = smtpmgmtport

  def __open_smtpmgmt_session(self):
    self.__mgmtclient = SmtpMgmtClient.SmtpMgmtClient(self.__smtphost, self.__smtpmgmtport)


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
      #Process().terminate_process(self.__stub_handle, kill=True)
      Process().terminate_all_processes(kill=True)
    else:
      logger.warn('Stub already stopped')

    self.__stub_started = False

  def clear_mailstore(self):
    """
    Clears the internal mailstore
    """
    logger.info('Clear mail store')
    if not self.__mgmtclient:
      self.__open_smtpmgmt_session()

    self.__mgmtclient.reset()

  # Smtp Manager

  def get_message_count(self, recipient):
    """
    Get message count for a recipient
    """
    logger.info('Get message count for "%s"' % recipient)
    if not self.__mgmtclient:
      self.__open_smtpmgmt_session()

    return self.__mgmtclient.msgcnt(recipient)

  def get_json_message_list(self, recipient):
    return self.get_message_list(recipient, 'json')

  def get_message_list(self, recipient, mode=None):
    """
    Get message list for recipient
    """
    logger.info('Get message list for "%s"' % recipient)
    if not self.__mgmtclient:
      self.__open_smtpmgmt_session()

    return self.__mgmtclient.msglst(recipient, mode)

  def get_message_content(self, recipient, messageid):
    return self.get_message(recipient, messageid)

  def get_mime_message(self, recipient, messageid):
    return self.get_message(recipient, messageid, 'mime')

  def get_json_message(self, recipient, messageid):
    return self.get_message(recipient, messageid, 'json')

  def get_message(self, recipient, messageid, mode=None):
    msgid = int(messageid)
    logger.info('Get message for "%s" msgid: %d' % (recipient, msgid))
    if not self.__mgmtclient:
      self.__open_smtpmgmt_session()

    return self.__mgmtclient.msgget(recipient, msgid, mode)

  def get_message_subject(self, recipient, messageid):
    msgid = int(messageid)
    logger.info('Get message subject for "%s" msgid: %d' % (recipient, msgid))
    if not self.__mgmtclient:
      self.__open_smtpmgmt_session()

    msg = self.__mgmtclient.msgget(recipient, msgid, 'mime')
    return msg['Subject']
    
  # Smtp Client
  def get_mail_address(self, name, emailaddress):
    return email.utils.formataddr((name, emailaddress))

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

  def send_simple_message(self, senderaddr, recipient, subject='No subject', body=None):
    # Create the message
    msg = MIMEText(body)
    msg['To'] = email.utils.formataddr(('Recipient', recipient))
    msg['From'] = email.utils.formataddr(('Author', senderaddr))
    msg['Subject'] = subject

    server = smtplib.SMTP(self.__smtphost, self.__smtpport)
    #server.set_debuglevel(True) # show communication with the server
    try:
        server.sendmail(senderaddr, [recipient], msg.as_string())
    finally:
        server.quit()

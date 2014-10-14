from SmtpLibrary import SmtpMgmtClient
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)

client = SmtpMgmtClient.SmtpMgmtClient('localhost', 5252)

client.dump()
print 'Bye'

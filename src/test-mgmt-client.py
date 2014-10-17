from SmtpLibrary import SmtpMgmtClient
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)

client = SmtpMgmtClient.SmtpMgmtClient('localhost', 5252)

print client.echo('Hello, world!')

d = client.dump('json')
print d

cnt = client.msgcnt('recipient1@example.com')
print 'Count: %d' % cnt

lst = client.msglst('recipient1@example.com', 'json')
print lst

if cnt>0:
  msg = client.msgget('recipient1@example.com', 1)
  print 'Message plain:'
  print msg

  msg = client.msgget('recipient1@example.com', 1, 'json')
  print 'Message json:'
  print msg

  msg = client.msgget('recipient1@example.com', 1, 'mime')
  print 'Message mime:'
  print repr(msg)

client.reset()

cnt = client.msgcnt('recipient1@example.com')
print 'Count: %d' % cnt

print 'Bye'

import SmtpLibrary
import time

p = SmtpLibrary.SmtpLibrary()
p.start_smtp_stub()
time.sleep(3)
p.stop_smtp_stub()

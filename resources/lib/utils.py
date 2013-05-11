import xbmc
import xbmcvfs
import xbmcaddon
import os
    
__addon_id__= 'service.watchedlist'
__Addon = xbmcaddon.Addon(__addon_id__)

def data_dir():
    __datapath__ = xbmc.translatePath( __Addon.getAddonInfo('profile') ).decode('utf-8')
    if not xbmcvfs.exists(__datapath__):
        xbmcvfs.mkdir(__datapath__)
    return __datapath__

def addon_dir():
    return __Addon.getAddonInfo('path')

def log(message,loglevel=xbmc.LOGNOTICE):
    # loglevels: LOGDEBUG, xbmc.LOGNOTICE
    xbmc.log(encode(__addon_id__ + ": " + message),level=loglevel)


def showNotification(title,message, time=4000):
    __addoniconpath__ = os.path.join(addon_dir(),"icon.png")
    xbmc.executebuiltin('Notification("' + encode(title) + '","' + encode(message) + '",'+str(time)+',"' + __addoniconpath__ + '")')
    if getSetting('debug') == 'true':
        xbmc.sleep(250) # time to read the message
        log('%s: %s' % (title, message) )

def setSetting(name,value):
    __Addon.setSetting(name,value)

def getSetting(name):
    return __Addon.getSetting(name)
    
def getString(string_id):
    return __Addon.getLocalizedString(string_id)

def encode(string):
    return string.encode('UTF-8','replace')

def footprint():
    log('data_dir() = %s' % data_dir(), xbmc.LOGDEBUG)
    log('addon_dir() = %s' % addon_dir(), xbmc.LOGDEBUG)
    log('debug = %s' % getSetting('debug'), xbmc.LOGDEBUG)
    log('w_movies = %s' % getSetting('w_movies'), xbmc.LOGDEBUG)
    log('w_episodes = %s' % getSetting('w_episodes'), xbmc.LOGDEBUG)
    log('autostart = %s' % getSetting('autostart'), xbmc.LOGDEBUG)
    log('periodic = %s' % getSetting('periodic'), xbmc.LOGDEBUG)
    log('interval = %s' % getSetting('interval'), xbmc.LOGDEBUG)
    log('delay = %s' % getSetting('delay'), xbmc.LOGDEBUG)
    log('progressdialog = %s' % getSetting('progressdialog'), xbmc.LOGDEBUG)
    log('extdb = %s' % getSetting('extdb'), xbmc.LOGDEBUG)
    log('dbpath = %s' % getSetting('dbpath'), xbmc.LOGDEBUG)
    log('dbfilename = %s' % getSetting('dbfilename'), xbmc.LOGDEBUG)
    log('dbbackup = %s' % getSetting('dbbackup'), xbmc.LOGDEBUG)
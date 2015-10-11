"""
This file is entry point for manual start via the programs menu
"""

# work around bugalloo error when called for dropbox
if len(sys.argv) == 2:
    sys.argv.append('')

import xbmcgui
import resources.lib.utils as utils
from service import WatchedList

__remotedebug__ = False
# append pydev remote debugger
if __remotedebug__:
    utils.log("Initialize remote debugging.")
    # Make pydev debugger works for auto reload.
    try:
        import pydevd
        pydevd.settrace('localhost', port=60678, stdoutToServer=True, stderrToServer=True)
    except ImportError:
        sys.stderr.write("Error: " +
            "You must add org.python.pydev.debug.pysrc to your PYTHONPATH.")
        utils.showNotification('WatchedList Error', 'remote debug could not be imported.')
        sys.exit(1)
    except:
        utils.showNotification('WatchedList Error', 'remote debug in pydev is activated, but remote server not responding.')
        sys.exit(1)

# check to see if invoked from settings to setup dropbox
dropbox = False
if len(sys.argv) > 1:
    if sys.argv[1] == 'dropbox':
        dropbox = True

# Create WatchedList Class
WL = WatchedList()

if dropbox:
    WL.authorizeDropbox()
elif (not utils.getSetting("autostart") == 'true') or xbmcgui.Dialog().yesno( utils.getString(32101),utils.getString(32001) ):
    # Check if we should run updates (only ask if autostart is on)
    # run the program
    utils.log("Update Library Manual Run.")
    # WL.runProgram() # function executed on autostart. For Test purpose
    WL.runUpdate(True) # one time update

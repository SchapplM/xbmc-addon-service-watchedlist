import xbmcgui
import resources.lib.utils as utils
from service import WatchedList

__remotedebug__ = False
# append pydev remote debugger
if __remotedebug__:
    # Make pydev debugger works for auto reload.
    # Note pydevd module need to be copied in XBMC\system\python\Lib\pysrc
    try:
        import pysrc.pydevd as pydevd
    # stdoutToServer and stderrToServer redirect stdout and stderr to eclipse console
        pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
    except ImportError:
        sys.stderr.write("Error: " +
            "You must add org.python.pydev.debug.pysrc to your PYTHONPATH.")
        sys.exit(1)


WL = WatchedList()

#check if we should run updates
if True or ( xbmcgui.Dialog().yesno( utils.getString(32101),utils.getString(31001) ) ):
    #run the program
    utils.log("Update Library Manual Run...")
    WL.runUpdate()


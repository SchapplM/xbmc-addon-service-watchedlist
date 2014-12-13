"""
This file is entry point for automatic start via XBMC
"""

import resources.lib.utils as utils
from service import WatchedList
import xbmc

__remotedebug__ = False
# Append pydev remote debugger
if __remotedebug__:
    # Make pydev debugger works for auto reload.
    # Note pydevd module need to be copied in XBMC\system\python\Lib\pysrc
    try:
        import pysrc.pydevd as pydevd
    # stdoutToServer and stderrToServer redirect stdout and stderr to eclipse console
        pydevd.settrace('localhost', port=60678, stdoutToServer=True, stderrToServer=True)
    except ImportError:
        sys.stderr.write("Error: " +
            "You must add org.python.pydev.debug.pysrc to your PYTHONPATH.")
        sys.exit(1)
    except:
        sys.stderr.write("Error importing the debugger")

# Run the program
xbmc.sleep(1500) # wait 1.5 seconds to prevent import-errors
utils.log("WatchedList Database Service starting...")
WatchedList().runProgram()

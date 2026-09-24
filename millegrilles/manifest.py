# manifest.py

include("$(PORT_DIR)/boards/manifest.py")

require('ntptime')
require('urequests')
require('ssl')
#require('bluetooth')
#require('aioble')

c_module("src/")

freeze("lib/")
freeze("python/")

# manifest.py

include("$(PORT_DIR)/boards/manifest.py")

require('ntptime')

c_module("src/")

freeze("lib/")
freeze("python/")

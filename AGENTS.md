# MilleGrilles RPi PICO application

This project is a micropython application that works with RaspberryPi PICO microcontrolers. It connects to a MilleGrilles sensor backend through https and websockets. Configuration is done through Bluetooth.

## Project Structure Overview

The `millegrilles.rpipico` project is a MicroPython-based application designed for Raspberry Pi Pico microcontrollers. It facilitates connection to a MilleGrilles sensor backend via HTTPS and WebSockets, with Bluetooth for configuration.

### Key Directories

- `micropython/`: Contains the MicroPython source code, used as a base for building the custom firmware.
- `millegrilles/`: The primary application directory.
    - `src/`: Contains C/C++ source files for MicroPython extensions and OS-specific porting (e.g., `os_port_rpipico.c`).
    - `python/`: Contains the main MicroPython scripts that execute on the device, such as `millegrilles/python/appareil.main.py`.
    - `lib/`: A collection of MicroPython libraries and modules required by the application (e.g., display drivers, websocket support).
- `oryx-embedded/`: Contains common code and OS porting layers, likely related to the Oryx-Embedded ecosystem.
- `tests/`: Contains test suites for the application.
- `doc/`: Documentation for the project.

### Build and Setup

The project includes several scripts to facilitate building and setting up the environment:
- `build.sh`: Main build script.
- `setup_pico.sh`: Script to set up the Raspberry Pi Pico environment.
import uasyncio as asyncio
from struct import unpack


class BMP180:
    
    def __init__(self, i2c_bus, addr=0x77):
        self.__i2c_bus = i2c_bus
        self.__addr = addr
        
        if addr not in i2c_bus.scan():
            raise Exception("BMP180 absent")

    def readBmp180Id(self):
      # Chip ID Register Address
      REG_ID     = 0xD0
      (chip_id, chip_version) = self.__i2c_bus.readfrom_mem(self.__addr, REG_ID, 2)
      return (chip_id, chip_version)

    async def readBmp180(self):
      # Register Addresses
      REG_CALIB  = 0xAA
      REG_MEAS   = 0xF4
      REG_MSB    = 0xF6
      REG_LSB    = 0xF7
      # Control Register Address
      CRV_TEMP   = bytearray([0x2E])
      CRV_PRES   = 0x34 
      # Oversample setting
      OVERSAMPLE = 3    # 0 - 3
      
      # Read calibration data
      # Read calibration data from EEPROM
      cal = self.__i2c_bus.readfrom_mem(self.__addr, REG_CALIB, 22)

      # Convert byte data to word values
      (AC1, AC2, AC3, AC4, AC5, AC6, B1, B2, MB, MC, MD) = unpack(">hhhHHHhhhhh", cal)

      # Read temperature
      self.__i2c_bus.writeto_mem(self.__addr, REG_MEAS, CRV_TEMP)
      
      await asyncio.sleep_ms(5)
      # (msb, lsb) = bus.read_i2c_block_data(addr, REG_MSB, 2)
      val = self.__i2c_bus.readfrom_mem(self.__addr, REG_MSB, 2)
      (msb, lsb) = val
      val2 = unpack('>h', val)
      UT = (msb << 8) + lsb

      # Read pressure
      # bus.write_byte_data(addr, REG_MEAS, CRV_PRES + (OVERSAMPLE << 6))
      self.__i2c_bus.writeto_mem(self.__addr, REG_MEAS, bytearray([CRV_PRES + (OVERSAMPLE << 6)]))
      await asyncio.sleep_ms(40)
      # (msb, lsb, xsb) = bus.read_i2c_block_data(addr, REG_MSB, 3)
      (msb, lsb, xsb) = self.__i2c_bus.readfrom_mem(self.__addr, REG_MSB, 3)
      UP = ((msb << 16) + (lsb << 8) + xsb) >> (8 - OVERSAMPLE)

      # Refine temperature
      X1 = ((UT - AC6) * AC5) >> 15
      X2 = (MC << 11) / (X1 + MD)
      B5 = X1 + X2
      temperature = int(B5 + 8) >> 4
      temperature = temperature / 10.0

      # Refine pressure
      B6  = B5 - 4000
      B62 = int(B6 * B6) >> 12
      X1  = (B2 * B62) >> 11
      X2  = int(AC2 * B6) >> 11
      X3  = X1 + X2
      B3  = (((AC1 * 4 + X3) << OVERSAMPLE) + 2) >> 2

      X1 = int(AC3 * B6) >> 13
      X2 = (B1 * B62) >> 16
      X3 = ((X1 + X2) + 2) >> 2
      B4 = (AC4 * (X3 + 32768)) >> 15
      B7 = (UP - B3) * (50000 >> OVERSAMPLE)

      P = (B7 * 2) / B4

      X1 = (int(P) >> 8) * (int(P) >> 8)
      X1 = (X1 * 3038) >> 16
      X2 = int(-7357 * P) >> 16
      pressure = int(P + ((X1 + X2 + 3791) >> 4))

      # Altitude
      altitude = 44330.0 * (1.0 - pow(pressure / 101325.0, (1.0/5.255)))
      altitude = round(altitude, 2)

      # pressure_hecto = int(pressure / 100.0)  # convertir en int hectopascal (hPa)

      return (temperature,pressure,altitude)


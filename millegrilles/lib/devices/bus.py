# Module de gestions des bus
class Bus:
    
    def __init__(self, params):
        self.__instance = None
    
    @staticmethod
    def parse(params):
        driver_name = params['driver'].upper()
        
        if driver_name == 'I2C':
            from machine import I2C, Pin
            bus_no = params.get('bus') or 0
            freq = params.get('freq') or 100000
            sda_pin = params['sda_pin']
            scl_pin = params['scl_pin']
            return I2C(bus_no, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=freq)
        else:
            raise Exception('bus %s not implemented' % driver_name)


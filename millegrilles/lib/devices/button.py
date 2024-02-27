import machine
import uasyncio as asyncio
from machine import Pin
from micropython import const
from sys import print_exception

from millegrilles.pins import WaiterPin
from handler_devices import Driver


class DriverButtonPin(Driver):

    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__waiter_pin = None

    async def load(self):
        pin_no = self._params['pin']
        self.__waiter_pin = WaiterPin(pin_no)

    @property
    def device_id(self):
        pin = self._params['pin']
        return 'button_p%d' % pin

    async def run_device(self, *args):
        while True:
            try:
                cycles = await self.__waiter_pin.wait()
                if cycles > 30:  # Long press
                    await self.long_press()
                else:  # Short press
                    await self.short_press()
            except Exception as e:
                print(const("DriverButtonPin.run_device error"))
                print_exception(e)

    async def long_press(self):
        print("Long press ", self.device_id)
        try:
            press_config = self._params['long']
            await self.process_press(press_config)
        except KeyError:
            pass  # Aucune action definie

    async def short_press(self):
        print("Short press ", self.device_id)
        try:
            press_config = self._params['short']
            await self.process_press(press_config)
        except KeyError:
            pass  # Aucune action definie

    async def process_press(self, params):
        did = params.get('did')
        action = params['action']
        if action == 'bleconfig':
            print(const("Activer configuration BLE"))
        elif action == 'toggle':
            await self.toggle_switch(did)
        else:
            print(const("button action %s inconnue") % action)

    async def toggle_switch(self, did: str):
        try:
            device = self._appareil.get_device(did)
        except KeyError:
            print(const("button toggle DID inconnu "), did)
            return

        valeur_courante = device.value
        if valeur_courante == 0:
            device.value = 1
        else:
            device.value = 0

        self._appareil.trigger_stale_event()

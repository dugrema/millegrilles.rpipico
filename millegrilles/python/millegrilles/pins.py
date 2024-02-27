import uasyncio as asyncio
from machine import Pin


class WaiterPin:
    """
    Utilise une pin comme input. Active PULL_UP.
    """

    def __init__(self, pin: int):
        self.button = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.event = asyncio.ThreadSafeFlag()
        self.button.irq(self.__interrupt, trigger=Pin.IRQ_FALLING)

    def __interrupt(self, pin):
        if self.button == pin:
            self.event.set()

    async def wait(self):
        """
        Utiliser cette methode pour attendre un evenement.
        :returns: Nombre de cycles de 100ms durant lesquels le bouton a ete actif.
        """
        while True:
            self.event.clear()
            await self.event.wait()

            # Detecter duree de l'activite du bouton
            cycles = 0
            while self.button.value() == 0:  # Valeur 0 => ON (mode PULL_UP)
                cycles += 1
                if cycles > 30:  # Limite max (long press)
                    return cycles
                await asyncio.sleep_ms(100)

            # Debounce: cycles == 0 indique un bounce du IRQ
            if cycles > 30:
                return 2  # Long press
            elif cycles > 0:
                return 1  # Short press

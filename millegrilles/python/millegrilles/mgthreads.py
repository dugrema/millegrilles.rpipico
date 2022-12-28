import time
import uasyncio
from gc import collect
import _thread

class ThreadExecutor():
    """
    Execute une methode a la fois en mode blocking dans core1.
    """
    
    def __init__(self, ioloop_local=False):
        # Event asyncio externe
        self.__core_asyncio = uasyncio.Event()
        self.__core_asyncio.set()  # Pret par defaut
        
        # self.__internal_set = True
        self.__internal_set = True
        self.__internal = uasyncio.ThreadSafeFlag()
        
        # Lock interne entre cores
        self.__ioloop_local = ioloop_local
        self.__runnable = None
        self.__args = ()
        self.__kwargs = dict()
        self.__timeout = None
        self.__resultat = None
        self.__exception = None
    
    def run_io_loop(self):
        """ Faire executer sur core a gerer """
        self.__ioloop_local = True
        while self.__ioloop_local:
            time.sleep(0.5)
            if self.__internal_set is False:
                try:
                    # Executer runnable
                    self.__resultat = self.__runnable(*self.__args, **self.__kwargs)
                except Exception as e:
                    self.__exception = e
                finally:
                    self.__internal_set = True
                    self.__internal.set()

    def stop(self):
        self.__ioloop_local = False

    async def run(self, runnable, *args, timeout=None, **kwargs):
        """
        Execute une methode blocking lorsque core1 est disponible.
        @param runnable: Methode a executer
        @args : Liste d'arguments pour la methode
        @return coro - et le resultat de la methode si applicable
        @raises : Erreur provenant de la methode
        """
        
        # Attendre que core1 soit disponible
        await self.__core_asyncio.wait()
        
        try:
            # Mettre en attente autres runners
            self.__core_asyncio.clear()

            output = dict()
            if self.__ioloop_local is True:
                self.__runnable = runnable
                self.__args = args
                self.__kwargs = kwargs
                self.__timeout = timeout
                
            # Demarrer la thread - non blocking
            self.__internal.clear()
            self.__internal_set = False
                
            if self.__ioloop_local is False:
                # Mode thread sans ioloop local
                print('start_new_thread core1')
                _thread.start_new_thread(self.__wrap_execution, (runnable, output, args, kwargs))
            
            # Attendre que l'execution soit completee
            await self.__internal.wait()
            
            # Core1 libere, run GC
            collect()

            if self.__ioloop_local is True:
                output['exception'] = self.__exception
                output['resultat'] = self.__resultat
                self.__resultat = None
                self.__exception = None
                self.__timeout = None
            
        except Exception as e:
            print("Erreur %s" % e)
            if output.get('exception') is None:
                output['exception'] = e
        finally:
            # S'assurer de liberer l'event
            self.__core_asyncio.set()
        
        if output.get('exception'):
            raise output.get('exception')
        
        return output.get('resultat')
    
    def __wrap_execution(self, runnable, output, args, kwargs):
        print("__wrap_execution debut")
        try:
            resultat = runnable(*args, **kwargs)
            output['resultat'] = resultat
        except Exception as e:
            print("Exception : %s" % e)
            #_thread.exit()  # S'assurer d'arreter la thread
            output['exception'] = e
        finally:
            print("__wrap_execution done!")
            self.__internal.set()  # Reset execution

# Programme appareil millegrille
import uasyncio as asyncio


async def initialisation():
    """
    Mode initial si aucun parametres charges
    """
    pass


async def recuperer_ca():
    """
    Mode de chargement du certificat CA.
    """
    pass


async def signature_certificat():
    """
    Mode d'attente de signature de certificat
    """
    pass


async def polling():
    """
    Main thread d'execution du polling/commandes
    """
    pass


async def entretien():
    """
    Thread d'entretient durant polling
    """
    pass


async def detecter_mode_operation():
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    import os
    try:
        os.stat('wifi.txt')
        os.stat('idmg.txt')
        os.stat('conn.json')
    except:
        print("Mode initialisation")
        return 1
    
    try:
        os.stat('certs/ca.der')
    except:
        print("Mode recuperer ca.der")
        return 2
    
    try:
        os.stat("certs/cert.pem")
    except:
        print("Mode signer certificat")
        return 3

    return 99  # Mode polling


async def main():
    pass


if __name__ == '__main__':
    asyncio.run(main())
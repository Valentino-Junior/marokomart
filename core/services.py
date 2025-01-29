# services.py
import requests
import logging
from .utils import PayHeroConfig

logger = logging.getLogger(__name__)

def check_transaction_status(reference):
    """
    Check PayHero transaction status
    """
    try:
        response = requests.get(
            f'https://backend.payhero.co.ke/api/v2/transaction-status',
            params={'reference': reference},
            headers={
                'Authorization': PayHeroConfig.generate_auth_token()
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Transaction status for {reference}: {data.get('status')}")
            return data
        else:
            logger.error(f"Failed to get transaction status: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error checking transaction status: {str(e)}")
        return None
from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

class Google:
    """ Google class to fetch user details from google and return it """

    @staticmethod
    def validate(auth_token):
        """
        validate method query the google OAuth2 api to fetch the user info
        """
        
        try:
            id_info = id_token.verify_oauth2_token(
                auth_token, 
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
            return id_info
        except Exception as e:
            logger.warning("Google auth failed", exc_info=True)
            return None

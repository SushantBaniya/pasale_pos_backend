from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.authtoken.models import Token


class RawOrTokenAuthentication(BaseAuthentication):
    """
    Supports both standard DRF token auth and raw token header values.

    Accepted Authorization header formats:
    - Token <token_key>
    - <token_key>
    """

    keyword = b"token"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth:
            return None

        # JWT is handled by JWTAuthentication before this class.
        if len(auth) == 2 and auth[0].lower() == b"bearer":
            return None

        # Backward compatibility: allow raw token key with no prefix.
        if len(auth) == 1:
            try:
                token_key = auth[0].decode()
            except UnicodeError:
                raise exceptions.AuthenticationFailed("Invalid token header.")
            return self._authenticate_credentials(token_key)

        if len(auth) == 2 and auth[0].lower() == self.keyword:
            try:
                token_key = auth[1].decode()
            except UnicodeError:
                raise exceptions.AuthenticationFailed("Invalid token header.")
            return self._authenticate_credentials(token_key)

        return None

    def _authenticate_credentials(self, key):
        try:
            token = Token.objects.select_related("user").get(key=key)
        except Token.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token.")

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed("User inactive or deleted.")

        return (token.user, token)

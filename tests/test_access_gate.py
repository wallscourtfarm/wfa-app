"""Access gate: staff pages need a valid Cloudflare Access token (team signature, issuer, expiry, known audience);
pupil live pages, the evidence API and /ping stay open; report mode refuses nothing.
Run: python3 tests/test_access_gate.py   Needs PyJWT[crypto]. A throwaway key, no network."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
os.environ.pop('RAILWAY_ENVIRONMENT_NAME', None)

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

import access_gate
from app import app

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
AUD = next(iter(access_gate.KNOWN_AUDS))


class FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return type('K', (), {'key': KEY.public_key()})()


access_gate._jwks = FakeJwks()


def tok(key=KEY, aud=AUD, iss=access_gate.ISSUER, exp=3600):
    now = int(time.time())
    return jwt.encode({'aud': [aud], 'iss': iss, 'exp': now + exp, 'iat': now, 'email': 'staff@example.org'},
                      key, algorithm='RS256')


c = app.test_client()


def status(path, token=None, method='get'):
    headers = {'Cf-Access-Jwt-Assertion': token} if token else {}
    return getattr(c, method)(path, headers=headers).status_code


os.environ['ACCESS_GATE'] = 'enforce'
assert status('/ping') == 200
assert status('/api/class/roster-status') == 403
assert status('/api/class/roster-sync', method='post') == 403
assert status('/api/claude', method='post') == 403
assert status('/class-manager', 'not-a-jwt') == 403
assert status('/class-manager', tok(key=OTHER)) == 403            # not signed by the team
assert status('/class-manager', tok(aud='someone-elses-app')) == 403
assert status('/class-manager', tok(iss='https://evil.cloudflareaccess.com')) == 403
assert status('/class-manager', tok(exp=-120)) == 403             # expired
assert status('/livefoo') == 403                                   # not a bypass path
print('refused without a valid token OK')

assert status('/class-manager', tok()) != 403
assert status('/api/evidence/spelling/Y5') == 401                  # open here, its own token check answers
assert status('/live/bee/nosuchsession/p01') != 403
assert status('/api/live/submit', method='post') != 403
print('valid token and open paths OK')

os.environ['ACCESS_GATE'] = 'report'
assert status('/class-manager') != 403
os.environ['ACCESS_GATE'] = 'off'
assert status('/class-manager') != 403
print('report and off modes refuse nothing OK')
print('ALL OK')

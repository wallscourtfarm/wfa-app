"""
access_gate.py — only answer requests that came through Cloudflare Access.

Cloudflare Access on app.wallscourt-farm-academy.co.uk is the app's only
staff login, but Railway also serves the app at its own address
(web-production-35df2.up.railway.app), which skips Cloudflare. This check
runs before every request and needs a valid Cloudflare Access sign-in token
(the Cf-Access-Jwt-Assertion header: signature, issuer, expiry, audience),
which only Cloudflare can add.

Paths Cloudflare deliberately lets through without a sign-in (its bypass
apps) stay open here too: the pupil live-session pages, the evidence API
(it has its own token) and /ping.

ACCESS_GATE setting: 'enforce' (default since 30.10.26g) refuses; 'report'
logs what would be refused and lets everything through; 'off' does nothing.
Report mode ran first and a real staff sign-in through app.* passed.
"""

import logging
import os

from flask import request

log = logging.getLogger('access_gate')

TEAM = os.environ.get('CF_ACCESS_TEAM', 'square-snowflake-8bcb')
ISSUER = f'https://{TEAM}.cloudflareaccess.com'

# Audience tags of the Access apps that cover app.* (identifiers, not secrets).
KNOWN_AUDS = {
    '9690495618c28b3c82ed51f81bdb84e0f38c869952e47cbf2190214c5da29eb9',   # WFA App Dashboard (whole domain)
    'f97d5389df08ef410bcbbc04a3602b69b7135108a4efb0150d4ae4b00b78931a',   # /menu
}
KNOWN_AUDS |= {a.strip() for a in os.environ.get('CF_ACCESS_AUDS', '').split(',') if a.strip()}

# Matches Cloudflare's bypass apps: app.*/live, app.*/api/live, app.*/api/evidence.
OPEN_PREFIXES = ('/live', '/api/live', '/api/evidence')
OPEN_PATHS = {'/ping'}

_jwks = None
_seen_auds = set()


def is_open(path):
    if path in OPEN_PATHS:
        return True
    return any(path == p or path.startswith(p + '/') for p in OPEN_PREFIXES)


def check_token(token):
    """(ok, reason, claims). ok only if signed by the team, unexpired and for a
    known audience. reason is a short word for the logs."""
    global _jwks
    if not token:
        return False, 'no-token', None
    try:
        import jwt
        if _jwks is None:
            _jwks = jwt.PyJWKClient(ISSUER + '/cdn-cgi/access/certs')
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], issuer=ISSUER,
                            options={'verify_aud': False})
    except Exception as e:
        return False, f'bad-token ({type(e).__name__})', None
    auds = claims.get('aud') or []
    auds = [auds] if isinstance(auds, str) else list(auds)
    if not any(a in KNOWN_AUDS for a in auds):
        return False, 'unknown-aud', claims
    return True, 'ok', claims


def mode():
    m = os.environ.get('ACCESS_GATE', 'enforce').strip().lower()
    return m if m in ('report', 'enforce', 'off') else 'enforce'


def _before():
    m = mode()
    if m == 'off' or is_open(request.path):
        return None
    ok, reason, claims = check_token(request.headers.get('Cf-Access-Jwt-Assertion', ''))
    if claims:
        for a in ([claims.get('aud')] if isinstance(claims.get('aud'), str) else claims.get('aud') or []):
            if a not in _seen_auds:
                _seen_auds.add(a)
                log.warning('access gate: audience seen %s (known=%s) host=%s path=%s',
                            a, a in KNOWN_AUDS, request.host, request.path)
    if ok:
        return None
    if m == 'report':
        log.warning('access gate: would refuse %s %s host=%s reason=%s',
                    request.method, request.path, request.host, reason)
        return None
    return ('Please open this through app.wallscourt-farm-academy.co.uk and sign in.', 403)


def install(app):
    app.before_request(_before)

"""
roster_autosync.py — runs the Class Manager's "Sync from Bromcom" by itself.

A Roster Import (Bromcom upload) changes the Postgres roster but not the
spelling class files, which keep each child's spelling record. This checks
the roster every CHECK_EVERY seconds and runs roster_sync.sync_roster when
it has changed since the last sync:

  * Changed = the roster fingerprint (roster_sync.roster_fingerprint) differs
    from the one stored in data/roster_meta.json by the last sync (button or
    automatic).
  * Settled = the same new fingerprint is seen on two checks in a row, so a
    Roster Import that is still part-way through (import, then leavers, then
    class settings) is not synced half-done.
  * Small = a dry run first; if it would remove more than MAX_AUTO_REMOVALS
    children (e.g. the September year change) or fails its safety checks,
    nothing is written and the button is left for a person to press.

Each fingerprint is tried once per process, so a failed or skipped sync does
not repeat every few minutes. Started from app.py on Railway only.
"""

import logging
import os
import threading
import time

import roster_sync

log = logging.getLogger('roster_autosync')

CHECK_EVERY = 600          # seconds between roster checks
FIRST_CHECK_AFTER = 60     # let the app finish starting first
MAX_AUTO_REMOVALS = 15


def new_state():
    return {'pending': None, 'tried': set()}


def check_once(state):
    """One check. Returns a short word saying what happened (for tests/logs)."""
    try:
        pupils = roster_sync.fetch_roster()
    except Exception as e:
        log.warning('roster check: could not fetch roster: %s', e)
        return 'fetch-failed'
    classes = roster_sync.fetch_classes()
    current = roster_sync.roster_fingerprint(pupils, classes)

    try:
        meta, _ = roster_sync._gh_get(roster_sync.META_PATH)
    except Exception as e:
        log.warning('roster check: could not read sync meta: %s', e)
        return 'meta-failed'
    if (meta or {}).get('roster_hash') == current:
        state['pending'] = None
        return 'up-to-date'

    if state['pending'] != current:
        state['pending'] = current          # wait one more check for it to settle
        return 'waiting'
    if current in state['tried']:
        return 'already-tried'
    state['tried'].add(current)

    with roster_sync.SYNC_LOCK:
        dry = roster_sync.sync_roster(apply=False, roster=pupils, classes=classes, trigger='auto')
        if not dry.get('ok'):
            log.warning('roster check: dry run not ok, skipped: %s', dry.get('aborted'))
            return 'skipped-unsafe'
        if len(dry.get('removed') or []) > MAX_AUTO_REMOVALS:
            log.warning('roster check: %d removals is more than %d, left for the button',
                        len(dry['removed']), MAX_AUTO_REMOVALS)
            return 'skipped-too-many-removals'
        res = roster_sync.sync_roster(apply=True, roster=pupils, classes=classes, trigger='auto')
    log.warning('roster check: synced ok=%s added=%d removed=%d renamed=%d',
                res.get('ok'), len(res.get('added') or []),
                len(res.get('removed') or []), len(res.get('renamed') or []))
    try:
        import data_manager
        for cid in roster_sync.ALL_CLASSES:
            data_manager._invalidate(f'data/classes/{cid}.json')
    except Exception:
        pass
    return 'synced' if res.get('ok') else 'sync-failed'


def _loop():
    state = new_state()
    time.sleep(FIRST_CHECK_AFTER)
    while True:
        try:
            check_once(state)
        except Exception as e:             # never let the thread die
            log.warning('roster check crashed: %s', e)
        time.sleep(CHECK_EVERY)


_started = False


def start():
    """Start the background checker once. On only when running on Railway
    (or ROSTER_AUTO_SYNC=1), off with ROSTER_AUTO_SYNC=0."""
    global _started
    flag = os.environ.get('ROSTER_AUTO_SYNC', '')
    if flag == '0' or _started:
        return False
    if flag != '1' and not os.environ.get('RAILWAY_ENVIRONMENT_NAME'):
        return False
    _started = True
    threading.Thread(target=_loop, name='roster-autosync', daemon=True).start()
    return True

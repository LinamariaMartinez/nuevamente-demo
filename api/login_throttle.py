"""Límite de intentos de login: dos contadores independientes con bloqueo progresivo.

- ``ip:<ip>``: frena a quien prueba muchos usuarios desde una misma IP.
- ``cuenta:<usuario>|<ip>``: frena la fuerza bruta sobre una cuenta sin que otra IP pueda bloquearla.
"""

import math
import os
import time
from collections.abc import Callable

from fastapi import Depends, Request

from api.database import Store
from api.dependencies import get_store
from api.errors import ApiError

WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))
MAX_FAILS_PER_ACCOUNT = int(os.getenv("LOGIN_MAX_FAILS", "5"))
MAX_FAILS_PER_IP = int(os.getenv("LOGIN_MAX_FAILS_PER_IP", "20"))
LOCK_SECONDS = (60, 300, 900)  # 1.er, 2.º y siguientes bloqueos.
MAX_KEY_PART = 200


class LoginThrottle:
    def __init__(self, store: Store, clock: Callable[[], float] = time.time):
        self.store = store
        self.clock = clock

    @staticmethod
    def keys(usuario: str, ip: str) -> list[tuple[str, int]]:
        return [
            (f"ip:{ip[:MAX_KEY_PART]}", MAX_FAILS_PER_IP),
            (f"cuenta:{usuario[:MAX_KEY_PART]}|{ip[:MAX_KEY_PART]}", MAX_FAILS_PER_ACCOUNT),
        ]

    def check(self, usuario: str, ip: str) -> None:
        """Lanza 429 si alguno de los contadores está bloqueado."""
        now = self.clock()
        names = [key for key, _ in self.keys(usuario, ip)]
        with self.store.connection() as conn:
            rows = conn.execute(
                f"SELECT bloqueado_hasta FROM intentos_login WHERE clave IN ({','.join('?' * len(names))})", names,
            ).fetchall()
        remaining = max((row["bloqueado_hasta"] - now for row in rows), default=0)
        if remaining > 0:
            seconds = math.ceil(remaining)
            raise ApiError(
                429, "DEMASIADOS_INTENTOS", f"Demasiados intentos fallidos. Reintenta en {seconds} segundos.",
                headers={"Retry-After": str(seconds)},
            )

    def fail(self, usuario: str, ip: str) -> None:
        now = self.clock()
        with self.store.connection() as conn:
            for key, limit in self.keys(usuario, ip):
                row = conn.execute("SELECT * FROM intentos_login WHERE clave = ?", (key,)).fetchone()
                fails, start, locks, locked_until = (
                    (row["fallos"], row["ventana_inicio"], row["bloqueos"], row["bloqueado_hasta"]) if row else (0, now, 0, 0)
                )
                if now - start > WINDOW_SECONDS:
                    fails, start = 0, now
                    if now - locked_until > WINDOW_SECONDS:
                        locks = 0
                fails += 1
                if fails >= limit:
                    locked_until = now + LOCK_SECONDS[min(locks, len(LOCK_SECONDS) - 1)]
                    locks, fails, start = locks + 1, 0, now
                conn.execute(
                    """INSERT INTO intentos_login (clave, fallos, ventana_inicio, bloqueos, bloqueado_hasta)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(clave) DO UPDATE SET fallos = excluded.fallos, ventana_inicio = excluded.ventana_inicio,
                    bloqueos = excluded.bloqueos, bloqueado_hasta = excluded.bloqueado_hasta""",
                    (key, fails, start, locks, locked_until),
                )

    def succeed(self, usuario: str, ip: str) -> None:
        """Un login correcto limpia solo el contador de la cuenta, no el de la IP."""
        with self.store.connection() as conn:
            conn.execute("DELETE FROM intentos_login WHERE clave = ?", (self.keys(usuario, ip)[1][0],))

    def unlock(self, usuario: str) -> None:
        """Desbloqueo manual de una cuenta desde cualquier IP."""
        prefix = f"cuenta:{usuario[:MAX_KEY_PART]}|"
        with self.store.connection() as conn:
            conn.execute("DELETE FROM intentos_login WHERE substr(clave, 1, ?) = ?", (len(prefix), prefix))


def client_ip(request: Request) -> str:
    """No se confía en X-Forwarded-For salvo que TRUST_PROXY esté activo (detrás de un proxy propio)."""
    if os.getenv("TRUST_PROXY") == "1":
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "desconocida"


def get_throttle(request: Request, store: Store = Depends(get_store)) -> LoginThrottle:
    return LoginThrottle(store, getattr(request.app.state, "clock", time.time))

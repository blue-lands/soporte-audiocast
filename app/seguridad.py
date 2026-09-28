"""Comparación de tokens. El panel no tiene usuarios ni claves propias: vale la sesión de la central (app/central.py)."""

import hmac


def token_valido(esperado: str, recibido: str | None) -> bool:
    """Comparación en tiempo constante. Un token esperado vacío no vale nunca."""
    return bool(esperado) and bool(recibido) and hmac.compare_digest(esperado.encode(), recibido.encode())

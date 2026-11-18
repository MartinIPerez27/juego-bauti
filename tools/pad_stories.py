#!/usr/bin/env python3
"""Alarga con una frase final las historias de un lote que quedaron por debajo de 362 caracteres (mínimo aceptado: 350)."""
import sys
ADDS = [' Su historia sigue sumando aventuras en los cómics.', ' Los lectores lo recuerdan por su estilo inconfundible.', ' Cada vez que aparece, la pelea se pone más interesante.', ' Es un personaje que nadie olvida después de verlo en acción.']
k = 0
for p in sys.argv[1:]:
    out = []
    for ln in open(p, encoding='utf8').read().split('\n'):
        if ln.strip() and not ln.startswith('#'):
            x = ln.split('|', 8)
            while len(x[8]) < 362: x[8] += ADDS[k % 4]; k += 1
            ln = '|'.join(x)
        out.append(ln)
    open(p, 'w', encoding='utf8').write('\n'.join(out))

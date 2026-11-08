"""
chemicals.py -- the molecule list (thermosteam Chemicals).
Depends on: nothing local. Used by: units.py, system.py.

Change vs the paper's repo: instead of 4 lumps (C4, C6, C10, C18) we carry EVERY ASF chain length
C4, C6, ... C16 plus one C18+ lump, so the fractionation columns cut at real carbon-number boundaries
(RN = C4-C6, SAF = C8-C16, RD = C18+). This also removes the repo's decane-vs-dodecane surrogate mismatch.
"""
import thermosteam as tmo

OLEFINS = {2: '1-Butene', 3: '1-Hexene', 4: '1-Octene', 5: '1-Decene', 6: '1-Dodecene',
           7: '1-Tetradecene', 8: '1-Hexadecene', 9: '1-Octadecene'}          # key k = number of C2 units
PARAFFINS = {2: 'Butane', 3: 'Hexane', 4: 'Octane', 5: 'Decane', 6: 'Dodecane',
             7: 'Tetradecane', 8: 'Hexadecane', 9: 'Octadecane'}
RN_K, SAF_K, RD_K = (2, 3), (4, 5, 6, 7, 8), (9,)

def create_chemicals():
    ids = ['Water', 'Ethanol', 'Ethylene', 'Hydrogen'] + list(OLEFINS.values()) + list(PARAFFINS.values())
    chems = [tmo.Chemical(i) for i in ids]
    # Solid catalysts: no phase equilibrium needed, only a molar mass so mass flows can be tracked.
    # MW placeholders; Syndol ~ alumina-based (Zhang & Yu 2013), Ni/SiO2-Al2O3 (Heveling 1998), CoMo/Al2O3 (Tao 2017)
    for name, mw in [('Syndol', 102.0), ('Nickel_SiAl', 100.0), ('CobaltMolybdenum', 150.0)]:
        chems.append(tmo.Chemical(name, search_db=False, default=True, phase='s', MW=mw))
    cs = tmo.Chemicals(chems)
    cs.compile()
    return cs

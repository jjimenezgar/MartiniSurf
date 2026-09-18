# Protein preparation regression fixture

`8AV5.pdb` is the unmodified RCSB coordinate download from
https://files.rcsb.org/download/8AV5.pdb (retrieved 2026-09-18).
Entry: https://www.rcsb.org/structure/8AV5
SHA-256: `c91aa1983fd505d22e0fcf1b043c04b22932dc76b149ff681915eebb29644aab`.

This real structure exercises alternate locations, missing GLU20 and LYS261
side-chain atoms, and removal of glycans, heme, ions and waters. Tests use it
locally without downloading structures. The end-to-end regression runs
martinize2 with DSSP and maxwarn=0 and rejects non-finite CG coordinates.

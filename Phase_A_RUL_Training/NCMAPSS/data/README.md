# NCMAPSS data

Put the N-CMAPSS HDF5 file(s) you downloaded directly in this folder (for example `N-CMAPSS_DS01-005.h5`), together with the dataset's readme/PDF if you have it. Do not rename or edit anything. `.h5` files are git-ignored.

## Step 0 prompt (`setup ncmapss`)
```text
STEP 0 - setup ncmapss (SIRE Phase A). Do not start Step 1.
1. Environment: reuse the Phase_A_RUL_Training/.venv and requirements.txt if Step 0 of the CMAPSS track already created them; otherwise create them as described in CMAPSS/data/README.md (GPU check, matching PyTorch build, pinned requirements, environment report).
2. Data audit with h5py (read lazily, never load whole arrays at once): for every .h5 file list every key, shape and dtype, decode the *_var name arrays and print the channel names for W, X_s, X_v, T, A; estimate memory in float32; unit ids in dev and test; flight cycles per unit; samples per flight cycle; Y (RUL) range per unit; distribution of the health-state flag hs and the flight class Fc; NaN/inf counts. Write ../results/data_audit.md.
3. Figures in ../results/figures/: W and X_s signals for one flight cycle early and one late in life of one unit, RUL vs flight cycle for all units, hs over life.
4. List every difference between the files and the expectations in ../README.md section 1 (array names, units, channels).
5. Propose (do not apply) the number of validation units and memory-safe settings for this machine, based on measured RAM and VRAM.
6. Update STATUS.md, report with real output, then STOP.
```

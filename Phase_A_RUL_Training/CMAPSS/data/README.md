# CMAPSS data

Put the files of the NASA C-MAPSS download directly in this folder (no sub-folders, no renaming, no editing):

```text
train_FD001.txt  test_FD001.txt  RUL_FD001.txt
train_FD002.txt  test_FD002.txt  RUL_FD002.txt
train_FD003.txt  test_FD003.txt  RUL_FD003.txt
train_FD004.txt  test_FD004.txt  RUL_FD004.txt
readme.txt   "Damage Propagation Modeling.pdf"
```
The dataset files are git-ignored. Keep the PDF: it is also a first source document for Phase C.

## Step 0 prompt (`setup cmapss`)
```text
STEP 0 - setup cmapss (SIRE Phase A). Do not start Step 1.
1. Environment: create .venv at Phase_A_RUL_Training/. Run nvidia-smi; if an NVIDIA GPU is present install the matching PyTorch build from the official PyTorch index and verify torch.cuda.is_available(). Create ONE pinned Phase_A_RUL_Training/requirements.txt (torch, numpy, pandas, scipy, scikit-learn, lightgbm, optuna, pyyaml, matplotlib, joblib, h5py, tqdm, pytest). Print an environment report (python, torch, CUDA, GPU name, lightgbm).
2. Data audit: open every file in this folder and write ../results/data_audit.md with, per subset: shapes, number of engines in train and test, min/median/max engine length in cycles, shortest test engines, missing values and dtypes, constant and near-constant sensors, operating-setting clusters (FD002/FD004), RUL distribution, check that RUL_FD00X.txt has one row per test engine.
3. Figures in ../results/figures/: sensor trajectories of 3 engines per subset, life-length histogram, correlation of every sensor with RUL (train), operating-setting clusters for FD002 and FD004.
4. List every difference between the data and the expectations in ../README.md section 1.
5. Update STATUS.md, report with real output, then STOP.
```

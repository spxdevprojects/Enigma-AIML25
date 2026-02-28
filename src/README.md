# AIML Pipeline (src)

Welcome to source, this directory mirrors a real world ML workflow, up to 'ready to ship'.\
Here we will take some data, process, train, evaluate, export, and inference on models.\
(Deployment infra is out of scope for this project.)

> If you’re working on Level 3/4, start exploring code in this dir.
> Level 1/2 contributor's work will be promoted into these modules via PRs.

---

## Getting started

Once you have cloned the repo, you may try running the following commands on the terminal while at the root of the project. If you have an env and/or the deps already setup, you can ignore steps 1 and 2 below.

Try running steps 3, 4, and 5. These are supposed to work if you have setup the project properly (there is no buggy code here). If you are facing issues here, please open an [issue](https://github.com/Dristro/HacktoberFest25_AIML/issues) and one of the repo's maintainers will assist you. However, you are encouraged to explore and try to fix the problem yourself.

```bash
# 1) Create/activate a virtual env (optional but recommended)
python -m venv .venv && source .venv/bin/activate
conda create -n [name] python=3.12 && conda activate [name] # or use conda | replace [name] with env-name

# 2) Install minimal deps
pip install -r requirements.txt  # install same as remote
pip install numpy pandas scikit-learn matplotlib  # manually installing
pip install torch torchvision torchaudio  # please refer to https://pytorch.org/get-started/locally/

# 3) Run a config-driven experiment
python -m src.experiments.run_experiment --config src/experiments/configs/lr_default.json

# 4) Export the best model
python -m src.serving_prep.export --run_dir runs/YYYY-MM-DD-HH-MM --format pickle

# 5) Do batch/single inference
python -m src.serving_prep.inference --model artifacts/best.pkl --input samples/inference_batch.csv
```

---

## Project breakdown

This is the thorough breakdown of the repo structure, features, and logic. This will provide a nice starting point for someone new to this repo, and understand what goes where.

## **`src/data`**

All data-related work goes here: loading, processing, storing, and more.

**`data/loaders.py`**: will be used to load data from some `.csv` file, split it and return the data in a nice, readable format.

**`data/preprocessing.py`**: functions like `normalize`, `standard`, `compose` will go here. Once `augment.py` is up and running, functionality from augment.py will also be included in preprocessing.py.

**`data/augment.py`** (work in progress): all data-augmentation functions go here. Functions like: resize-image, shuffle-samples, noise injection, color jittering, etc.

> Often, buggy models are a result of logical bugs in this layer ;)

## **`src/models`**

All model related work goes here.

All models are expected to expose a simple, consistent API:

```python
class BaseModel:
    def forward(self, Xb, yb): ...    # train or inference model
    def save(self, f_path: str): ...  # save model to path (.pkl or .pth)
    @classmethod
    def load(cls, f_path: str): ...   # load model from path (.pkl or .pth)
```

> Note that torch models are expected to retain their API.
> Our project will/should be compatible with both `BaseModel` and `nn.Module`.

Since model API and training are tightly linked, you will have to make sure that any model instance is compatible with `training.trainer`. You may have to make adapters for torch models in training.trainer.py, while BaseModel is plug-and-play.

## **`src/training`**

**`training/trainer.py`**: all training code for `torch` and `base-model` instances. There are 2 functions, one for training numpy-models (`BaseModel` child instance) and torch-models (`nn.Module` child instance). The trainer must log all data from a train run into `src/runs`.

**`training/metrics.py`**: all evaluation metrics for the models. Following metrics are supported: accuracy, precision, recall, f1, roc-auc. More will be added soon (contributors' help needed here).

**`training/visualize.py`**: plot utils. Once a model is created and trained, we can use the visualization utils in `training/visualize.py`.

Once model training is complete, all artifacts (logs, plots, weights) are written into a timestamped `runs/<date_time>/` directory.

## **`src/experiments`**

All experiments are config-driven, that is, you make one config file that defines which: model, dataset, split, learning-rate, experiment-name, etc are used. The config file is then loaded into `run_experiment` to... run it, and log all information. Finally, based on config-save settings, all artifacts are stored in `src/runs/<datetime>/`.

This is the single entrypoint that: it reads a `.json` config, initializes (loaders, models, preprocessor, trainer), trains the model, and finally saves outputs in a single `results.json`. Due to the analytical nature of experiments, artifacts will contain visualizations by default (users can choose not to log visualizations).

All experiment config files are expected to be placed in `src/experiments/configs/`.

Example config file (`configs/dummy-experiment-for-demo.json`):

```json
{
    "experiment_name": "dummy-experiment-for-demo",
    "seed": 42,

    "data_config": {
        "path": "path-to-csv-file",
        "target": "label-column-name",
        "split": ["train", "validation", "test"]
    },

    "preprocessor_config": {
        "op": {
            "name": "normalize",
            "args": {
                "kind": "l2",
                "axis": 1
            }
        },
        "aug": ["resize", "jitter", "noise"]
    },

    "model": {
        "name": "linear_regression",
        "args": {
            "lr": 1e-2,
            "epochs": 100,
            "early_stopping_crit": 1e-6
        }
    },

    "training": {
        "kind": "numpy",
        "early_stopping": true,
        "patience": 10
    },

    "metrics": ["accuracy", "precision", "recall", "f1"],

    "output": {
        "root_dir": "runs",
        "save_best": true,
        "run_name": "dummy-config-file-model"
    },

    "artifacts_config": {
        "export_visualizations": false,
        "save_all": true,
        "trace_metrics": true,
        "save_best_metrics_only": false
    }
}
```

**Running an experiment from config**:

```bash
python -m src.experiments.run_experiment --config src/experiments/configs/dummy-experiment-for-demo.json
```

## **`src/runs/`**

All experiment artifacts are stored in `src/runs/<date_time>/`.\
This includes: `results.json` (metrics), `model.pth`/`model.pkl` (weights), `plots/` (visualizations).

## **`src/serving_prep`**

All code related to exporting and inference goes here.

**`serving_prep/export.py`**: exports the best model from a `runs/<...>` directory into `artifacts/` in a chosen format: `pickle`, `torchscript`, `onnx` (if someone adds this feature).

**Exporting a model**:

```bash
python -m src.serving_prep.export --run_dir runs/YYYY-MM-DD-HH-MM --format pickle
```

**`serving_prep/inference.py`**: loads exported model and runs batch/single prediction.

```bash
python -m src.serving_prep.inference   --model artifacts/best.pkl   --input samples/batch.csv   --output predictions.csv
```

> Add tests for export and inference in `tests/`.

---

## CLI

**`cli/main.py`**: a simple CLI wrapper around common actions (train, evaluate, export, predict).

```bash
# Train from config
python -m src.cli.main train --config src/experiments/configs/config_file.json

# Evaluate an existing run
python -m src.cli.main evaluate --run_dir runs/YYYY-MM-DD-HH-MM

# Export and predict
python -m src.cli.main export --run_dir runs/YYYY-MM-DD-HH-MM --format pickle
python -m src.cli.main predict --model artifacts/best.pkl --input samples/batch.csv
```

---

## Common Level-3 Bug Themes (and where to look)

All bugs found in the repo will be found in the issues section. Here are some common themes and where to look:

- **Normalization is wrong** (L1 vs L2, wrong axis) in `data/preprocessing.py`
- **Matrix shape errors** (e.g., `(N,1)` vs `(N,)`, bad transpose) in `models/*`, `training/trainer.py`
- **Torch issues** (dtype/device/batch) in `models/torch_mlp.py`, `training/trainer.py`
- **Documentation drift** (README logs outdated) update run artifacts + docs

Each bug should be paired with/validated by a failing test in `tests/` (where applicable).

---

## Code Conventions

You are expected to follow these conventions when contributing to keep the codebase consistent:

- **Typing**: Prefer type hints using python's `typing` module.
- **Docstrings**: Google style (see existing code).
- **Tests**: Use `pytest` in `tests/` folder. Name test files `test_*.py`.
- **Dependencies**: Use only those in `requirements.txt` (or add new ones via PR).
- **Reproducibility**: Set seeds in data split and trainers.

**Base model pattern** (numpy):

```python
class NumpyBinaryClassifier(BaseModel):
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Train the model in-place, using (X, y).
        Args:
            X (np.ndarray): shape (N, D) input features
            y (np.ndarray): shape (N,) binary labels (0/1)
        Returns:
            None. Model is trained in-place.
        """
        ...
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict binary labels for X.
        Checks if model is trained, else raises error.
        Args:
            X (np.ndarray): shape (B, D) input features
        Returns:
            y_pred (np.ndarray): shape (B,) binary labels (0/1)
        """
        ...
```

**Torch training contract**:

- Model forward returns **logits** shape `(B, C)` for classification.
- Targets are `LongTensor` shape `(B,)`.
- Device is configurable (`cpu`/`cuda`/`mps`) and consistent.
- Device memory management (e.g., `with torch.no_grad()` in eval) and moving to/from device.

---

## Contributor Checklist

- [ ] Reproduce the bug with a **minimal example** or failing test.
- [ ] Add/extend tests in `tests/` that capture the fix.
- [ ] Keep public APIs stable (or document breaking changes prominently).
- [ ] Update visuals/metrics if they change due to your fix.
- [ ] Add a short note in PR body: root cause, fix, tests, impact.
- [ ] Ensure code style matches existing code.

---

## What 'Ready to Ship' Means Here

- A trained model exists in `runs/<...>`
- An exported artifact exists in `artifacts/` (or inside run dir)
- `inference.py` can load it and produce correct predictions against a **validated schema**
- Metrics & plots retained for auditability (in `runs/`)

From here, you could containerize or wire a FastAPI server—but that’s outside the scope of this repo.

---

Happy hacking! If you’re unsure where to start, open an issue and tag it with `question`.

---

## Automative OSINT Tool

A passive OSINT utility is available at `src/automative_osint.py`.

### Features
- Detects indicator type automatically (`domain`, `email`, `ip`, `username`).
- Collects DNS/TLS/certificate-transparency information for domains.
- Enriches emails by analyzing their domain.
- Performs reverse-DNS and geo/ASN lookup for IP addresses.
- Checks common social platforms for username presence.
- Produces a JSON report for further analysis/automation.

### Usage
```bash
python src/automative_osint.py example.com 8.8.8.8 analyst_user --output report.json
```

### Notes
- This script is designed for passive recon and defensive investigation workflows.
- Some sources may rate limit requests.
- Always ensure you have legal authorization for investigations.

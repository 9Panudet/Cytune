# SMAC3 RF backend — explicit record (Step 0.1.3, required by roadmap §1.3)

**Recorded experimental constant: SMAC3 2.4.0's random-forest surrogate is
scikit-learn-backed (`EPMRandomForest`, a `sklearn.ensemble._forest.ForestRegressor`
subclass). pyrfr is NOT installed and is offered upstream only as the optional extra
`smac[pyrfr]`.**

Evidence (probe `scripts/probe_smac_backend.py` run in image `f9328a8a92f8`, 2026-06-11;
verbatim output):

```
python 3.12.3
Cython 3.2.5
numpy 2.4.6
scipy 1.17.1
scikit-learn 1.8.0
smac 2.4.0
ConfigSpace 1.2.2
pytest 9.0.3
pyrfr: ABSENT from environment
default model class: smac.model.random_forest.random_forest.RandomForest
MRO: smac.model.random_forest.random_forest.RandomForest -> smac.model.random_forest.abstract_random_forest.AbstractRandomForest -> smac.model.abstract_model.AbstractModel -> builtins.object
module source imports pyrfr: True
module source imports sklearn: True
wrapped estimator attributes (pre-fit): [('_pca', 'sklearn.decomposition._pca.PCA'), ('_scaler', 'sklearn.preprocessing._data.MinMaxScaler')]
fitted forest class: smac.model.random_forest.random_forest.EPMRandomForest
fitted forest MRO: smac.model.random_forest.random_forest.EPMRandomForest -> sklearn.ensemble._forest.ForestRegressor -> sklearn.base.RegressorMixin -> sklearn.ensemble._forest.BaseForest -> sklearn.base.MultiOutputMixin -> sklearn.ensemble._base.BaseEnsemble -> sklearn.base.MetaEstimatorMixin -> sklearn.base.BaseEstimator -> sklearn.utils._repr_html.base.ReprHTMLMixin -> sklearn.utils._repr_html.base._HTMLDocumentationLinkMixin -> sklearn.utils._metadata_requests._MetadataRequester -> builtins.object
predict smoke: mu=0.027959 var=0.000522
BACKEND VERDICT: sklearn
```

Reading notes:
- "module source imports pyrfr: True" is a substring scan hitting **comments** in
  `smac/model/random_forest/random_forest.py` (e.g. "...compared to the pyrfr version");
  the module's import block (lines 1–19) imports sklearn machinery only. Verified by
  direct source inspection during D3 (see /logs/defects/D3.md).
- The forest is built lazily at `_train` (`self._rf = EPMRandomForest(...)`, line 747),
  hence "none found by scan" pre-fit and the definitive MRO post-fit.
- smac 2.4.0 metadata: `Requires-Dist: pyrfr>=0.9.0; extra == "pyrfr"` — opt-in only.

Consequences for §2 (surrogate): the §2.1 "SMAC3-RF" surrogate is the sklearn-backed
implementation above. Any future switch (e.g. installing smac[pyrfr]) is a change to a
pinned experimental constant and requires the human + a lock re-resolution + this file
updated.

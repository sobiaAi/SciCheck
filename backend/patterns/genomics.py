from . import Pattern


GEN_001 = Pattern(
    id="GEN-001",
    name="Two-Step Batch Correction Error",
    severity="Critical",
    doc_link="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3307112/",
    trigger_imports=("sva", "combat", "pycombat", "limma", "edger", "pydeseq2",
                     "scvi", "anndata", "scanpy", "harmony", "scanorama", "bbknn"),
    seed_functions=("ComBat", "ComBat_seq", "removeBatchEffect", "sva", "pycombat",
                    "SCVI", "SCANVI", "run_harmony", "integrate"),
    detection_prompt="""Analyze this code for a two-step batch correction error.

A bug exists when:
A batch effect correction tool — including classical methods
(ComBat, ComBat_seq, removeBatchEffect, SVA) OR modern
probabilistic/deep-learning methods (scVI, scANVI, Harmony,
Scanorama, BBKNN) — is applied to produce corrected or
integrated data, AND the corrected output is then passed
directly to a standard statistical test (t-test, ANOVA,
linear model, Wilcoxon, or equivalent) that assumes sample
independence, WITHOUT any correction for the induced
correlation structure.

For variational methods (scVI/scANVI): a bug exists when
the model is trained on the FULL dataset including future
test samples, and the resulting latent representations or
corrected counts are then fed into a classifier or
hypothesis test that is evaluated with cross-validation.
This is leakage because the model has already encoded
information from the test donors during training.

This is a bug because batch correction — whether linear or
variational — induces dependencies between samples. Standard
statistical tests assume independence. Combining them
produces artificially small p-values or inflated classifier
accuracy that will not replicate on truly independent data.

NOT a bug if:
- Batch is included as a covariate in a linear model
  rather than being corrected out beforehand
- The corrected data is used only for visualization (PCA,
  heatmaps, UMAP) and not for hypothesis testing or
  classifier training
- A mixed-effects model explicitly accounts for the
  correlation structure
- For scVI/scANVI: the model is retrained within each
  cross-validation fold using only training-fold donors,
  and test donors are embedded using the fold-specific
  encoder

Does this code contain a two-step batch correction error?
Answer YES or NO, then explain specifically what you found
and at approximately which line.""",
)


GEN_002 = Pattern(
    id="GEN-002",
    name="Gene Name Corruption via Automatic Type Conversion",
    severity="Critical",
    doc_link="https://www.nature.com/articles/s41588-020-0669-3",
    trigger_imports=("pandas", "openpyxl", "xlrd", "readxl"),
    seed_functions=("read_csv", "read_excel", "read_table", "read.csv", "read_excel"),
    detection_prompt="""Analyze this code for gene name corruption vulnerability.

A bug exists when:
A file containing gene names or identifiers (CSV, TSV,
or Excel) is read using pandas read_csv, read_excel,
pd.read_table, or R equivalents like read.csv or
read_excel, WITHOUT explicitly protecting the gene name
column from automatic type conversion (i.e., without
dtype=str, dtype={'column': str}, or colClasses='character'
equivalent), AND those gene names are subsequently used
for any downstream operation such as merging with a
reference database, pathway enrichment analysis, or
differential expression analysis.

This is a bug because default parsers convert gene symbols
like SEPT1, MARCH1, DEC1 to dates or numbers silently.
The gene is permanently lost from all downstream analyses.

NOT a bug if:
- dtype=str or equivalent string protection is explicitly
  specified on the read call
- Gene names are read from a programmatically generated
  source with guaranteed string types
- Immediate post-read validation against a reference gene
  list is performed

Does this code contain a gene name corruption vulnerability?
Answer YES or NO, then explain specifically what you found
and at approximately which line.""",
)


GEN_003 = Pattern(
    id="GEN-003",
    name="Feature Selection Leakage in Genomic ML",
    severity="Critical",
    doc_link="https://www.cell.com/patterns/fulltext/S2666-3899(23)00159-3",
    trigger_imports=("sklearn", "torch", "tensorflow", "keras", "xgboost", "lightgbm",
                     "scvi", "scanpy", "anndata"),
    seed_functions=(),
    detection_prompt="""BEFORE evaluating anything else, scan the code for an
explicit model training call (e.g. .fit(), cross_val_score(),
GridSearchCV(), .train(), a PyTorch training loop, scVI/scANVI
.train(), or any equivalent classifier/regressor/embedding
training step). If NO such call exists in the code, answer
NO immediately and stop.

Analyze this code for pre-split data leakage in a genomic
machine learning pipeline. There are TWO forms of this bug:

FORM 1 — Label-Informed Feature Selection Leakage:
Differential expression analysis, statistical testing
(t-test, ANOVA, DESeq2, edgeR, limma), or any label-informed
feature ranking is performed on the FULL dataset BEFORE the
data is split into training and test sets or before
cross-validation folds are defined, AND the selected features
are subsequently used to train a classifier.

FORM 2 — Pre-Split Embedding Leakage (unsupervised):
Any of the following is applied to the FULL dataset including
future test samples, BEFORE cross-validation splits are
defined, and the result is used as input to a downstream
classifier:
- Highly Variable Gene (HVG) selection using sc.pp.highly_variable_genes()
  or equivalent across all samples
- Dimensionality reduction trained on all samples (PCA, NMF,
  autoencoders, scVI, scANVI) where the fitted transform or
  model encodes test-sample information
- Z-score normalization, StandardScaler, or any data-wide
  scaling fitted on the full dataset before splitting

Both forms leak test-sample information into the training
process. Even unsupervised preprocessing on the full dataset
can inflate performance estimates by up to 30% because the
representation is implicitly tuned to the full sample
distribution, including test donors.

The correct approach for FORM 2 is:
- HVG selection must be performed on training-fold cells only
- scVI/PCA must be fit on training-fold data and used to
  TRANSFORM (not retrain on) test-fold data
- Scalers must be fit on X_train only, then applied to X_test

NOT a bug if:
- Feature selection or embedding is performed strictly inside
  each cross-validation fold using only training fold data
- An external independent cohort is used for feature selection
- The only processing on the full dataset is raw count loading
  or quality control (cell filtering, doublet removal) that
  does not use sample identity labels or encode sample-level
  biological signal
- There is no downstream classifier training step anywhere
  in the code

Does this code contain pre-split data leakage (either form)?
Answer YES or NO, specify which FORM applies, then explain
specifically what you found and at approximately which line.""",
)


GEN_004 = Pattern(
    id="GEN-004",
    name="Genome Assembly Version Mismatch",
    severity="High",
    doc_link="https://genome.ucsc.edu/FAQ/FAQformat.html",
    trigger_imports=("pysam", "pybedtools", "pyvcf", "allel", "cyvcf2", "biopython"),
    seed_functions=(),
    detection_prompt="""Analyze this code for genome assembly version mismatch.

A bug exists when:
Both GRCh37/hg19 AND GRCh38/hg38 are referenced in
active use within the same pipeline — for example,
alignment is performed against one assembly while
annotation files (GTF, GFF, BED, VCF) reference the
other assembly — WITHOUT an explicit coordinate
conversion step (liftover) between them.

This is a bug because genomic coordinates are not
transferable between assemblies. Mixing them silently
shifts every variant position, region boundary, and
gene annotation, producing incorrect results that look
normal.

NOT a bug if:
- An explicit liftover step using liftOver, CrossMap,
  or equivalent is present between the two assembly
  references
- Multiple assemblies appear only in comments,
  documentation, or print statements
- Each assembly is processed in a completely isolated
  independent branch

Does this code contain a genome assembly version mismatch?
Answer YES or NO, then explain specifically what you
found and at approximately which line.""",
)


GENOMICS_PATTERNS: list[Pattern] = [GEN_001, GEN_002, GEN_003, GEN_004]

# SPEC: Naive Bayes Classifier v1

**Module:** `tools/naive_bayes_classifier/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, math, collections)  
**Priority:** Medium (text classification, spam detection, sentiment analysis foundation)

---

## Overview

Train and evaluate Naive Bayes text classifiers. Pure, stateless training: no persistent state beyond JSON model output. All computation from pre-tokenized input. Emit trained model (class priors + feature likelihoods) suitable for downstream classification of new documents.

**Design principle:** Deterministic model training. Accept labeled corpus (documents with class labels); emit trained model as JSON. Classifier emits class predictions + probability estimates. No randomness, fully reproducible.

**Use case:** "I have 500 labeled traces (success/failure). Train a Naive Bayes classifier to predict class from tool sequence. Then classify 10 new traces and show prediction confidence."

---

## Scope

### In Scope ✓
- Train Naive Bayes classifier: learn class priors + feature likelihoods from labeled corpus
- Support multi-class classification (2 classes, 3+ classes)
- Feature types: token presence/absence (Bernoulli), token frequency (Multinomial)
- Classification: predict class + compute posterior probabilities for new documents
- Confidence scores: probability estimates for predictions
- Detailed output: feature contributions to classification decision
- Batch training: multiple classifiers simultaneously (e.g., one-vs-rest)
- Smoothing: add-one (Laplace) smoothing for unseen features

### Out of Scope ✗
- Feature selection or engineering (input features are tokens; no extraction)
- Hyperparameter tuning or cross-validation
- Ensemble methods or boosting
- Online/incremental learning
- Non-text features (audio, images, structured data)
- Calibration of probabilities beyond Naive Bayes

---

## Module Structure

```
tools/naive_bayes_classifier/
  __init__.py                     # exports main functions
  core.py                         # model training and classification
  features.py                     # feature extraction and computation
  smoothing.py                    # Laplace smoothing
  cli.py                          # argparse CLI
  classifier_schema.py            # dataclasses for input/output
  README.md                        # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `train_classifier(training_corpus: list, feature_type: str = "bernoulli", smoothing: str = "laplace") -> dict`

**Purpose:** Train Naive Bayes classifier from labeled corpus.

**Input:**

- `training_corpus` (list): Documents with class labels:
  ```json
  [
    {
      "id": "doc_1",
      "tokens": ["machine", "learning", "success"],
      "class": "positive"
    },
    {
      "id": "doc_2",
      "tokens": ["deep", "learning", "success"],
      "class": "positive"
    },
    {
      "id": "doc_3",
      "tokens": ["random", "failure"],
      "class": "negative"
    },
    {
      "id": "doc_4",
      "tokens": ["bug", "error", "failure"],
      "class": "negative"
    }
  ]
  ```

- `feature_type` (str, default "bernoulli"): One of `["bernoulli", "multinomial"]`
  - `bernoulli`: Binary features (token present or absent)
  - `multinomial`: Token counts (frequency of each token)

- `smoothing` (str, default "laplace"): Smoothing strategy. Currently only `"laplace"` (add-one smoothing)

**Output:**

```json
{
  "tool": "naive_bayes_classifier",
  "version": "v1",
  "run_id": "nb_train_001",
  "timestamp": "2026-07-14T15:30:00Z",
  "input_summary": {
    "training_documents": 4,
    "classes": ["positive", "negative"],
    "feature_type": "bernoulli",
    "vocabulary_size": 8
  },
  "model": {
    "classes": ["positive", "negative"],
    "class_priors": {
      "positive": 0.5,
      "negative": 0.5
    },
    "class_counts": {
      "positive": 2,
      "negative": 2
    },
    "feature_likelihoods": {
      "positive": {
        "machine": 0.4,
        "learning": 0.4,
        "success": 0.4,
        "deep": 0.2,
        "random": 0.1,
        "bug": 0.1,
        "error": 0.1,
        "failure": 0.1
      },
      "negative": {
        "machine": 0.1,
        "learning": 0.1,
        "success": 0.1,
        "deep": 0.1,
        "random": 0.4,
        "bug": 0.4,
        "error": 0.4,
        "failure": 0.4
      }
    },
    "smoothing": "laplace",
    "feature_type": "bernoulli"
  },
  "training_stats": {
    "accuracy_on_training_set": 1.0,
    "per_class_precision": {
      "positive": 1.0,
      "negative": 1.0
    },
    "per_class_recall": {
      "positive": 1.0,
      "negative": 1.0
    }
  },
  "metadata": {
    "computation_time_ms": 5,
    "training_documents_used": 4
  }
}
```

#### 2. `classify(model: dict, document: dict, return_probabilities: bool = True) -> dict`

**Purpose:** Classify a single document using trained model.

**Input:**

- `model` (dict): Trained model from `train_classifier`
- `document` (dict): Document to classify:
  ```json
  {
    "id": "test_doc_1",
    "tokens": ["machine", "learning", "success"]
  }
  ```
- `return_probabilities` (bool, default true): Include posterior probability estimates

**Output:**

```json
{
  "tool": "naive_bayes_classifier",
  "version": "v1",
  "run_id": "nb_classify_001",
  "timestamp": "2026-07-14T15:30:05Z",
  "classification": {
    "document_id": "test_doc_1",
    "predicted_class": "positive",
    "confidence": 0.92,
    "posterior_probabilities": {
      "positive": 0.92,
      "negative": 0.08
    },
    "feature_contributions": {
      "machine": {
        "log_likelihood": 0.40,
        "class": "positive"
      },
      "learning": {
        "log_likelihood": 0.40,
        "class": "positive"
      },
      "success": {
        "log_likelihood": 0.40,
        "class": "positive"
      }
    },
    "decision_log": "Class positive: log_prior=-0.693 + sum(log_likelihoods)=1.20 = total=0.507"
  },
  "metadata": {
    "computation_time_ms": 1,
    "model_classes": ["positive", "negative"],
    "feature_type": "bernoulli"
  }
}
```

#### 3. `batch_classify(model: dict, documents: list, return_probabilities: bool = True) -> dict`

**Purpose:** Classify multiple documents at once.

**Input:**

- `model` (dict): Trained model
- `documents` (list): Documents to classify
- `return_probabilities` (bool, default true): Include probabilities

**Output:**

```json
{
  "batch_classification_run_id": "nb_batch_001",
  "documents_classified": 10,
  "classifications": [
    {single_classification_result_1},
    {single_classification_result_2}
  ],
  "summary": {
    "class_distribution": {
      "positive": 7,
      "negative": 3
    },
    "average_confidence": 0.87,
    "most_confident_class": "positive"
  }
}
```

#### 4. `evaluate_classifier(model: dict, test_corpus: list) -> dict`

**Purpose:** Evaluate trained classifier on held-out test set.

**Input:**

- `model` (dict): Trained model
- `test_corpus` (list): Labeled test documents (same format as training)

**Output:**

```json
{
  "evaluation_run_id": "nb_eval_001",
  "test_documents": 20,
  "model_classes": ["positive", "negative"],
  "results": {
    "accuracy": 0.85,
    "per_class_metrics": {
      "positive": {
        "precision": 0.88,
        "recall": 0.82,
        "f1_score": 0.85
      },
      "negative": {
        "precision": 0.81,
        "recall": 0.88,
        "f1_score": 0.84
      }
    },
    "confusion_matrix": {
      "positive": {
        "positive": 9,
        "negative": 2
      },
      "negative": {
        "positive": 1,
        "negative": 8
      }
    },
    "macro_f1": 0.845
  },
  "metadata": {
    "computation_time_ms": 8
  }
}
```

---

## Naive Bayes Variants

### Bernoulli Naive Bayes (default)

**Model:** Binary features (token present/absent in document)

**Training:**
- P(class) = count(class) / total_documents
- P(token | class) = (count(token in class) + 1) / (count(class) + 2) [with Laplace smoothing]

**Classification:**
- P(class | tokens) ∝ P(class) × ∏ P(token | class) for each token in document

### Multinomial Naive Bayes

**Model:** Token frequencies (count of each token in document)

**Training:**
- P(class) = count(class) / total_documents
- P(token | class) = (total_count(token in class) + 1) / (total_tokens_in_class + vocabulary_size)

**Classification:**
- P(class | tokens) ∝ P(class) × ∏ P(token | class)^count(token)

---

## Configuration & Parameters

### Standard Config (Shared Contract)
- `lowercase` (bool, default true): Normalize tokens
- `verbose` (bool, default false): Include detailed stats

### Naive Bayes Specific
- `feature_type` (string, default "bernoulli"): One of `["bernoulli", "multinomial"]`
- `smoothing` (string, default "laplace"): Smoothing strategy (currently only "laplace")

---

## CLI Interface

```bash
# Train classifier
python -m tools.naive_bayes_classifier \
  --input training_corpus.json \
  --feature-type bernoulli \
  --output model.json

# Classify single document
python -m tools.naive_bayes_classifier \
  --model model.json \
  --classify document.json \
  --output classification.json

# Batch classify
python -m tools.naive_bayes_classifier \
  --model model.json \
  --input test_documents.json \
  --batch \
  --output classifications.json

# Evaluate on test set
python -m tools.naive_bayes_classifier \
  --model model.json \
  --input test_corpus.json \
  --evaluate \
  --output evaluation.json

# Train with multinomial features
python -m tools.naive_bayes_classifier \
  --input training_corpus.json \
  --feature-type multinomial \
  --output model_multinomial.json

# Verbose training
python -m tools.naive_bayes_classifier \
  --input training_corpus.json \
  --verbose \
  --output model.json
```

---

## Input/Output Formats

### Input (JSON)

**Shape A (Training):**
```json
{
  "corpus": [
    {
      "id": "doc_1",
      "tokens": ["token1", "token2"],
      "class": "positive"
    }
  ],
  "config": {
    "feature_type": "bernoulli"
  }
}
```

**Shape B (Classification):**
```json
{
  "model": {... trained model ...},
  "document": {
    "id": "test_1",
    "tokens": ["token1", "token2"]
  }
}
```

### Output (JSON)

Standard Historical AI results format. Training output includes `model` field with class priors and feature likelihoods. Classification output includes `classification` field with predicted class and probabilities.

---

## Algorithm Details

### Training (Bernoulli)

1. **Compute class priors:** P(class) = count(class) / total_docs
2. **Extract vocabulary:** All unique tokens from training corpus
3. **For each class:**
   - For each token in vocabulary:
     - Count docs where token appears (Bernoulli) or sum token frequencies (Multinomial)
     - Apply Laplace smoothing: (count + 1) / (class_count + 2)
4. **Emit:** Model with class priors and feature likelihoods

### Classification

1. **Initialize:** log_score(class) = log(P(class))
2. **For each token in document:**
   - log_score(class) += log(P(token | class))
3. **Normalize:** Convert log-scores to probabilities (softmax)
4. **Emit:** Predicted class + posterior probabilities

### Complexity

- **Time (train):** O(docs * avg_tokens * unique_classes) ≈ O(N)
- **Time (classify):** O(tokens_in_doc * classes) ≈ O(K) where K = #classes
- **Space:** O(vocabulary_size * classes)

---

## Edge Cases & Error Handling

1. **Unseen tokens:** Laplace smoothing assigns non-zero probability
2. **Single token in document:** Classify normally (one feature)
3. **Empty document:** Use only class prior (no token contributions)
4. **Single class in training:** Predict always that class (trivial classifier)
5. **Unbalanced classes:** Priors reflect class distribution (no reweighting)
6. **Malformed input:** Exit 1 (ValueError)

---

## Testing Strategy

### Explicit Test Cases (TEST-naive_bayes_classifier_examples.json)

1. **Simple 2-class classifier:**
   - 4 docs (2 positive, 2 negative) with clear token separation
   - Expected: High accuracy on training set

2. **Multi-class (3+):**
   - 6 docs, 3 classes
   - Expected: Correct class distribution in priors

3. **Bernoulli vs. Multinomial:**
   - Same corpus, train both variants
   - Expected: Different probabilities but reasonable predictions

4. **Unseen tokens:**
   - Train on vocabulary, classify with new token
   - Expected: Laplace smoothing prevents zero probability

5. **Empty document:**
   - Classify doc with 0 tokens
   - Expected: Predict by class prior alone

6. **Evaluation metrics:**
   - Train, test, compute precision/recall/F1
   - Expected: Metrics sum correctly, confusion matrix is consistent

7. **Batch classification:**
   - Classify 5 docs in batch
   - Expected: Same results as individual classifications

---

## Performance Notes

- **Training:** 100 docs, 1000 unique tokens, 2 classes → <10ms
- **Classification:** Single doc → <1ms
- **Batch classification:** 1000 docs → <100ms
- **Memory:** O(vocabulary_size * classes) typically <10MB

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, math, collections, itertools
- **External libs:** None (stdlib only)
- **Resource limits:** Max 100K training docs, 100K vocabulary, 100 classes
- **Hardware:** CPU-only

---

## Related Tools

- **Tokenizer v1:** Pre-processes text (upstream)
- **Text Search v1:** Pattern matching (alternative approach)
- **Frequency Analysis v1:** Token distribution analysis (complementary)

---

## Non-Goals

- **Feature engineering:** No custom feature extraction (tokens only)
- **Hyperparameter tuning:** No cross-validation or grid search
- **Ensemble methods:** Single Naive Bayes classifier only
- **Non-text classification:** Tokens only (no numeric features)
- **Online learning:** Batch training only

---

## Post-1.0 Extensions

1. **Logistic regression classifier:** Alternative to Naive Bayes
2. **SVM or other algorithms:** Multiple classifier types
3. **Feature selection:** Reduce vocabulary based on information gain
4. **Probability calibration:** Calibrate probability estimates
5. **Online/incremental learning:** Update classifier with new data
6. **Domain adaptation:** Transfer learning from one class distribution to another

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch  
**Related:** Historical AI Shared Contract v1, Tokenizer v1, Frequency Analysis v1

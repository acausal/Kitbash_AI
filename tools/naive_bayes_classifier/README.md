# naive_bayes_classifier

Deterministic Naive Bayes text classifier (Historical AI batch). Bernoulli /
Multinomial features, Laplace smoothing, plus classify / batch / evaluate with
precision/recall/F1. Stateless, stdlib-only. See SPEC-naive_bayes_classifier_v1.md.

## Library

```python
from tools.naive_bayes_classifier import train_classifier, classify, batch_classify, evaluate_classifier
corpus = [
  {"id":"d1","tokens":["machine","learning","success"],"class":"positive"},
  {"id":"d2","tokens":["deep","learning","success"],"class":"positive"},
  {"id":"d3","tokens":["random","failure"],"class":"negative"},
  {"id":"d4","tokens":["bug","error","failure"],"class":"negative"},
]
model = train_classifier(corpus, feature_type="bernoulli")
c = classify(model, {"id":"t1","tokens":["machine","learning","success"]})
ev = evaluate_classifier(model, corpus)
```

Multinomial: `train_classifier(corpus, feature_type="multinomial")`.

## CLI

```bash
echo '{"corpus":[...]}' | python -m tools.naive_bayes_classifier --train --feature-type bernoulli
python -m tools.naive_bayes_classifier --classify --model model.json --input doc.json
python -m tools.naive_bayes_classifier --batch --model model.json --input docs.json
python -m tools.naive_bayes_classifier --evaluate --model model.json --input test.json
```

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Notes
- Deterministic: same corpus + config -> identical model and predictions.
- `run_id`/`timestamp` differ per call; model + classifications are deterministic.

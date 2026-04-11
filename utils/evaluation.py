import logging

logger = logging.getLogger(__name__)

def calculate_metrics(y_true, y_pred):
    """
    Calculates Precision, Recall, and F1 Score.
    (Step 2 of Match Accuracy Evaluation Report)
    """
    # y_true: List of boolean (True if actually relevant)
    # y_pred: List of boolean (True if recommended by system)
    
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": round(precision, 2),
        "recall": round(recall, 2),
        "f1_score": round(f1, 2)
    }

def generate_evaluation_report(test_results):
    """
    test_results: List of (actual_relevant, is_recommended)
    """
    y_true = [res[0] for res in test_results]
    y_pred = [res[1] for res in test_results]
    
    metrics = calculate_metrics(y_true, y_pred)
    
    report = f"""
📊 MATCH ACCURACY EVALUATION REPORT
-----------------------------------
Metric          Value
Precision       {metrics['precision']}
Recall          {metrics['recall']}
F1 Score        {metrics['f1_score']}
-----------------------------------
Interpretation:
- High precision -> accurate recommendations
- High recall -> covers more relevant jobs
"""
    logger.info(report)
    return metrics, report

if __name__ == '__main__':
    # Sample evaluation data
    # (actual_relevance, system_recommendation)
    sample_data = [
        (True, True), (True, True), (False, True), (True, False),
        (True, True), (False, False), (True, True), (False, True)
    ]
    _, report = generate_evaluation_report(sample_data)
    print(report)
